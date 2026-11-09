"""Reusable session client through the actual authenticated temporary app."""
import tempfile,unittest
from pathlib import Path
import httpx
from test import test_hearth2_delivery_acceptance as base


class SessionClientAcceptanceTests(unittest.IsolatedAsyncioTestCase):
    setUpClass=classmethod(base.NamedSessionAcceptanceTests.setUpClass.__func__)
    tearDownClass=classmethod(base.NamedSessionAcceptanceTests.tearDownClass.__func__)
    asyncSetUp=base.NamedSessionAcceptanceTests.asyncSetUp
    asyncTearDown=base.NamedSessionAcceptanceTests.asyncTearDown
    post=base.NamedSessionAcceptanceTests.post
    saved=base.NamedSessionAcceptanceTests.saved
    get=base.NamedSessionAcceptanceTests.get
    notice=base.NamedSessionAcceptanceTests.notice

    def integration(self,path,target=None,transport=None):
        from hearth2.delivery import NoticeSession
        from hearth2.session_client import NamedSessionClient
        from hearth2.session_inbox import SessionInbox
        target=target or NoticeSession('claude-a','claude-session-a','claude')
        inbox=SessionInbox(path,'https://hearth-memory.test',target)
        return NamedSessionClient(origin='https://hearth-memory.test',target=target,
            token='session-a-fixture-token' if target.session_id=='claude-a' else 'session-b-fixture-token',
            inbox=inbox,transport=transport or httpx.ASGITransport(app=self.memory.app))

    async def test_client_durably_receives_and_acknowledges_without_understanding_or_completion(self):
        from hearth2.delivery import NoticeSession
        task,notice=await self.notice();store=self.memory.h2_runtime.store;before=store.snapshot()
        with tempfile.TemporaryDirectory() as directory:
            other=self.integration(Path(directory)/'other.db',NoticeSession('claude-b','claude-session-b','claude'))
            self.assertEqual((await other.poll_once()).receipts_recorded,0)
            client=self.integration(Path(directory)/'own.db')
            app_transport=httpx.ASGITransport(app=self.memory.app)
            class InspectBeforeAck(httpx.AsyncBaseTransport):
                async def handle_async_request(inner,request):
                    if request.url.path.endswith('/acknowledge'):
                        local=client.inbox.records()[0]
                        self.assertEqual(local['notice']['reference'],'Notice body for the intended Claude session')
                        self.assertEqual(local['delivery_state'],'stored_unconfirmed')
                        status=await self.get('/status')
                        self.assertEqual(next(n for n in status['notices'] if n['id']==notice['id'])['delivery_state'],'unconfirmed')
                    return await app_transport.handle_async_request(request)
            client.transport=InspectBeforeAck()
            result=await client.poll_once()
            self.assertEqual((result.stored,result.receipts_recorded,result.understanding_state),(1,1,'unknown'))
            rows=client.inbox.records()
            self.assertEqual((rows[0]['notice']['id'],rows[0]['delivery_state'],rows[0]['understanding_state']),(notice['id'],'receipt_recorded','unknown'))
            view=await self.get('/status');row=next(n for n in view['notices'] if n['id']==notice['id'])
            self.assertEqual((row['delivery_state'],row['understanding_state']),('received','unknown'))
            self.assertEqual(next(t for t in view['tasks'] if t['id']==task['id'])['state'],'running')
            restarted=self.integration(Path(directory)/'own.db')
            self.assertEqual((await restarted.poll_once()).receipts_recorded,0)
            self.assertEqual(restarted.inbox.records(),rows)
            for table in ['tasks','runs','claims','notices','incidents','incident_attempts']:
                self.assertEqual(store.snapshot()[table],before[table])

    async def lost_response(self,suffix):
        from hearth2.session_client import DeliveryClientError
        _,notice=await self.notice();app_transport=httpx.ASGITransport(app=self.memory.app);lost=False
        class LoseOnce(httpx.AsyncBaseTransport):
            async def handle_async_request(inner,request):
                nonlocal lost
                response=await app_transport.handle_async_request(request)
                if request.url.path.endswith(suffix) and not lost:
                    lost=True;await response.aread();raise httpx.ReadError('fixture response lost',request=request)
                return response
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'inbox.db';client=self.integration(path,transport=LoseOnce())
            with self.assertRaises(DeliveryClientError):await client.poll_once()
            self.assertEqual(len(client.inbox.records()),1 if suffix=='/acknowledge' else 0)
            first_status=next(n for n in (await self.get('/status'))['notices'] if n['id']==notice['id'])
            self.assertEqual(first_status['delivery_state'],'received' if suffix=='/acknowledge' else 'unconfirmed')
            restarted=self.integration(path);result=await restarted.poll_once()
            self.assertEqual(result.receipts_recorded,1)
            record=restarted.inbox.records()[0];self.assertEqual(record['understanding_state'],'unknown')
            if suffix=='/acknowledge':self.assertEqual(record['receipt']['at'],first_status['acknowledged_at'])
            with self.memory.h2_runtime.store.transaction() as db:
                self.assertEqual(db.execute("SELECT COUNT(*) FROM audit_events WHERE entity_id=? AND action='notice_offered'",(notice['id'],)).fetchone()[0],1)
                self.assertEqual(db.execute("SELECT COUNT(*) FROM audit_events WHERE entity_id=? AND action='notice_receipt'",(notice['id'],)).fetchone()[0],1)

    async def test_lost_ack_response_recovers_after_client_restart_even_when_server_inbox_is_empty(self):
        await self.lost_response('/acknowledge')

    async def test_lost_receive_response_reuses_original_offer_after_client_restart(self):
        await self.lost_response('/receive')
