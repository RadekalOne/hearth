"""Fresh application instances over one temporary durable service directory."""
import importlib.util
import json
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
import httpx
from test import test_hearth2_delivery_acceptance as base


class SessionLifecycleAcceptanceTests(unittest.IsolatedAsyncioTestCase):
    setUpClass=classmethod(base.NamedSessionAcceptanceTests.setUpClass.__func__)
    tearDownClass=classmethod(base.NamedSessionAcceptanceTests.tearDownClass.__func__)
    asyncSetUp=base.NamedSessionAcceptanceTests.asyncSetUp
    asyncTearDown=base.NamedSessionAcceptanceTests.asyncTearDown
    post=base.NamedSessionAcceptanceTests.post
    saved=base.NamedSessionAcceptanceTests.saved
    get=base.NamedSessionAcceptanceTests.get
    notice=base.NamedSessionAcceptanceTests.notice

    async def restart(self, raw, enabled='true'):
        await self.client.aclose()
        spec=importlib.util.spec_from_file_location('hearth_lifecycle_restart',Path(self.memory.__file__))
        memory=importlib.util.module_from_spec(spec)
        with patch.dict('os.environ',{'HEARTH2_NOTICE_SESSIONS':raw,'HEARTH2_ENABLED':enabled}):
            spec.loader.exec_module(memory)
        memory.h2_runtime.initialize()
        memory._notice_session_policy()  # Same ordering as the actual startup lifespan.
        self.memory=memory
        self.client=httpx.AsyncClient(transport=httpx.ASGITransport(app=memory.app),base_url='https://hearth-memory.test')

    async def test_restart_receipt_and_terminal_credential_lifecycle(self):
        original=self.memory.h2_runtime.notice_sessions_raw
        self.memory._notice_session_policy()
        tokens=self.memory.load_tokens()
        Path(self.memory.TOKENS_PATH).write_text('{partial')
        try:
            self.assertEqual((await self.client.get('/api/hearth2/session/notices',headers={'Authorization':'Bearer session-a-fixture-token'})).status_code,503)
        finally:
            self.memory.save_tokens(tokens)
        self.assertEqual((await self.client.get('/api/hearth2/session/notices',headers={'Authorization':'Bearer session-a-fixture-token'})).status_code,200)
        task,notice=await self.notice()
        before=self.memory.h2_runtime.store.snapshot()
        epoch=self.memory.h2_runtime.store.control_snapshot()['restore_epoch']
        path='/notices/'+notice['id']
        offer=await self.saved(path+'/receive',{'request_id':'restart-receipt','expected_epoch':epoch},'session-a-fixture-token')
        body={k:offer[k] for k in ('delivery_id','notice_digest')};body['expected_epoch']=epoch
        receipt=await self.saved(path+'/acknowledge',body,'session-a-fixture-token')
        await self.restart(original)
        self.assertEqual(await self.saved(path+'/acknowledge',body,'session-a-fixture-token'),receipt)
        self.assertEqual(len([r for r in self.memory.h2_runtime.store.snapshot()['audit_events'] if r['action']=='notice_receipt']),1)
        for token in ['session-a-fixture-token','controller-fixture-token','claude-fixture-token']:
            self.assertEqual((await self.post('/sessions/claude-a/revoke',{},token)).status_code,403)
        self.assertEqual((await self.saved('/sessions/claude-a/revoke',{}))['revoked'],1)
        policy=json.loads(original)
        policy['claude-b']['expires_at']=(datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat()
        await self.restart(json.dumps(policy))
        await self.restart(original)  # Removing expiry does not renew this credential.
        for token in ['session-a-fixture-token','session-b-fixture-token']:
            self.assertEqual((await self.client.get('/api/hearth2/session/notices',headers={'Authorization':'Bearer '+token})).status_code,403)
            self.assertEqual((await self.post(path+'/acknowledge',body,token)).status_code,403)
        self.memory.save_tokens({**self.memory.load_tokens(),'claude-session-a':'replacement-session-token'})
        self.assertEqual((await self.client.get('/api/hearth2/session/notices',headers={'Authorization':'Bearer replacement-session-token'})).status_code,200)
        # Remove enrollment, leave the old credential under a generic alias, disable H2.
        self.memory.save_tokens({**self.memory.load_tokens(),'ordinary-alias':'replacement-session-token'})
        await self.restart('{}',enabled='false')
        for token in ['session-a-fixture-token','session-b-fixture-token','replacement-session-token']:
            headers={'Authorization':'Bearer '+token}
            for endpoint in ['/api/status','/api/hearth2/session/notices','/mcp']:
                self.assertEqual((await self.client.get(endpoint,headers=headers)).status_code,403)
            self.assertEqual((await self.client.post('/api/auth/login',json={'token':token})).status_code,403)
        cookie=self.memory.create_session('ordinary-alias','token','replacement-session-token')
        self.client.cookies.set(self.memory.SESSION_COOKIE,cookie)
        self.assertEqual((await self.client.get('/api/status')).status_code,403)
        self.client.cookies.clear()
        reviewers=self.memory.reviewer_store
        reviewers.provision('retired-alias','replacement-session-token','full')
        cookie=reviewers.session(reviewers.authenticate('replacement-session-token'))
        self.client.cookies.set(self.memory.SESSION_COOKIE,cookie)
        self.assertEqual((await self.client.get('/api/status')).status_code,403)
        self.client.cookies.clear()
        await self.restart(original)
        self.assertEqual((await self.client.get('/api/hearth2/session/notices',headers={'Authorization':'Bearer session-a-fixture-token'})).status_code,403)
        status=await self.get('/status')
        self.assertEqual(next(n for n in status['notices'] if n['id']==notice['id'])['understanding_state'],'unknown')
        self.assertEqual(next(t for t in status['tasks'] if t['id']==task['id'])['state'],'running')
        after=self.memory.h2_runtime.store.snapshot()
        for table in ('tasks','runs','claims','notices','incidents','incident_attempts'):
            self.assertEqual(after[table],before[table])
