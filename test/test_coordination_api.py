"""Flag, identity, principal and compatibility boundaries using real ASGI/SQLite."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from test import test_work_api


class CoordinationAPITests(unittest.IsolatedAsyncioTestCase):
    # Reuse only integration setup helpers, not the inherited test collection.
    setUpClass = classmethod(test_work_api.WorkAPITests.setUpClass.__func__)
    tearDownClass = classmethod(test_work_api.WorkAPITests.tearDownClass.__func__)
    post = test_work_api.WorkAPITests.post
    project = test_work_api.WorkAPITests.project
    async def asyncSetUp(self):
        await test_work_api.WorkAPITests.asyncSetUp(self)
        self.coord_temp = tempfile.TemporaryDirectory()
        self.original_store = self.memory.coordination_store
        self.memory.coordination_store = self.memory._coordination_module.CoordinationStore(
            Path(self.coord_temp.name)/'coordination.sqlite3', enabled=True)
        self.memory.coordination_store.initialize()
        tokens = self.memory.load_tokens(); tokens['claude'] = 'claude-test-token'
        self.memory.save_tokens(tokens)
        self.humans = patch.object(self.memory, 'HUMAN_IDS', {'rad'})
        self.humans.start()
        self.identity = dict(work_kind='thread_plan',work_id='plan_fixture',room_id='!tasks:test',thread_id='$root')
        self.wait_payload = {**self.identity,'expected_generation':0,'parties':[
            {'kind':'agent','id':'claude','required_surface':'interactive'}],
            'source_event':'$request','since':'2026-10-10T12:00:00Z'}

    async def asyncTearDown(self):
        self.memory.coordination_store = self.original_store
        self.humans.stop()
        tokens=self.memory.load_tokens();tokens.pop('claude',None);self.memory.save_tokens(tokens)
        self.coord_temp.cleanup()
        await test_work_api.WorkAPITests.asyncTearDown(self)

    async def answer(self, kind='final_completion', token='claude-test-token', **extra):
        return await self.post('/api/coordination/answer', {**self.identity,'expected_generation':1,
            'party_id':'claude','answer_kind':kind,'source_event':'$reply','since':'2026-10-10T13:00:00Z',
            'summary':'Concrete review result','evidence':['commit_fixture'],**extra}, token)

    async def test_feature_disabled_is_read_empty_write_rejected_and_no_migration(self):
        path=Path(self.coord_temp.name)/'missing'/'disabled.sqlite3'
        self.memory.coordination_store=self.memory._coordination_module.CoordinationStore(path)
        self.memory.coordination_store.initialize()
        result=await self.post('/api/coordination/wait',self.wait_payload,'codex-test-token')
        self.assertEqual(result.status_code,409,result.text)
        read=await self.client.get('/api/coordination',params=self.identity,headers={'Authorization':'Bearer codex-test-token'})
        self.assertEqual(read.json()['coordination_waiting_on'],[])
        self.assertFalse(path.parent.exists())

    async def test_auth_csrf_spoof_and_unknown_party_fail_without_state_changes(self):
        self.assertEqual((await self.client.post('/api/coordination/wait',json=self.wait_payload)).status_code,401)
        self.assertEqual((await self.post('/api/coordination/wait',self.wait_payload,'codex-test-token',Origin='https://evil.test')).status_code,403)
        spoof={**self.wait_payload,'owner':'claude'}
        self.assertEqual((await self.post('/api/coordination/wait',spoof,'codex-test-token')).status_code,400)
        unknown={**self.wait_payload,'parties':[{'kind':'agent','id':'missing','required_surface':'interactive'}]}
        self.assertEqual((await self.post('/api/coordination/wait',unknown,'codex-test-token')).status_code,400)
        valid=await self.post('/api/coordination/wait',self.wait_payload,'codex-test-token')
        self.assertEqual(valid.status_code,200,valid.text)
        self.assertEqual((await self.answer(token='codex-test-token')).status_code,403)
        self.assertEqual((await self.answer(summary='')).status_code,400)
        ignored=await self.answer('progress')
        self.assertFalse(ignored.json()['changed'])
        self.assertEqual((await self.answer()).json()['coordination_waiting_on'],[])

    async def test_mcp_and_bootstrap_reads_show_pending_obligations_without_spec_bump(self):
        self.assertEqual((await self.post('/api/coordination/wait',self.wait_payload,'codex-test-token')).status_code,200)
        context=self.memory.CURRENT_PRINCIPAL.set('claude')
        try:
            result=self.memory.bootstrap('claude',compact=True)
            self.assertEqual(result['service']['agent_spec_version'],'1.5')
            self.assertTrue(result['capabilities']['coordination_waiting_on'])
            self.assertEqual(result['coordination_waiting_on'][0]['work_id'],'plan_fixture')
            answered=self.memory.coordination_answer(**self.identity,expected_generation=1,party_id='claude',
                answer_kind='change_list',source_event='$mcp_reply',since='2026-10-10T13:00:00Z',
                summary='Fix the validation',evidence=['commit_fixture'])
            self.assertEqual(answered['coordination_waiting_on'][0]['id'],'codex')
        finally:
            self.memory.CURRENT_PRINCIPAL.reset(context)

    async def test_prerequisites_and_coordination_are_separate_on_get_and_mcp(self):
        project=await self.project()
        dep=(await self.post(f"/api/work/projects/{project['id']}/tasks",{'title':'Dependency','acceptance':'Evidence','assignee':'codex'})).json()
        task=(await self.post(f"/api/work/projects/{project['id']}/tasks",{'title':'Consumer','acceptance':'Evidence',
            'assignee':'codex','dependencies':[dep['id']]})).json()
        self.identity={**self.identity,'work_kind':'task','work_id':task['id']}
        payload={**self.wait_payload,**self.identity}
        result=await self.post('/api/coordination/wait',payload,'codex-test-token')
        self.assertEqual(result.status_code,200,result.text)
        board=(await self.client.get('/api/work',headers={'Authorization':'Bearer codex-test-token'})).json()
        consumer=next(t for t in board['tasks'] if t['id']==task['id'])
        dependency=next(t for t in board['tasks'] if t['id']==dep['id'])
        self.assertEqual(consumer['waiting_on'],[dep['id']])
        self.assertEqual(consumer['dependency_waiting_on'],[dep['id']])
        self.assertEqual(consumer['coordination_waiting_on'][0]['id'],'claude')
        self.assertEqual(dependency['coordination_waiting_on'],[])
        self.assertEqual(dependency['dependency_waiting_on'],[])
        self.assertEqual((await self.post('/api/coordination/wait',payload,'claude-test-token')).status_code,403)
        context=self.memory.CURRENT_PRINCIPAL.set('codex')
        try:
            mcp_board=self.memory.work_board(project['id'])
            self.assertEqual(next(t for t in mcp_board['tasks'] if t['id']==task['id'])['waiting_on'],[dep['id']])
        finally:
            self.memory.CURRENT_PRINCIPAL.reset(context)

    async def test_pass_human_approval_and_relay_owner_do_not_grant_execution_authority(self):
        await self.post('/api/coordination/wait',self.wait_payload,'codex-test-token')
        passed=await self.answer('pass_needing_human',approval_party='rad')
        self.assertEqual(passed.json()['coordination_waiting_on'][0]['kind'],'human')
        denied=await self.answer('approved',token='codex-test-token',party_id='rad',source_event='$approval',expected_generation=passed.json()['generation'])
        self.assertEqual(denied.status_code,403)
        approved=await self.answer('approved',token='admin-test-token',party_id='rad',source_event='$approval',expected_generation=passed.json()['generation'])
        self.assertEqual(approved.status_code,200,approved.text)
        self.assertFalse(approved.json()['grants_authority'])
        context=self.memory.CURRENT_PRINCIPAL.set('codex')
        try:
            relay=self.memory.relay_request('codex','Read-only coordination fixture')
        finally:
            self.memory.CURRENT_PRINCIPAL.reset(context)
        relay_payload={**self.wait_payload,'work_kind':'relay','work_id':relay['relay_id']}
        self.assertEqual((await self.post('/api/coordination/wait',relay_payload,'claude-test-token')).status_code,403)
        self.assertEqual((await self.post('/api/coordination/wait',relay_payload,'codex-test-token')).status_code,200)
        context=self.memory.CURRENT_PRINCIPAL.set('codex')
        try:
            entry=next(e for e in self.memory.relay_inbox_for('codex')['entries'] if e['relay_id']==relay['relay_id'])
            self.assertEqual(entry['coordination_waiting_on'][0]['id'],'claude')
        finally:
            self.memory.CURRENT_PRINCIPAL.reset(context)

    async def test_running_task_requires_matching_claim_and_missing_fields_are_client_errors(self):
        project=await self.project()
        task=(await self.post(f"/api/work/projects/{project['id']}/tasks",{'title':'Claim fence',
            'acceptance':'Evidence','assignee':'codex'})).json()
        await self.post(f"/api/work/tasks/{task['id']}/action",{'action':'ready','revision':task['revision']})
        claim=(await self.post(f"/api/work/tasks/{task['id']}/action",{'action':'claim'},'codex-test-token')).json()
        payload={**self.wait_payload,'work_kind':'task','work_id':task['id']}
        self.assertEqual((await self.post('/api/coordination/wait',payload,'codex-test-token')).status_code,409)
        self.assertEqual((await self.post('/api/coordination/wait',{**payload,'claim_id':'old'},'codex-test-token')).status_code,409)
        live=await self.post('/api/coordination/wait',{**payload,'claim_id':claim['claim_id']},'codex-test-token')
        self.assertEqual(live.status_code,200,live.text)
        bad=await self.post('/api/coordination/answer',self.identity,'claude-test-token')
        self.assertEqual(bad.status_code,400,bad.text)

    async def test_work_context_exposes_coordination_only_and_does_not_change_claim_state(self):
        project=await self.project()
        task=(await self.post(f"/api/work/projects/{project['id']}/tasks",{'title':'Context',
            'acceptance':'Evidence','assignee':'codex'})).json()
        payload={**self.wait_payload,'work_kind':'task','work_id':task['id']}
        self.assertEqual((await self.post('/api/coordination/wait',payload,'codex-test-token')).status_code,200)
        # Exercise the real projection while keeping local embedding model downloads out of this boundary test.
        with patch.object(self.memory,'search_drawers',return_value={'results':[]}):
            response=await self.client.get(f"/api/work/tasks/{task['id']}/context",headers={'Authorization':'Bearer codex-test-token'})
        self.assertEqual(response.status_code,200,response.text)
        item=response.json()['task']
        self.assertEqual(item['waiting_on'],[])
        self.assertEqual(item['dependency_waiting_on'],[])
        self.assertEqual(item['coordination_waiting_on'][0]['id'],'claude')
        self.assertEqual(item['state'],'draft')

    async def test_malformed_values_and_missing_generation_are_rejected_as_client_errors(self):
        invalid=[{**self.wait_payload,'work_kind':[]},
            {**self.wait_payload,'parties':[{'kind':[],'id':'claude','required_surface':'interactive'}]},
            {k:v for k,v in self.wait_payload.items() if k!='expected_generation'}]
        for payload in invalid:
            with self.subTest(payload=payload):
                result=await self.post('/api/coordination/wait',payload,'codex-test-token')
                self.assertEqual(result.status_code,400,result.text)
        bad_json=await self.client.post('/api/coordination/wait',content='{bad',
            headers={'Authorization':'Bearer codex-test-token','Content-Type':'application/json'})
        self.assertEqual(bad_json.status_code,400,bad_json.text)

    async def test_mcp_state_reads_current_generation_for_thread_plan(self):
        await self.post('/api/coordination/wait',self.wait_payload,'codex-test-token')
        context=self.memory.CURRENT_PRINCIPAL.set('codex')
        try:
            state=self.memory.coordination_state(**self.identity)
            self.assertEqual(state['generation'],1)
            self.assertEqual(state['coordination_waiting_on'][0]['id'],'claude')
        finally:
            self.memory.CURRENT_PRINCIPAL.reset(context)
