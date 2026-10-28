"""Authenticated route wiring against the actual memory-service application."""
import os
import unittest
from pathlib import Path
from unittest.mock import patch
from test import test_dashboard_auth as base


class Hearth2APITests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.environment=patch.dict(os.environ,{'HEARTH2_ENABLED':'true','HEARTH2_HUMAN_IDS':'admin',
                                              'HEARTH2_CONTROLLER_IDS':'controller','HEARTH2_WORKER_IDS':'codex,claude'})
        cls.environment.start()
        base.DashboardAuthTests.setUpClass.__func__(cls)
        cls.memory.h2_runtime.initialize()
        tokens=cls.memory.load_tokens();tokens['controller']='controller-fixture-token';tokens['claude']='claude-fixture-token';cls.memory.save_tokens(tokens)

    @classmethod
    def tearDownClass(cls):
        base.DashboardAuthTests.tearDownClass.__func__(cls)
        cls.environment.stop()

    async def asyncSetUp(self):await base.DashboardAuthTests.asyncSetUp(self)
    async def asyncTearDown(self):await base.DashboardAuthTests.asyncTearDown(self)

    async def post(self,path,data,token='admin-test-token',**headers):
        return await self.client.post('/api/hearth2'+path,json=data,headers={'Authorization':'Bearer '+token,**headers})

    async def test_management_auth_actor_spoofing_and_csrf(self):
        self.assertEqual((await self.client.get('/api/hearth2')).status_code,401)
        self.assertEqual((await self.post('/projects',{'title':'Denied'},'codex-test-token')).status_code,403)
        self.assertEqual((await self.post('/projects',{'title':'Denied','actor':'admin'})).status_code,400)
        self.assertEqual((await self.post('/projects',{'title':'Denied'},Origin='https://evil.test')).status_code,403)
        created=await self.post('/projects',{'title':'Trial'})
        self.assertEqual(created.status_code,200,created.text)
        self.assertEqual(created.json()['title'],'Trial')
        self.assertEqual((await self.client.get('/api/hearth2',headers={'Authorization':'Bearer codex-test-token'})).status_code,403)

    async def test_disabled_does_not_open_or_create_store(self):
        before=Path(self.memory.DATA_DIR,'hearth2.sqlite3').read_bytes()
        with patch.object(self.memory.h2_runtime,'enabled',False):
            self.assertEqual((await self.post('/projects',{'title':'disabled'})).status_code,409)
        self.assertEqual(Path(self.memory.DATA_DIR,'hearth2.sqlite3').read_bytes(),before)

    async def test_export_is_management_only_and_restore_has_no_http_route(self):
        self.assertEqual((await self.client.get('/api/hearth2/export',headers={'Authorization':'Bearer codex-test-token'})).status_code,403)
        exported=await self.client.get('/api/hearth2/export',headers={'Authorization':'Bearer admin-test-token'})
        self.assertEqual(exported.status_code,200,exported.text)
        self.assertEqual(exported.json()['manifest']['format'],'hearth2-work-record')
        self.assertEqual((await self.post('/restore',{})).status_code,404)
        # The legacy export remains drawer JSONL; no operational envelope added.
        original=await self.client.get('/api/export',headers={'Authorization':'Bearer admin-test-token'})
        self.assertEqual(original.status_code,200)
        self.assertIn('ndjson',original.headers['content-type'])

    async def test_cookie_cannot_impersonate_controller(self):
        cookie=self.memory.create_session('controller','token','controller-fixture-token')
        self.client.cookies.set(self.memory.SESSION_COOKIE,cookie)
        r=await self.client.post('/api/hearth2/projects',json={'title':'forged controller'})
        self.assertEqual(r.status_code,403)

    async def test_full_controller_receipt_and_independent_review_flow(self):
        from datetime import datetime,timedelta,timezone
        p=(await self.post('/projects',{'title':'Lifecycle'})).json()
        handoff={'recipient':'codex','ask':'Write fixture','done_means':'Fixture checked',
                 'inputs':['drawer_fixture'],'return':'claude reviews'}
        plan_response=await self.post('/projects/'+p['id']+'/plans',{'content_ref':'approved-fixture',
                    'actions':{'write':{**handoff,'requires':{}}}})
        self.assertEqual(plan_response.status_code,200,plan_response.text);plan=plan_response.json()
        decision=await self.post('/decisions',{'plan_id':plan['id'],'intended_subject':'admin',
                    'expires_at':(datetime.now(timezone.utc)+timedelta(days=1)).isoformat()})
        self.assertEqual(decision.status_code,200,decision.text)
        self.assertEqual((await self.post('/decisions/'+decision.json()['id']+'/actions',
                    {'expected_revision':1,'action':'approve','source':'human-approval'})).status_code,200)
        for agent,model,family in [('codex','gpt-6.1-sol','openai'),('claude','claude','anthropic')]:
            self.assertEqual((await self.post('/roles/'+agent,{'model':model,'family':family,'role':'senior'})).status_code,200)
        task=await self.post('/tasks',{'project_id':p['id'],'plan_id':plan['id'],'action_id':'write',**handoff})
        self.assertEqual(task.status_code,200,task.text);task=task.json()
        c=await self.post('/tasks/'+task['id']+'/claim',{'expected_revision':1,'request_id':'api-fixture'},'controller-fixture-token')
        self.assertEqual(c.status_code,200,c.text);claim=c.json()
        closeout={'task':task['id'],'attempt':1,'status':'done','produced':'fixture','changed':'fixture',
                  'unblocked':'none','memory-used':['drawer_fixture'],'checks-run':[{'name':'check','passed':True,'evidence':'test'}],
                  'next':'review'}
        receipt={'ended_at':datetime.now(timezone.utc).isoformat(),'exit_status':0,'closeout':closeout,
                 'containment_state':'verified_empty','termination_evidence':['controller-verified-empty'],
                 'usage':{'state':'unknown','units':None}}
        r=await self.post('/runs/'+claim['run_id']+'/receipt',{'claim':claim,'receipt':receipt},'controller-fixture-token')
        self.assertEqual(r.status_code,200,r.text)
        review=await self.post('/tasks/'+task['id']+'/reviews',{'expected_revision':3,'verdict':'pass','evidence':['independent-check']},'claude-fixture-token')
        self.assertEqual(review.status_code,200,review.text)
        accepted=await self.post('/tasks/'+task['id']+'/acceptance',{'expected_revision':4,'evidence':['human-acceptance']})
        self.assertEqual(accepted.status_code,200,accepted.text)
        self.assertEqual(accepted.json()['state'],'accepted')
