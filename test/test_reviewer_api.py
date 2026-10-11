import tempfile
import json
from pathlib import Path
from unittest.mock import patch
from test import test_dashboard_auth as auth


class ReviewerAPI(auth.DashboardAuthTests):
    async def test_full_reviewer_export_bearer_and_session_preserve_write_denials(self):
        fixture={'ids':['export-fixture'], 'documents':['fixture content'],
                 'metadatas':[{'wing':'hearth','room':'lessons','record_class':'knowledge'}]}
        with patch.object(self.memory.drawers,'get',return_value=fixture):
            response=await self.client.get('/api/export',headers={'Authorization':'Bearer reviewer-fixture-secret'})
            self.assertEqual(response.status_code,200,response.text)
            self.assertEqual(json.loads(response.text)['content'],'fixture content')
            self.assertIn('application/x-ndjson',response.headers['content-type'])
            await self.client.post('/api/auth/login',json={'token':'reviewer-fixture-secret'})
            response=await self.client.get('/api/export')
            self.assertEqual(response.status_code,200,response.text)
            self.assertEqual(json.loads(response.text)['drawer_id'],'export-fixture')
            self.assertEqual((await self.client.get('/api/export',headers={'Authorization':'Bearer codex-test-token'})).status_code,403)
            self.assertEqual((await self.client.get('/api/export',headers={'Authorization':'Bearer admin-test-token'})).status_code,200)
            for path in ('/api/import','/api/tokens'):
                self.assertEqual((await self.client.post(path,json={})).status_code,403)
            self.memory.reviewer_store.revoke('fixture',actor='admin')
            self.assertEqual((await self.client.get('/api/export')).status_code,401)
            self.assertEqual((await self.client.get('/api/export',headers={'Authorization':'Bearer reviewer-fixture-secret'})).status_code,401)

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.temp=tempfile.TemporaryDirectory()
        self.old=self.memory.reviewer_store
        self.memory.reviewer_store=self.memory._reviewers.ReviewerStore(Path(self.temp.name)/'reviewers.sqlite3')
        self.memory.reviewer_store.provision('fixture','reviewer-fixture-secret','full',reserved=self.memory.load_tokens())

    async def asyncTearDown(self):
        self.memory.reviewer_store=self.old
        self.temp.cleanup()
        await super().asyncTearDown()

    async def test_reviewer_login_header_and_cross_worker_revoke(self):
        result=await self.client.post('/api/auth/login',json={'token':'reviewer-fixture-secret'})
        self.assertEqual(result.status_code,200,result.text)
        cookie=self.client.cookies.get('hearth_session')
        status=(await self.client.get('/api/auth/status')).json()
        self.assertEqual(status['role'],'reviewer')
        self.assertEqual(status['principal'],'reviewer:fixture')
        self.assertIn('Max-Age=86400',result.headers['set-cookie'])
        other=self.memory._reviewers.ReviewerStore(self.memory.reviewer_store.path)
        other.revoke('fixture',actor='admin')
        self.assertIsNone(other.session_context(cookie))
        self.assertEqual((await self.client.get('/api/status')).status_code,401)
        self.assertEqual((await self.client.get('/api/status',headers={'Authorization':'Bearer reviewer-fixture-secret'})).status_code,401)

    async def test_all_registered_mutations_and_admin_reads_are_denied(self):
        header={'Authorization':'Bearer reviewer-fixture-secret'}
        for route in self.memory.app.routes:
            path=getattr(route,'path','')
            if not path.startswith('/api/'):continue
            for method in getattr(route,'methods',set()):
                if self.memory._reviewers.rest_allowed(method,path):continue
                actual=path.replace('{agent}','codex').replace('{task_id}','fixture').replace('{project_id}','fixture').replace('{name}','fixture')
                response=await self.client.request(method,actual,headers=header,json={'anything':'irrelevant'})
                self.assertEqual(response.status_code,403,(method,path,response.text))
        self.assertEqual((await self.client.post('/api/inbox/acknowledgement',headers=header,json={})).status_code,403)
        self.assertEqual((await self.client.get('/api/future-unknown-read',headers=header)).status_code,403)
        self.assertEqual((await self.client.get('/api/taxonomy',headers=header)).status_code,200)

    async def test_invalid_mcp_bearer_cannot_borrow_reviewer_cookie(self):
        await self.client.post("/api/auth/login",json={"token":"reviewer-fixture-secret"})
        response=await self.client.post("/mcp",headers={"Authorization":"Bearer totally-invalid"},json={"jsonrpc":"2.0","id":1,"method":"initialize","params":{}})
        self.assertEqual(response.status_code,401)

    async def test_revoked_reviewer_credential_cannot_fall_back_to_legacy_admin(self):
        self.memory.reviewer_store.provision("collision-fixture","admin-test-token","full")
        self.memory.reviewer_store.revoke("collision-fixture",actor="admin")
        response=await self.client.get("/api/tokens",headers={"Authorization":"Bearer admin-test-token"})
        self.assertEqual(response.status_code,401)

    async def test_mcp_default_deny_every_write_unknown_and_resource(self):
        header={'Authorization':'Bearer reviewer-fixture-secret'}
        tools=await self.memory.mcp.list_tools()
        for tool in tools:
            if tool.name in self.memory._reviewers.READ_TOOLS:continue
            result=await self.client.post('/mcp',headers=header,json={'jsonrpc':'2.0','id':1,'method':'tools/call','params':{'name':tool.name,'arguments':{}}})
            self.assertEqual(result.status_code,403,(tool.name,result.text))
        for method,params in [('tools/call',{'name':'future_read'}),('resources/read',{'uri':'hearth://future'}),('prompts/get',{'name':'unknown'})]:
            self.assertEqual((await self.client.post('/mcp',headers=header,json={'jsonrpc':'2.0','id':1,'method':method,'params':params})).status_code,403)

    async def test_account_and_audit_require_configured_human_browser_session(self):
        for token in ['admin-test-token','codex-test-token','reviewer-fixture-secret']:
            self.assertEqual((await self.client.get('/api/reviewers/audit',headers={'Authorization':'Bearer '+token})).status_code,403)
        await self.client.post('/api/auth/login',json={'token':'admin-test-token'})
        self.assertEqual((await self.client.get('/api/reviewers/audit')).status_code,200)
        self.assertEqual((await self.client.post('/api/reviewers/fixture/revoke',json={})).status_code,200)
        self.assertEqual((await self.client.get('/api/reviewers/accounts')).json()['accounts'][0]['enabled'],0)

    async def test_matrix_administration_requires_explicit_human_configuration(self):
        with patch.object(self.memory.httpx,"AsyncClient",auth._MatrixClient):
            result=await self.client.post("/api/auth/login",json={"username":"rad","password":"correct"})
        self.assertEqual(result.status_code,200)
        with patch.object(self.memory,"HUMAN_IDS",set()):
            self.assertEqual((await self.client.get("/api/reviewers/audit")).status_code,403)
        with patch.object(self.memory,"HUMAN_IDS",{"rad"}):
            self.assertEqual((await self.client.get("/api/reviewers/audit")).status_code,200)

    async def test_provisioning_seam_rejects_existing_names_and_credentials(self):
        for name in ["codex","admin"]:
            with self.assertRaises(ValueError):self.memory.provision_reviewer(name,"fresh-fixture-secret","full")
        with self.assertRaises(ValueError):self.memory.provision_reviewer("external","codex-test-token","full")
        with self.assertRaises(ValueError):self.memory.provision_reviewer("external","fresh-fixture-secret",{"wing":"personal"})

    async def test_audit_normalization_and_no_matrix_or_memory_mutation(self):
        header={'Authorization':'Bearer reviewer-fixture-secret'}
        await self.client.get('/api/taxonomy?query=must-not-be-recorded',headers=header)
        rows=self.memory.reviewer_store.audit_rows()
        self.assertEqual(rows[-1]['route'],'/api/taxonomy')
        self.assertNotIn('must-not-be-recorded',str(rows))
        self.assertEqual((await self.client.post('/api/matrix/act',headers=header,json={'action':'reply'})).status_code,403)
        self.assertEqual(self.memory.reviewer_store.accounts()[0]['name'],'fixture')
        self.assertNotIn('reviewer:fixture',self.memory.load_tokens())
