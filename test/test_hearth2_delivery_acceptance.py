"""Authenticated named-session receipt acceptance; temporary fixture identities only."""
import hashlib,json,os,tempfile,unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path
from unittest.mock import patch
from test import test_hearth2_api as api
from test.test_hearth2_timing_config import FakeApp
from hearth2.api import Runtime


class NamedSessionAcceptanceTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.sessions_environment=patch.dict(os.environ,{'HEARTH2_NOTICE_SESSIONS':json.dumps({
            'claude-a':{'principal_id':'claude-session-a','recipient':'claude'},
            'claude-b':{'principal_id':'claude-session-b','recipient':'claude'}})})
        cls.sessions_environment.start();api.Hearth2APITests.setUpClass.__func__(cls)
        tokens=cls.memory.load_tokens();tokens['claude-session-a']='session-a-fixture-token';tokens['claude-session-b']='session-b-fixture-token';cls.memory.save_tokens(tokens)

    @classmethod
    def tearDownClass(cls):
        api.Hearth2APITests.tearDownClass.__func__(cls);cls.sessions_environment.stop()

    asyncSetUp=api.Hearth2APITests.asyncSetUp
    asyncTearDown=api.Hearth2APITests.asyncTearDown
    post=api.Hearth2APITests.post

    async def saved(self,path,data,token='admin-test-token'):
        r=await self.post(path,data,token);self.assertEqual(r.status_code,200,r.text);return r.json()

    async def get(self,path,token='admin-test-token'):
        r=await self.client.get('/api/hearth2'+path,headers={'Authorization':'Bearer '+token})
        self.assertEqual(r.status_code,200,r.text);return r.json()

    async def notice(self):
        project=await self.saved('/projects',{'title':'Named-session handoff'})
        handoff={'recipient':'codex','ask':'Prepare a handoff','done_means':'Independently reviewed handoff',
                 'inputs':['synthetic-brief'],'return':'Independent review'}
        plan=await self.saved('/projects/'+project['id']+'/plans',{'content_ref':'synthetic-approved-plan','actions':{'draft':{**handoff,'requires':{}}}})
        decision=await self.saved('/decisions',{'plan_id':plan['id'],'intended_subject':'admin','expires_at':(datetime.now(timezone.utc)+timedelta(days=1)).isoformat()})
        await self.saved('/decisions/'+decision['id']+'/actions',{'expected_revision':1,'action':'approve','source':'synthetic-human-approval'})
        await self.saved('/roles/codex',{'model':'gpt-6.1-sol','family':'openai','role':'senior'})
        task=await self.saved('/tasks',{'project_id':project['id'],'plan_id':plan['id'],'action_id':'draft',**handoff})
        claim=await self.saved('/tasks/'+task['id']+'/claim',{'expected_revision':1,'request_id':'named-session-claim-'+task['id']},'controller-fixture-token')
        notice=await self.saved('/notices',{'claim':claim,'notice':{'task_id':task['id'],'recipient':'claude',
            'recipient_session':'claude-a','kind':'interface_changed','reference':'Notice body for the intended Claude session'}},'controller-fixture-token')
        return task,notice

    async def test_notice_reaches_intended_named_session_without_comprehension_or_completion(self):
        task,notice=await self.notice();store=self.memory.h2_runtime.store;before=store.snapshot()
        inbox=await self.get('/session/notices','session-a-fixture-token')
        self.assertIn(notice['id'],[n['id'] for n in inbox['notices']])
        other=await self.get('/session/notices','session-b-fixture-token');self.assertNotIn(notice['id'],[n['id'] for n in other['notices']])
        epoch=inbox['restore_epoch'];path='/notices/'+notice['id']
        self.assertEqual((await self.post(path+'/receive',{'request_id':'wrong-session','expected_epoch':epoch},'session-b-fixture-token')).status_code,409)
        offer=await self.saved(path+'/receive',{'request_id':'intended-receive','expected_epoch':epoch},'session-a-fixture-token')
        self.assertEqual(offer['notice']['reference'],'Notice body for the intended Claude session')
        # Session checks the exact received body, rather than trusting an opaque digest.
        canonical=json.dumps(offer['notice'],sort_keys=True,separators=(',',':'),allow_nan=False).encode()
        self.assertEqual(hashlib.sha256(canonical).hexdigest(),offer['notice_digest'])
        view=await self.get('/status');row=next(n for n in view['notices'] if n['id']==notice['id'])
        self.assertEqual(row['delivery_state'],'unconfirmed')
        body={'delivery_id':offer['delivery_id'],'notice_digest':offer['notice_digest'],'expected_epoch':epoch}
        self.assertEqual((await self.post(path+'/acknowledge',body,'session-b-fixture-token')).status_code,409)
        receipt=await self.saved(path+'/acknowledge',body,'session-a-fixture-token')
        self.assertEqual(receipt['actor'],'claude-session-a')
        self.assertEqual(await self.saved(path+'/acknowledge',body,'session-a-fixture-token'),receipt)
        view=await self.get('/status');row=next(n for n in view['notices'] if n['id']==notice['id'])
        self.assertEqual((row['intended_session'],row['delivery_state'],row['acknowledgement_state'],row['understanding_state']),('claude-a','received','receipt_recorded','unknown'))
        self.assertEqual(row['acknowledged_at'],receipt['at'])
        self.assertEqual(next(t for t in view['tasks'] if t['id']==task['id'])['state'],'running')
        page=await self.client.get('/api/hearth2/status/view',headers={'Authorization':'Bearer admin-test-token'})
        for label in ['Receipt recorded','claude-a','claude-session-a','Understanding remains unknown','does not complete the task']:
            self.assertIn(label,page.text)
        for table in ['tasks','runs','claims','notices','incidents','incident_attempts']:
            self.assertEqual(store.snapshot()[table],before[table])
        after=store.snapshot();await self.get('/status');await self.get('/session/notices','session-a-fixture-token')
        self.assertEqual(store.snapshot(),after)

    async def test_receipt_identity_is_bearer_only_narrow_and_not_payload_supplied(self):
        store=self.memory.h2_runtime.store;before=store.snapshot();epoch=store.control_snapshot()['restore_epoch']
        for token in ['admin-test-token','controller-fixture-token','claude-fixture-token']:
            self.assertEqual((await self.post('/notices/missing/receive',{'request_id':'read','expected_epoch':epoch},token)).status_code,403)
        for field,value in [('session_id','claude-b'),('actor','claude-session-b'),('understood',True),('completed',True),('acknowledged_at','2099')]:
            self.assertEqual((await self.post('/notices/missing/acknowledge',{field:value},'session-a-fixture-token')).status_code,400)
        for path,payload in [('/control/ticks',{}),('/control/observe',{}),('/projects',{'title':'denied'})]:
            self.assertEqual((await self.post(path,payload,'session-a-fixture-token')).status_code,403)
        cookie=self.memory.create_session('claude-session-a','token','session-a-fixture-token');self.client.cookies.set(self.memory.SESSION_COOKIE,cookie)
        self.assertEqual((await self.client.post('/api/hearth2/notices/missing/receive',json={'request_id':'read','expected_epoch':epoch})).status_code,403)
        self.client.cookies.clear();self.assertEqual(store.snapshot(),before)


class NoticeSessionConfigTests(unittest.TestCase):
    def test_invalid_enrollment_fails_before_database_but_disabled_is_inert(self):
        cases=['{bad','{"a":{},"a":{}}',json.dumps({'a':{'principal_id':'controller','recipient':'claude'}}),
            json.dumps({'a':{'principal_id':'anonymous','recipient':'claude'}}),
            json.dumps({'a':{'principal_id':'session-a','recipient':'not-configured'}}),
            json.dumps({'a':{'principal_id':'session-a','recipient':'claude'},'b':{'principal_id':'session-a','recipient':'claude'}}),
            json.dumps({'a':{'principal_id':'session-a','recipient':'claude','understood':True}}),
            json.dumps({str(i):{'principal_id':'session-'+str(i),'recipient':'claude'} for i in range(129)})]
        cases += [json.dumps({'a':{'principal_id':subject,'recipient':'claude'}}) for subject in ['admin','claude','watcher']]
        for raw in cases:
            for enabled in [True,False]:
                with self.subTest(raw=raw[:65],enabled=enabled),tempfile.TemporaryDirectory() as path:
                    runtime=Runtime(FakeApp(),enabled=enabled,data_dir=path,principal=lambda:'admin',typed_auth=lambda:None,
                        same_origin=lambda r:True,bearer_principal=lambda r:None,human_ids={'admin'},controller_ids={'controller'},
                        worker_ids={'claude'},observer_ids={'watcher'},authenticated=True,notice_sessions=raw)
                    if enabled:
                        with self.assertRaises(RuntimeError):runtime.initialize()
                    else:runtime.initialize()
                    self.assertFalse(Path(path,'hearth2.sqlite3').exists())
