"""Small authenticated user workflow for an independently invoked observer."""
import json, os, tempfile, unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path
from unittest.mock import patch
from test import test_hearth2_api as api
from test.test_hearth2_timing_config import FakeApp
from hearth2.api import Runtime


class PollObserverAcceptanceTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.observer_environment=patch.dict(os.environ,{'HEARTH2_OBSERVER_IDS':'watcher',
            'HEARTH2_POLL_EXPECTATIONS':json.dumps({'controller':{'cadence_seconds':60,'grace_seconds':10}})})
        cls.observer_environment.start();api.Hearth2APITests.setUpClass.__func__(cls)
        tokens=cls.memory.load_tokens();tokens['watcher']='watcher-fixture-token';cls.memory.save_tokens(tokens)

    @classmethod
    def tearDownClass(cls):
        api.Hearth2APITests.tearDownClass.__func__(cls);cls.observer_environment.stop()

    asyncSetUp=api.Hearth2APITests.asyncSetUp
    asyncTearDown=api.Hearth2APITests.asyncTearDown
    post=api.Hearth2APITests.post

    async def saved(self,path,data,token):
        r=await self.post(path,data,token);self.assertEqual(r.status_code,200,r.text);return r.json()

    async def status(self):
        r=await self.client.get('/api/hearth2/status',headers={'Authorization':'Bearer admin-test-token'})
        self.assertEqual(r.status_code,200,r.text);return r.json()

    async def test_stopped_controller_observer_detection_and_resumption_stay_separate(self):
        store=self.memory.h2_runtime.store;start=datetime(2026,11,8,12,tzinfo=timezone.utc)
        epoch=store.control_snapshot()['restore_epoch'];before=store.snapshot()
        prior=next((t['seq'] for t in store.control_snapshot()['ticks'] if t['runner']=='controller'),0)
        tick=dict(request_id='observer-acceptance-poll',expected_seq=prior,expected_epoch=epoch,evidence=['controller says fine'])
        with patch.object(store,'now',return_value=start):
            first=await self.saved('/control/ticks',tick,'controller-fixture-token')
            checked=await self.saved('/control/observe',dict(request_id='observer-recent',expected_seq=0,expected_epoch=epoch),'watcher-fixture-token')
        with patch.object(store,'now',return_value=start+timedelta(seconds=71)):
            opened=await self.saved('/control/observe',dict(request_id='observer-stopped',expected_seq=checked['seq'],expected_epoch=epoch),'watcher-fixture-token')
            row=opened['observations'][0]
            self.assertEqual((row['poll_state'],row['incident_state'],row['sequence']),('stale','open',first['seq']))
            self.assertEqual(opened['actor'],'watcher')
            self.assertEqual((await self.status())['observers'][0]['observations'][0]['incident_state'],'open')
            # A claim, a self-recovery attempt and a tick replay cannot close it.
            failure=dict(kind='runner_stale',target='controller',key='observer-acceptance-claim',expected_seq=0,
                expected_epoch=epoch,state='open',evidence=['I recovered'])
            claim=await self.saved('/control/failures',failure,'controller-fixture-token')
            self.assertEqual((await self.post('/control/failures',{**failure,'state':'recovered','expected_seq':claim['seq']},'controller-fixture-token')).status_code,409)
            self.assertEqual(await self.saved('/control/ticks',tick,'controller-fixture-token'),first)
            self.assertEqual((await self.status())['observers'][0]['observations'][0]['incident_state'],'open')
            resumed=await self.saved('/control/ticks',{**tick,'request_id':'observer-acceptance-resumed','expected_seq':first['seq']},'controller-fixture-token')
            self.assertEqual((await self.status())['observers'][0]['observations'][0]['incident_state'],'open')
            recovery=await self.saved('/control/observe',dict(request_id='observer-confirms',expected_seq=opened['seq'],expected_epoch=epoch),'watcher-fixture-token')
            self.assertEqual(recovery['observations'][0]['recovery_tick_sequence'],resumed['seq'])
            view=await self.status();self.assertEqual(view['observers'][0]['observations'][0]['incident_state'],'recovered')
            self.assertEqual(next(f for f in view['failures'] if f['key']==failure['key'])['state'],'open')
            page=await self.client.get('/api/hearth2/status/view',headers={'Authorization':'Bearer admin-test-token'})
            for label in ['Independent poll observations','Polling resumed','watcher','Last observer check','not worker health']:
                self.assertIn(label,page.text)
        for table in ['tasks','runs','claims','incidents','incident_attempts']:
            self.assertEqual(store.snapshot()[table],before[table])

    async def test_observer_role_is_bearer_only_narrow_and_payload_cannot_forge_evidence(self):
        store=self.memory.h2_runtime.store
        epoch=store.control_snapshot()['restore_epoch'];data=dict(request_id='auth-check',expected_seq=0,expected_epoch=epoch)
        before=store.snapshot()
        for token in ['admin-test-token','controller-fixture-token','codex-test-token']:
            self.assertEqual((await self.post('/control/observe',data,token)).status_code,403)
        for field,value in [('actor','watcher'),('observed_at','2099-01-01'),('state','recovered'),('expectations',{}),('evidence',['forged'])]:
            self.assertEqual((await self.post('/control/observe',{**data,field:value},'watcher-fixture-token')).status_code,400)
        for path,payload in [('/control/ticks',{}),('/control/failures',{}),('/projects',{'title':'denied'})]:
            self.assertEqual((await self.post(path,payload,'watcher-fixture-token')).status_code,403)
        cookie=self.memory.create_session('watcher','token','watcher-fixture-token');self.client.cookies.set(self.memory.SESSION_COOKIE,cookie)
        self.assertEqual((await self.client.post('/api/hearth2/control/observe',json=data)).status_code,403)
        self.client.cookies.clear()
        self.assertEqual(store.snapshot(),before)
        r=await self.client.get('/api/hearth2/control',headers={'Authorization':'Bearer watcher-fixture-token'})
        self.assertEqual(r.status_code,200,r.text)


class ObserverConfigurationTests(unittest.TestCase):
    def test_roles_disjoint_and_controller_bound_validated_before_database(self):
        for enabled,observer_ids,controllers in [(True,{'controller'},{'controller'}),(True,{'admin'},{'controller'}),
                (True,{'codex'},{'controller'}),(True,{'anonymous'},{'controller'}),
                (True,{'watcher'},{str(i) for i in range(129)}),(False,{'controller'},{'controller'})]:
            with self.subTest(enabled=enabled,observer_ids=observer_ids),tempfile.TemporaryDirectory() as path:
                runtime=Runtime(FakeApp(),enabled=enabled,data_dir=path,principal=lambda:'admin',typed_auth=lambda:None,
                    same_origin=lambda r:True,bearer_principal=lambda r:None,human_ids={'admin'},controller_ids=controllers,
                    worker_ids={'codex'},observer_ids=observer_ids,authenticated=True)
                if enabled:
                    with self.assertRaises(RuntimeError):runtime.initialize()
                else:runtime.initialize()
                self.assertFalse(Path(path,'hearth2.sqlite3').exists())
