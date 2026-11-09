"""Synthetic records and real authenticated HTTP acceptance for the human view."""
from datetime import timedelta
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import test_hearth2_receipts as fixtures
from test import test_hearth2_api as api
from hearth2.store import Principal,RecordError


class HumanStatusTests(unittest.TestCase):
    def setUp(self):
        fixtures.ReceiptTests.setUp(self)
        self.assertIsNotNone(importlib.util.find_spec('hearth2.human_status'),'human status read model missing')
        from hearth2 import human_status as m
        self.m=m
        self.controllers={self.controller.id}
        self.expectations={self.controller.id:{'cadence_seconds':300,'grace_seconds':60}}

    def view(self,**options):
        return self.m.human_status(self.store,self.controllers,options.get('expectations',self.expectations),options.get('project_id'))

    def tick(self,**changes):
        values=dict(request_id='first-status-poll',expected_seq=0,
            expected_epoch=self.store.control_snapshot()['restore_epoch'],evidence=['synthetic-poll-evidence'])
        values.update(changes)
        return self.store.runner_tick(self.controller,**values)

    def test_poll_is_recent_at_boundary_overdue_after_and_replay_never_refreshes(self):
        tick=self.tick()
        self.time+=timedelta(seconds=360)
        self.assertEqual(self.view()['controllers'][0]['poll_state'],'recent')
        self.time+=timedelta(microseconds=1)
        row=self.view()['controllers'][0]
        self.assertEqual(row['poll_state'],'stale')
        self.assertEqual(row['last_completed_at'],tick['at'])
        self.assertEqual(row['supplied_references'],['synthetic-poll-evidence'])
        self.assertEqual(row['cadence_seconds'],300)
        self.assertEqual(row['grace_seconds'],60)
        self.assertEqual(self.tick(),tick)
        self.assertEqual(self.view()['controllers'][0]['poll_state'],'stale')

    def test_missing_tick_missing_expectation_and_future_time_are_unknown(self):
        self.assertEqual(self.view()['controllers'][0]['reason'],'no_completed_poll')
        self.tick()
        row=self.view(expectations={})['controllers'][0]
        self.assertEqual((row['poll_state'],row['reason']),('unknown','timing_not_configured'))
        self.time-=timedelta(seconds=1)
        self.assertEqual(self.view()['controllers'][0]['reason'],'poll_time_in_future')

    def test_restore_epoch_hides_old_tick_but_preserves_historical_failure(self):
        tick=self.tick()
        self.store.control_failure(self.controller,kind='runner_stale',target=self.controller.id,key='outage',
            expected_seq=0,expected_epoch=tick['restore_epoch'],state='open',evidence=['outside-observation'])
        with self.store.transaction() as db:db.execute("UPDATE record_meta SET restore_epoch='synthetic-new-epoch'")
        result=self.view()
        self.assertEqual(result['controllers'][0]['poll_state'],'unknown')
        self.assertTrue(result['failures'][0]['historical'])

    def test_new_poll_does_not_erase_open_failure_and_reading_never_mutates(self):
        tick=self.tick()
        self.store.control_failure(self.controller,kind='runner_stale',target=self.controller.id,key='outage',
            expected_seq=0,expected_epoch=tick['restore_epoch'],state='open',evidence=['outside-observation'])
        self.tick(request_id='next-status-poll',expected_seq=tick['seq'])
        before=self.store.snapshot()
        result=self.view()
        self.assertEqual(result['controllers'][0]['poll_state'],'recent')
        self.assertEqual(result['failures'][0]['state'],'open')
        self.assertFalse(result['failures'][0]['historical'])
        self.assertEqual(self.store.snapshot(),before)

    def test_notice_metadata_cannot_invent_delivery_and_private_run_data_is_absent(self):
        notice=self.store.append_notice(self.controller,{'task_id':self.task['id'],'recipient':'rad',
            'kind':'interface_changed','reference':'synthetic-evidence','delivered_at':'FORGED-DELIVERY',
            'acknowledged_at':'FORGED-ACK','private':'PRIVATE-SENTINEL'},claim=self.claim)
        result=self.view()
        row=result['notices'][0]
        self.assertEqual((row['id'],row['delivery_state'],row['recorded_at']),(notice['id'],'unconfirmed',None))
        self.assertEqual(row['supplied_references'],['synthetic-evidence'])
        self.assertEqual(result['tasks'][0]['state'],'running')
        encoded=json.dumps(result)
        for value in ('FORGED-DELIVERY','FORGED-ACK','PRIVATE-SENTINEL',self.claim['id']):self.assertNotIn(value,encoded)

    def test_project_filter_omits_other_tasks_and_notices_unknown_project_refuses(self):
        other=self.store.create_project(self.rad,{'title':'Other project'})
        result=self.view(project_id=other['id'])
        self.assertEqual(result['tasks'],[]);self.assertEqual(result['notices'],[])
        self.assertEqual(len(result['controllers']),1)
        with self.assertRaises(RecordError):self.view(project_id='not-found')

    def test_strict_timing_config_and_disabled_runtime_no_database(self):
        from hearth2.api import Runtime
        from test_hearth2_timing_config import FakeApp
        for raw in ('[]','{"unknown":{"cadence_seconds":300,"grace_seconds":60}}',
                '{"controller":{"cadence_seconds":true,"grace_seconds":60}}',
                '{"controller":{"cadence_seconds":300,"grace_seconds":-1}}',
                '{"controller":{},"controller":{}}','PRIVATE-CONFIG'):
            with tempfile.TemporaryDirectory() as directory:
                kwargs=dict(enabled=True,data_dir=directory,principal=lambda:'admin',typed_auth=lambda:None,
                    same_origin=lambda r:True,bearer_principal=lambda r:'controller',human_ids=['admin'],
                    controller_ids=['controller'],worker_ids=[],authenticated=True,poll_expectations=raw)
                runtime=Runtime(FakeApp(),**kwargs)
                with self.assertRaises(RuntimeError):runtime.initialize()
                self.assertFalse(Path(directory,'hearth2.sqlite3').exists())
                runtime=Runtime(FakeApp(),**{**kwargs,'enabled':False})
                runtime.initialize()
                self.assertFalse(Path(directory,'hearth2.sqlite3').exists())

    def test_malformed_poll_time_is_unknown_and_config_boundaries_are_explicit(self):
        tick=self.tick()
        with self.store.transaction() as db:db.execute("UPDATE audit_events SET at='not-a-time' WHERE seq=?",(tick['seq'],))
        self.assertEqual(self.view()['controllers'][0]['reason'],'poll_time_unusable')
        self.assertEqual(self.m.poll_expectations(None,{'controller'}),{})
        expected={'controller':{'cadence_seconds':86400,'grace_seconds':3600}}
        self.assertEqual(self.m.poll_expectations(json.dumps(expected),{'controller'}),expected)
        for timing in ({'cadence_seconds':86401,'grace_seconds':0},{'cadence_seconds':1,'grace_seconds':3601},
                {'cadence_seconds':1,'grace_seconds':False},{'cadence_seconds':1,'grace_seconds':0,'extra':1}):
            with self.assertRaises(RuntimeError):self.m.poll_expectations(json.dumps({'controller':timing}),{'controller'})

    def test_task_result_states_and_recovered_failures_keep_distinct_labels(self):
        from hearth2.status_page import render_status
        for state,label in (('review','Awaiting independent review'),('reviewed','Awaiting human acceptance'),('accepted','Accepted')):
            with self.store.transaction() as db:db.execute('UPDATE tasks SET state=? WHERE id=?',(state,self.task['id']))
            self.assertIn(label,render_status(self.view()))
        tick=self.tick()
        opened=self.store.control_failure(self.controller,kind='runner_stale',target=self.controller.id,key='outage',
            expected_seq=0,expected_epoch=tick['restore_epoch'],state='open',evidence=['outside-observation'])
        self.store.control_failure(self.controller,kind='runner_stale',target=self.controller.id,key='outage',
            expected_seq=opened['seq'],expected_epoch=tick['restore_epoch'],state='recovered',evidence=['outside-recovery'])
        page=render_status(self.view())
        self.assertIn('Recovery reported',page);self.assertIn('outside-recovery',page)

    def test_self_recovery_is_labelled_self_reported_and_not_verified_health(self):
        from hearth2.status_page import render_status
        epoch=self.store.control_snapshot()['restore_epoch']
        opened=self.store.control_failure(self.controller,kind='runner_stale',target=self.controller.id,key='self-outage',
            expected_seq=0,expected_epoch=epoch,state='open',evidence=['my-own-report'])
        self.store.control_failure(self.controller,kind='runner_stale',target=self.controller.id,key='self-outage',
            expected_seq=opened['seq'],expected_epoch=epoch,state='recovered',evidence=['my-own-recovery'])
        view=self.view();page=render_status(view)
        self.assertIn('Self-reported',page)
        self.assertIn('Recovery reported',page)
        self.assertNotIn('>Recovered</span>',page)
        self.assertIn('<span class="badge unknown">Recovery reported</span>',page)
        self.assertTrue(view['failures'][0]['self_reported'])
        self.assertEqual(view['failures'][0]['supplied_references'],['my-own-recovery'])

    def test_separate_controller_report_does_not_become_verified_evidence(self):
        from hearth2.status_page import render_status
        epoch=self.store.control_snapshot()['restore_epoch']
        self.store.control_failure(Principal('supervisor','controller'),kind='runner_stale',target=self.controller.id,
            key='supervisor-outage',expected_seq=0,expected_epoch=epoch,state='open',evidence=['supervisor-reference'])
        value=self.view()
        self.assertFalse(value['failures'][0]['self_reported'])
        self.assertEqual(value['failures'][0]['reference_provenance'],'reporter_supplied_unverified')
        page=render_status(value)
        self.assertIn('Reporter-supplied references (unverified)',page)
        self.assertIn('Inspect record',page)
        self.assertNotIn('View evidence',page)

    def test_running_shows_claim_lease_expiry_without_implying_worker_liveness(self):
        from hearth2.status_page import render_status
        row=self.view()['tasks'][0]
        self.assertEqual(row['claim_lease_until'],self.claim['lease_until'])
        self.assertEqual(row['lease_state'],'current')
        self.assertEqual(row['worker_liveness'],'unverified')
        page=render_status(self.view())
        self.assertIn('Running (claim recorded)',page)
        self.assertIn('Worker liveness is unverified',page)
        self.assertIn(self.claim['lease_until'],page)
        self.time+=timedelta(seconds=901)
        value=self.view();page=render_status(value)
        self.assertEqual(value['tasks'][0]['lease_state'],'expired')
        self.assertEqual(value['tasks'][0]['state'],'running')
        self.assertIn('Claim lease expired',page)
        self.assertNotIn('Worker stopped',page)

    def test_old_epoch_or_malformed_lease_remains_unknown(self):
        with self.store.transaction() as db:db.execute("UPDATE claims SET lease_until='not-a-time' WHERE id=?",(self.claim['id'],))
        self.assertEqual(self.view()['tasks'][0]['lease_state'],'unknown')
        with self.store.transaction() as db:
            db.execute('UPDATE claims SET lease_until=?,restore_epoch=? WHERE id=?',
                (self.claim['lease_until'],'old-period',self.claim['id']))
        row=self.view()['tasks'][0]
        self.assertEqual(row['lease_state'],'unknown')
        self.assertIsNone(row['claim_lease_until'])
        with self.store.transaction() as db:
            db.execute('UPDATE claims SET restore_epoch=?,generation=generation+1 WHERE id=?',
                (self.claim['restore_epoch'],self.claim['id']))
        self.assertEqual(self.view()['tasks'][0]['lease_state'],'unknown')

    def test_page_escapes_all_stored_identity_and_evidence_without_active_links(self):
        from hearth2.status_page import render_status
        self.store.append_notice(self.controller,{'task_id':self.task['id'],'recipient':'<svg onload=alert(1)>',
            'kind':'question','reference':'javascript:alert(1)'},claim=self.claim)
        with self.store.transaction() as db:
            db.execute('UPDATE tasks SET assignee=? WHERE id=?',('<script>private</script>',self.task['id']))
        page=render_status(self.view())
        self.assertNotIn('<svg',page);self.assertNotIn('<script>',page)
        self.assertIn('&lt;script&gt;',page)
        self.assertIn('javascript:alert(1)',page)
        self.assertNotIn('href="javascript:',page)


class HumanStatusHTTPTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):api.Hearth2APITests.setUpClass.__func__(cls)
    @classmethod
    def tearDownClass(cls):api.Hearth2APITests.tearDownClass.__func__(cls)
    asyncSetUp=api.Hearth2APITests.asyncSetUp
    asyncTearDown=api.Hearth2APITests.asyncTearDown

    async def test_both_routes_require_human_and_disabled_remains_closed(self):
        for path in ('/api/hearth2/status','/api/hearth2/status/view','/api/hearth2/status/style.css'):
            self.assertEqual((await self.client.get(path)).status_code,401)
            for token in ('codex-test-token','controller-fixture-token'):
                self.assertEqual((await self.client.get(path,headers={'Authorization':'Bearer '+token})).status_code,403)
            response=await self.client.get(path,headers={'Authorization':'Bearer admin-test-token'})
            self.assertEqual(response.status_code,200,response.text)
            self.assertEqual(response.headers['cache-control'],'no-store')
            with patch.object(self.memory.h2_runtime,'enabled',False):
                self.assertEqual((await self.client.get(path,headers={'Authorization':'Bearer admin-test-token'})).status_code,409)

    async def test_human_bearer_and_human_browser_session_are_both_supported(self):
        response=await self.client.get('/api/hearth2/status',headers={'Authorization':'Bearer admin-test-token'})
        self.assertEqual(response.status_code,200,response.text)
        login=await self.client.post('/api/auth/login',json={'token':'admin-test-token'})
        self.assertEqual(login.status_code,200,login.text)
        for path in ('/api/hearth2/status','/api/hearth2/status/view','/api/hearth2/status/style.css'):
            session=await self.client.get(path)
            self.assertEqual(session.status_code,200,session.text)
            denied=await self.client.get(path,headers={'Authorization':'Bearer controller-fixture-token'})
            self.assertEqual(denied.status_code,403,denied.text)

    async def test_human_workflow_poll_evidence_and_notice_escape(self):
        from datetime import datetime,timezone
        async def post(path,value,token='admin-test-token'):
            response=await api.Hearth2APITests.post(self,path,value,token)
            self.assertEqual(response.status_code,200,response.text)
            return response.json()
        headers={'Authorization':'Bearer admin-test-token'}
        project=await post('/projects',{'title':'Onboarding handoff'})
        fields=dict(recipient='codex',ask='Draft the onboarding handoff',done_means='The next step is clear',
            inputs=['synthetic-brief'],**{'return':'Review the draft'})
        plan=await post('/projects/'+project['id']+'/plans',{'content_ref':'synthetic-plan',
            'actions':{'draft':{**fields,'requires':{}}}})
        decision=await post('/decisions',{'plan_id':plan['id'],'intended_subject':'admin',
            'expires_at':(datetime.now(timezone.utc)+timedelta(days=1)).isoformat()})
        await post('/decisions/'+decision['id']+'/actions',{'expected_revision':1,'action':'approve','source':'synthetic-human'})
        await post('/roles/codex',{'model':'gpt-6.1-sol','family':'openai','role':'senior'})
        task=await post('/tasks',{'project_id':project['id'],'plan_id':plan['id'],'action_id':'draft',**fields})
        claim=await post('/tasks/'+task['id']+'/claim',{'expected_revision':1,'request_id':'status-view-handoff'},'controller-fixture-token')
        await post('/notices',{'claim':claim,'notice':{'task_id':task['id'],'recipient':'admin',
            'kind':'interface_changed','reference':'<img src=x onerror=alert(1)>','delivered_at':'FORGED-ACK'}},'controller-fixture-token')
        store=self.memory.h2_runtime.store
        start=datetime.now(timezone.utc)
        with patch.object(store,'now',return_value=start),patch.object(self.memory.h2_runtime,'poll_expectations',
                {'controller':{'cadence_seconds':300,'grace_seconds':60}}):
            epoch=store.control_snapshot()['restore_epoch']
            tick=await post('/control/ticks',{'request_id':'status-view-completed','expected_seq':0,
                'expected_epoch':epoch,'evidence':['synthetic-poll-proof']},'controller-fixture-token')
            page=await self.client.get('/api/hearth2/status/view?project_id='+project['id'],headers=headers)
            self.assertEqual(page.status_code,200,page.text)
            for text in ('Draft the onboarding handoff','Running','Recorded','Delivery unconfirmed','Poll recent','synthetic-poll-proof'):
                self.assertIn(text,page.text)
            self.assertIn('&lt;img src=x onerror=alert(1)&gt;',page.text)
            self.assertNotIn('<img src=x',page.text);self.assertNotIn('FORGED-ACK',page.text)
            self.assertNotIn('<script',page.text)
            self.assertIn('<details',page.text)
            self.assertIn("frame-ancestors 'none'",page.headers['content-security-policy'])
            before=store.snapshot()
            with patch.object(store,'now',return_value=start+timedelta(seconds=361)):
                stale=await self.client.get('/api/hearth2/status/view',headers=headers)
                self.assertIn('Poll overdue',stale.text)
                self.assertIn(tick['at'],stale.text)
                replay=await post('/control/ticks',{'request_id':'status-view-completed','expected_seq':0,
                    'expected_epoch':epoch,'evidence':['synthetic-poll-proof']},'controller-fixture-token')
                self.assertEqual(replay['at'],tick['at'])
                again=await self.client.get('/api/hearth2/status',headers=headers)
                self.assertEqual(again.json()['controllers'][0]['poll_state'],'stale')
            self.assertEqual(store.snapshot(),before)
        unknown=await self.client.get('/api/hearth2/status/view',headers=headers)
        self.assertIn('Poll status unknown',unknown.text)
        self.assertIn('Timing expectation not configured',unknown.text)


if __name__=='__main__':unittest.main()
