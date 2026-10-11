import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from test import test_inbox_ack_api as ack
from test.test_inbox_usability import ACTION

class UsabilityAPI(unittest.IsolatedAsyncioTestCase):
    setUpClass=classmethod(ack.InboxAcknowledgementAPI.setUpClass.__func__)
    tearDownClass=classmethod(ack.InboxAcknowledgementAPI.tearDownClass.__func__)
    async def asyncSetUp(self):
        await ack.InboxAcknowledgementAPI.asyncSetUp(self)
        self.old_store=self.memory.coordination_store
        self.memory.coordination_store=self.memory._coordination_module.CoordinationStore(Path(self.temp.name)/'coord.sqlite',enabled=True)
        self.memory.coordination_store.initialize()
        self.item['sender']='codex'
        self.client.cookies.set(self.memory.SESSION_COOKIE,self.memory.create_session('@rad:hearth.test','matrix'))
    async def asyncTearDown(self):
        self.memory.coordination_store=self.old_store
        await ack.InboxAcknowledgementAPI.asyncTearDown(self)
    async def snapshot(self):return (await self.client.get('/api/inbox')).json()
    async def action(self,item,action='reassign',party=None,reason='Codex can handle it.'):
        return await self.client.post('/api/inbox/action',json={'kind':item['kind'],'item_id':item.get('id') or item['event_id'],
            'state_key':item['state_key'],'action':action,'party':party or {'kind':'agent','id':'codex','required_surface':'interactive'},'reason':reason})
    async def test_reassign_moves_attention_and_stale_key_is_rejected(self):
        first=await self.snapshot();item=first['items'][0]
        result=await self.action(item);self.assertEqual(result.status_code,200,result.text)
        fresh=await self.snapshot();self.assertEqual(fresh['open_total'],0)
        self.assertEqual(fresh['waiting_on_agents']['codex'][0]['required_surface'],'interactive')
        self.assertEqual((await self.action(item)).status_code,409)
        self.item['latest_qualifying_event']='$new'
        self.assertEqual((await self.snapshot())['open_total'],1)
    async def test_dispatch_preserves_existing_reassignment(self):
        item=(await self.snapshot())['items'][0]
        self.assertEqual((await self.action(item)).status_code,200)
        item=(await self.snapshot())['waiting_on_agents']['codex'][0]
        self.assertEqual((await self.action(item,'dispatch')).status_code,200)
        fresh=await self.snapshot()
        self.assertEqual(len(fresh['waiting_on_agents']['codex']),1)
        self.assertEqual([i['kind'] for i in fresh['items']],['dispatch_required'])
    async def test_dispatch_has_priority_and_exact_session_steps(self):
        item=(await self.snapshot())['items'][0]
        result=await self.action(item,'dispatch');self.assertEqual(result.status_code,200,result.text)
        fresh=await self.snapshot()
        dispatch=next(i for i in fresh['items'] if i['kind']=='dispatch_required')
        self.assertIn('Open Codex on the laptop',' '.join(dispatch['human_action']['steps']))
        self.assertEqual(dispatch['priority'],'high')
        self.assertEqual(result.json()['wake_state'],'needs_interactive')
    async def test_agents_bearer_reviewers_csrf_unknown_and_empty_reason_are_rejected(self):
        item=(await self.snapshot())['items'][0]
        self.client.cookies.clear()
        self.assertEqual((await self.action(item)).status_code,401)
        self.client.cookies.set(self.memory.SESSION_COOKIE,self.memory.create_session('codex','token','codex-test-token'))
        self.assertEqual((await self.action(item)).status_code,403)
        self.client.cookies.set(self.memory.SESSION_COOKIE,self.memory.create_session('@rad:hearth.test','matrix'))
        self.assertEqual((await self.client.post('/api/inbox/action',headers={'Origin':'https://evil.test'},json={})).status_code,403)
        self.assertEqual((await self.action(item,party={'kind':'agent','id':'missing','required_surface':'interactive'})).status_code,400)
        self.assertEqual((await self.action(item,reason='')).status_code,400)
        self.assertEqual(self.memory.coordination_store.attention_audit(),[])
    async def test_coordination_human_agent_split_and_failed_delivery(self):
        store=self.memory.coordination_store
        store.set_wait('codex',False,owner='codex',work_kind='thread_plan',work_id='plan',room_id='!tasks:test',thread_id='$plan',
            parties=[{'kind':'human','id':'rad','required_surface':'interactive','human_action':ACTION},
                     {'kind':'agent','id':'codex','required_surface':'interactive'}],source_event='$ask',since='2026-10-11T12:00:00Z')
        snap=await self.snapshot()
        self.assertTrue(any(i['kind']=='coordination_wait' and i['human_action']==ACTION for i in snap['items']))
        self.assertEqual(snap['waiting_on_agents']['codex'][0]['work_id'],'plan')
        self.assertGreaterEqual(snap['waiting_on_agents']['codex'][0]['age_minutes'],0)
    async def test_compact_bootstrap_instructs_inbox_first(self):
        with patch.object(self.memory,'_principal',lambda:'codex'):
            result=self.memory.bootstrap('codex',compact=True)
        self.assertIn('Before taking a new prompt',result['interactive_start'])
    async def test_ingested_auth_expired_receipt_records_reason_without_losing_fields(self):
        import json
        context=self.memory.CURRENT_PRINCIPAL.set('codex')
        try:
            value=self.memory.write_checkpoint('codex','desktop (auto)','heartbeat-runner',
                json.dumps({'process_exit':1,'error':'OAuth session expired','run_id':'fixture'}))
            receipt=json.loads(self.memory.checkpoints.get(ids=[value['checkpoint_id']],include=['documents'])['documents'][0])
            self.assertEqual(receipt['reason'],'auth_expired');self.assertEqual(receipt['run_id'],'fixture')
        finally:self.memory.CURRENT_PRINCIPAL.reset(context)
    async def test_work_actions_and_agent_dispatch_bootstrap_priority(self):
        self.patches[-1].stop()
        context=self.memory.CURRENT_PRINCIPAL.set('codex')
        try:relay=self.memory.create_relay('codex','Review the inbox','codex','laptop','!tasks:test $root')
        finally:self.memory.CURRENT_PRINCIPAL.reset(context)
        work=(await self.client.get('/api/dashboard/work')).json()
        item=next(i for i in work['items'] if i['id']==relay['relay_id'])
        self.assertEqual(item['kind'],'work_item')
        result=await self.action(item,'dispatch');self.assertEqual(result.status_code,200,result.text)
        context=self.memory.CURRENT_PRINCIPAL.set('codex')
        try:
            bootstrap=self.memory.bootstrap('codex',compact=True)
            entry=next(i for i in bootstrap['relay_inbox']['entries'] if i['relay_id']==relay['relay_id'])
            self.assertEqual(entry['priority'],'high')
            self.assertTrue(any(i['item_id']==relay['relay_id'] for i in bootstrap['attention_requests']))
        finally:self.memory.CURRENT_PRINCIPAL.reset(context)
    async def test_failed_delivery_is_in_human_inbox(self):
        store=self.memory.coordination_store
        ids=dict(work_kind='thread_plan',work_id='fail-plan',room_id='!tasks:test',thread_id='$fail')
        store.set_wait('codex',False,owner='codex',parties=[{'kind':'agent','id':'claude','required_surface':'interactive'}],source_event='$ask',since='2026-10-11T12:00:00Z',**ids)
        store.answer('claude',False,expected_generation=1,party_id='claude',answer_kind='final_completion',source_event='$answer',since='2026-10-11T12:05:00Z',summary='Finished',evidence=['commit'],**ids)
        def conflict(job):raise self.memory._coordination_module.DeliveryConflict('identity conflict')
        store.drain('codex',conflict,'2026-10-11T12:06:00Z')
        item=next(i for i in (await self.snapshot())['items'] if i['kind']=='failed_continuation')
        self.assertIn('identity conflict',item['body']);self.assertTrue(item['source_refs']);self.assertTrue(item['human_action']['steps'])
    async def test_declared_background_notifier_uses_human_matrix_identity(self):
        import httpx
        requests=[]
        def handler(request):
            requests.append(request)
            if request.url.path.endswith('whoami'):return httpx.Response(200,json={'user_id':'@rad:hearth.test'})
            return httpx.Response(200,json={'event_id':'$dispatch'})
        original=httpx.AsyncClient
        declaration={'active':True,'agent':'codex','dispatch_via_mentions':True,'dispatch_room_id':'!tasks:test','matrix_user_id':'@codex:hearth.test'}
        self.data['rooms']={'!tasks:test':{}}
        self.item['required_surface']='background'
        item=(await self.snapshot())['items'][0]
        payload={'kind':item['kind'],'item_id':item['event_id'],'state_key':item['state_key'],'action':'dispatch',
                 'party':{'kind':'agent','id':'codex','required_surface':'background'},'reason':'Pick up the review.'}
        with patch.object(self.memory,'WATCHER_REGISTRY',[declaration]),patch.object(self.memory,'HOMESERVER_URL','https://matrix.test'),\
             patch.object(self.memory.httpx,'AsyncClient',lambda **kw:original(transport=httpx.MockTransport(handler),**kw)):
            result=await self.client.post('/api/inbox/action',json=payload,headers={'X-Matrix-Token':'fixture-human-matrix'})
        self.assertEqual(result.status_code,200,result.text);self.assertEqual(result.json()['wake_state'],'mention_posted')
        self.assertEqual(len(requests),2)
        import json
        message=json.loads(requests[1].content)
        self.assertEqual(message['m.mentions']['user_ids'],['@codex:hearth.test'])
        self.assertNotIn('fixture-human-matrix',message['body'])
    async def test_dispatch_cannot_bypass_an_interactive_obligation(self):
        store=self.memory.coordination_store
        ids=dict(work_kind='thread_plan',work_id='interactive',room_id='!tasks:test',thread_id='$interactive')
        store.set_wait('codex',False,owner='codex',parties=[{'kind':'agent','id':'codex','required_surface':'interactive'}],
            source_event='$ask',since='2026-10-11T12:00:00Z',**ids)
        item=(await self.snapshot())['waiting_on_agents']['codex'][0]
        result=await self.action(item,'dispatch',{'kind':'agent','id':'codex','required_surface':'background'})
        self.assertEqual(result.status_code,409)
    async def test_missing_background_runtime_gives_session_opening_steps(self):
        item=(await self.snapshot())['items'][0]
        target={'kind':'agent','id':'codex','required_surface':'background'}
        self.assertEqual((await self.action(item,'reassign',target)).status_code,200)
        item=(await self.snapshot())['waiting_on_agents']['codex'][0]
        with patch.object(self.memory,'WATCHER_REGISTRY',[]):result=await self.action(item,'dispatch',target)
        self.assertEqual(result.json()['wake_state'],'no_background_runtime_declared')
        launch=next(i for i in (await self.snapshot())['items'] if i['kind']=='dispatch_required')
        self.assertIn('Open Codex on the laptop',' '.join(launch['human_action']['steps']))
