"""Named-session credentials cannot become generic HM or MCP authority."""
import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from test import test_hearth2_delivery_acceptance as base


class SessionBoundaryTests(unittest.IsolatedAsyncioTestCase):
    setUpClass=classmethod(base.NamedSessionAcceptanceTests.setUpClass.__func__)
    tearDownClass=classmethod(base.NamedSessionAcceptanceTests.tearDownClass.__func__)
    asyncSetUp=base.NamedSessionAcceptanceTests.asyncSetUp
    asyncTearDown=base.NamedSessionAcceptanceTests.asyncTearDown
    post=base.NamedSessionAcceptanceTests.post
    saved=base.NamedSessionAcceptanceTests.saved
    get=base.NamedSessionAcceptanceTests.get
    notice=base.NamedSessionAcceptanceTests.notice
    test_receipt_control=base.NamedSessionAcceptanceTests.test_notice_reaches_intended_named_session_without_comprehension_or_completion

    def headers(self,token='session-a-fixture-token'):return {'Authorization':'Bearer '+token}

    async def test_other_memory_apis_and_methods_are_denied_without_writes(self):
        before=self.memory.h2_runtime.store.snapshot()
        for method,path,data in [('GET','/api/status',None),('GET','/api/recent',None),('GET','/api/taxonomy',None),
                ('GET','/api/drawer/not-real',None),('GET','/api/export',None),('GET','/api/tokens',None),
                ('GET','/api/work',None),('GET','/api/auth/status',None),('POST','/api/auth/logout',{}),
                ('POST','/api/coordination/answer',{}),('POST','/api/import',{}),
                ('POST','/api/hearth2/projects',{'title':'must not create'}),('GET','/',None)]:
            with self.subTest(method=method,path=path):
                r=await self.client.request(method,path,json=data,headers=self.headers())
                self.assertEqual(r.status_code,403,r.text)
                self.assertEqual(r.headers.get('cache-control'),'no-store')
        self.assertEqual(self.memory.h2_runtime.store.snapshot(),before)
        # Ordinary established agents and admin retain their legacy reads.
        for token in ['admin-test-token','codex-test-token']:
            self.assertEqual((await self.client.get('/api/status',headers=self.headers(token))).status_code,200)

    async def test_mcp_all_shapes_denied_before_dispatch_ordinary_agent_still_dispatches(self):
        calls=[]
        async def sentinel(scope,receive,send):
            calls.append(scope['path'])
            await send({'type':'http.response.start','status':200,'headers':[(b'content-type',b'application/json')]})
            await send({'type':'http.response.body','body':b'{"dispatched":true}'})
        mount=next(route for route in self.memory.app.routes if getattr(route,'path',None)=='')
        with patch.object(mount,'app',sentinel):
            frames=[{'jsonrpc':'2.0','id':1,'method':'initialize','params':{}},
                {'jsonrpc':'2.0','id':2,'method':'tools/list'},
                {'jsonrpc':'2.0','id':3,'method':'tools/call','params':{'name':'memory_add','arguments':{}}},
                [{'jsonrpc':'2.0','id':4,'method':'tools/list'}],{'jsonrpc':'2.0','method':'notifications/initialized'}]
            for frame in frames:
                for path in ['/mcp','/mcp/','/mcp/extra']:
                    r=await self.client.post(path,json=frame,headers=self.headers())
                    self.assertEqual(r.status_code,403,r.text)
            for method in ['GET','DELETE']:
                self.assertEqual((await self.client.request(method,'/mcp',headers=self.headers())).status_code,403)
            self.assertEqual(calls,[])
            r=await self.client.post('/mcp',json=frames[0],headers=self.headers('codex-test-token'))
            self.assertEqual(r.status_code,200,r.text);self.assertEqual(calls,['/mcp'])

    async def test_login_body_token_and_existing_cookie_cannot_expand_authority(self):
        before=dict(self.memory.SESSIONS)
        r=await self.client.post('/api/auth/login',json={'token':'  session-a-fixture-token  '})
        self.assertEqual(r.status_code,403,r.text);self.assertNotIn('set-cookie',r.headers)
        self.assertEqual(self.memory.SESSIONS,before)
        cookie=self.memory.create_session('claude-session-a','token','session-a-fixture-token')
        self.client.cookies.set(self.memory.SESSION_COOKIE,cookie)
        for headers in [{},self.headers('admin-test-token')]:
            self.assertEqual((await self.client.get('/api/status',headers=headers)).status_code,403)
            self.assertEqual((await self.client.get('/api/hearth2/session/notices',headers=headers)).status_code,403)
        self.client.cookies.clear()
        admin_cookie=self.memory.create_session('admin','token','admin-test-token')
        self.client.cookies.set(self.memory.SESSION_COOKIE,admin_cookie)
        self.assertEqual((await self.client.get('/api/status',headers=self.headers())).status_code,403)
        self.assertEqual((await self.client.get('/api/hearth2/session/notices',headers=self.headers())).status_code,200)
        # Header spelling/whitespace cannot borrow the admin browser cookie.
        self.assertEqual((await self.client.get('/api/status',headers={'Authorization':'bEaReR session-a-fixture-token '})).status_code,403)
        self.client.cookies.clear()

    async def test_duplicate_credential_aliases_never_select_broader_identity(self):
        tokens=self.memory.load_tokens()
        try:
            self.memory.save_tokens({'ordinary-alias':'session-a-fixture-token',**tokens})
            for path in ['/api/status','/api/hearth2/session/notices']:
                self.assertEqual((await self.client.get(path,headers=self.headers())).status_code,403)
            self.memory.save_tokens(tokens)
            with patch.object(self.memory,'ADMIN_TOKEN','session-a-fixture-token'):
                self.assertEqual((await self.client.get('/api/status',headers=self.headers())).status_code,403)
            with patch.object(self.memory.reviewer_store,'owns_credential',return_value=True):
                self.assertEqual((await self.client.get('/api/status',headers=self.headers())).status_code,403)
        finally:self.memory.save_tokens(tokens)

    async def test_disabled_uninitialized_and_invalid_policy_never_fall_back_to_generic_auth(self):
        runtime=self.memory.h2_runtime
        for enabled,initialized,status in [(False,False,409),(True,False,503)]:
            with patch.object(runtime,'enabled',enabled),patch.object(runtime,'initialized',initialized),patch.object(runtime,'notice_sessions',{}):
                self.assertEqual((await self.client.get('/api/status',headers=self.headers())).status_code,403)
                self.assertEqual((await self.client.get('/api/hearth2/session/notices',headers=self.headers())).status_code,status)
        with patch.object(runtime,'enabled',False),patch.object(runtime,'notice_sessions',{}),patch.object(runtime,'notice_sessions_raw','{bad'):
            self.assertEqual((await self.client.get('/api/status',headers=self.headers())).status_code,503)

    async def test_rotation_revocation_and_in_process_unenrollment_keep_boundary(self):
        runtime=self.memory.h2_runtime;tokens=self.memory.load_tokens()
        cookie=self.memory.create_session('claude-session-a','token','session-a-fixture-token')
        try:
            self.memory.save_tokens({**tokens,'claude-session-a':'rotated-session-fixture-token'})
            self.assertEqual((await self.client.get('/api/status',headers=self.headers())).status_code,401)
            self.assertEqual((await self.client.get('/api/status',headers=self.headers('rotated-session-fixture-token'))).status_code,403)
            self.assertEqual((await self.client.get('/api/hearth2/session/notices',headers=self.headers('rotated-session-fixture-token'))).status_code,200)
            self.client.cookies.set(self.memory.SESSION_COOKIE,cookie)
            self.assertEqual((await self.client.get('/api/status')).status_code,401);self.client.cookies.clear()
            with patch.object(runtime,'notice_sessions_raw',None):
                self.assertEqual((await self.client.get('/api/status',headers=self.headers('rotated-session-fixture-token'))).status_code,403)
            self.memory.save_tokens({key:value for key,value in tokens.items() if key!='claude-session-a'})
            self.assertEqual((await self.client.get('/api/status',headers=self.headers())).status_code,401)
        finally:self.memory.save_tokens(tokens);self.client.cookies.clear()

    async def test_reviewer_and_duplicate_header_representations_cannot_hide_session_scope(self):
        for headers in [[('Authorization','Bearer admin-test-token'),('Authorization','Bearer session-a-fixture-token')],
                [('Authorization','Bearer session-a-fixture-token'),('Authorization','Bearer admin-test-token')]]:
            self.assertEqual((await self.client.get('/api/status',headers=headers)).status_code,403)
        with tempfile.TemporaryDirectory() as directory:
            store=self.memory._reviewers.ReviewerStore(Path(directory)/'reviewers.sqlite3')
            store.provision('separate','separate-reviewer-secret','full')
            reviewer_cookie=store.session(store.authenticate('separate-reviewer-secret'))
            with patch.object(self.memory,'reviewer_store',store):
                self.client.cookies.set(self.memory.SESSION_COOKIE,reviewer_cookie)
                self.assertEqual((await self.client.get('/api/status')).status_code,200)
                self.assertEqual((await self.client.get('/api/status',headers=self.headers())).status_code,403)
                self.client.cookies.clear()
                named_cookie=self.memory.create_session('claude-session-a','token','session-a-fixture-token')
                self.client.cookies.set(self.memory.SESSION_COOKIE,named_cookie)
                self.assertEqual((await self.client.get('/api/status',headers=self.headers('separate-reviewer-secret'))).status_code,403)
                self.client.cookies.clear()
                store.provision('collision','session-a-fixture-token','full')
                colliding_cookie=store.session(store.authenticate('session-a-fixture-token'))
                self.client.cookies.set(self.memory.SESSION_COOKIE,colliding_cookie)
                self.assertEqual((await self.client.get('/api/status')).status_code,403)
                self.client.cookies.clear()

    async def test_opaque_credential_whitespace_cannot_escape_scope(self):
        tokens=self.memory.load_tokens()
        try:
            for credential in [' session-a-fixture-token','session-a-fixture-token ',' session-a-fixture-token ']:
                self.memory.save_tokens({**tokens,'claude-session-a':credential})
                with self.subTest(credential=repr(credential)):
                    self.assertEqual((await self.client.get('/api/status',headers=self.headers(credential))).status_code,403)
                    self.assertEqual((await self.client.get('/api/hearth2/session/notices',headers=self.headers(credential))).status_code,200)
        finally:self.memory.save_tokens(tokens)

    async def test_login_checks_opaque_credential_before_generic_trimming(self):
        tokens=self.memory.load_tokens()
        try:
            self.memory.save_tokens({**tokens,'claude-session-a':' session-a-fixture-token',
                'ordinary-trimmed-alias':'session-a-fixture-token'})
            before=dict(self.memory.SESSIONS)
            r=await self.client.post('/api/auth/login',json={'token':' session-a-fixture-token'})
            self.assertEqual(r.status_code,403,r.text)
            self.assertNotIn('set-cookie',r.headers);self.assertEqual(self.memory.SESSIONS,before)
        finally:self.memory.save_tokens(tokens);self.client.cookies.clear()

    async def test_exact_route_method_matching_and_encoded_paths(self):
        for method,path in [('POST','/api/hearth2/session/notices'),('GET','/api/hearth2/notices/x/receive'),
                ('POST','/api/hearth2/notices/x/receive/extra'),('GET','/api/hearth2/session/notices/'),
                ('GET','/%61pi/status'),('GET','/api/hearth2/session/notices/../status')]:
            self.assertEqual((await self.client.request(method,path,json={},headers=self.headers())).status_code,403)
        self.assertEqual((await self.client.get('/api/hearth2/%73ession/notices',headers=self.headers())).status_code,200)
