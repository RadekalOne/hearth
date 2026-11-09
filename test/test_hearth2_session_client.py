"""Named-session client defenses and durable inbox, without external requests."""
import hashlib,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import httpx
sys.path.insert(0,str(Path(__file__).parents[1]/'mcp/memory'))
from hearth2.delivery import NoticeSession


class SessionClientTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'private'/'inbox.db'
        self.target=NoticeSession('claude-a','session-a','claude');self.origin='https://hearth.test'
        self.notice=dict(id='notice_'+'1'*32,project_id='project_'+'2'*32,task_id='task_'+'3'*32,
            sender='controller',recipient='claude',kind='interface_changed',reference='Untrusted notice text')
        self.digest=hashlib.sha256(json.dumps(self.notice,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        self.offer=dict(notice=self.notice,session_id='claude-a',recipient='claude',notice_digest=self.digest,
            delivery_id='delivery_'+'4'*32,restore_epoch='epoch-one',offered_at='2026-11-09T12:00:00+00:00',offered_sequence=10)
        self.receipt=dict(session_id='claude-a',principal_id='session-a',recipient='claude',notice_id=self.notice['id'],
            notice_digest=self.digest,delivery_id=self.offer['delivery_id'],restore_epoch='epoch-one',offered_sequence=10,
            seq=11,at='2026-11-09T12:00:01+00:00',actor='session-a')
        self.calls=[]

    def client(self,handler=None,**changes):
        from hearth2.session_client import NamedSessionClient
        from hearth2.session_inbox import SessionInbox
        fields=dict(origin=self.origin,target=self.target,token='fixture-session-secret',
            inbox=SessionInbox(self.path,self.origin,self.target),transport=httpx.MockTransport(handler or self.handler))
        fields.update(changes);return NamedSessionClient(**fields)

    def handler(self,request):
        self.calls.append(request)
        if request.method=='GET':return httpx.Response(200,json=dict(notices=[dict(id=self.notice['id'],task_id=self.notice['task_id'],kind=self.notice['kind'],recipient='claude',recipient_session='claude-a')],more_pending=False,restore_epoch='epoch-one'))
        if request.url.path.endswith('/receive'):return httpx.Response(200,json=self.offer)
        return httpx.Response(200,json=self.receipt)

    async def test_stores_before_ack_and_credential_never_enters_records(self):
        client=self.client()
        def handler(request):
            if request.url.path.endswith('/acknowledge'):
                rows=client.inbox.records();self.assertEqual(rows[0]['notice'],self.notice)
                self.assertEqual(rows[0]['delivery_state'],'stored_unconfirmed')
            self.assertEqual(request.headers['Authorization'],'Bearer fixture-session-secret')
            return self.handler(request)
        client.transport=httpx.MockTransport(handler)
        result=await client.poll_once()
        self.assertEqual((result.stored,result.receipts_recorded,result.understanding_state),(1,1,'unknown'))
        rows=client.inbox.records();self.assertEqual(rows[0]['delivery_state'],'receipt_recorded')
        self.assertEqual(rows[0]['understanding_state'],'unknown')
        self.assertNotIn('fixture-session-secret',self.path.read_bytes().decode('latin1'))
        self.assertNotIn('fixture-session-secret',repr(result))

    async def test_invalid_offer_identity_digest_or_body_never_acknowledged(self):
        from hearth2.session_client import DeliveryClientError
        for changes in [dict(session_id='claude-b'),dict(recipient='codex'),dict(notice_digest='0'*64),
                dict(restore_epoch='old'),dict(offered_sequence=True),dict(notice={**self.notice,'id':'notice_'+'9'*32})]:
            self.calls=[]
            def handler(request):
                if request.url.path.endswith('/receive'):
                    self.calls.append(request);return httpx.Response(200,json={**self.offer,**changes})
                return self.handler(request)
            with self.subTest(changes=changes),self.assertRaises(DeliveryClientError):await self.client(handler).poll_once()
            self.assertFalse(any(r.url.path.endswith('/acknowledge') for r in self.calls))

    async def test_local_storage_failure_never_acknowledges(self):
        from hearth2.session_inbox import SessionInboxError
        client=self.client()
        with patch.object(client.inbox,'store',side_effect=SessionInboxError('fixture storage failure')):
            with self.assertRaises(SessionInboxError):await client.poll_once()
        self.assertFalse(any(r.url.path.endswith('/acknowledge') for r in self.calls))

    async def test_bad_receipt_stays_locally_unconfirmed(self):
        from hearth2.session_client import DeliveryClientError
        def handler(request):
            if request.url.path.endswith('/acknowledge'):return httpx.Response(200,json={**self.receipt,'actor':'another-session'})
            return self.handler(request)
        client=self.client(handler)
        with self.assertRaises(DeliveryClientError):await client.poll_once()
        self.assertEqual(client.inbox.records()[0]['delivery_state'],'stored_unconfirmed')

    async def test_redirect_and_oversize_response_fail_without_following_or_persistence(self):
        from hearth2.session_client import DeliveryClientError
        for response in [httpx.Response(302,headers={'Location':'https://elsewhere.test/steal'}),httpx.Response(200,content=b'X'*262145)]:
            calls=[]
            def handler(request):calls.append(request);return response
            with self.assertRaises(DeliveryClientError):await self.client(handler).poll_once()
            self.assertEqual(len(calls),1)

    def test_scope_and_origin_changes_refuse_without_overwriting_inbox(self):
        from hearth2.session_client import DeliveryClientError
        from hearth2.session_inbox import SessionInbox,SessionInboxError
        client=self.client();before=self.path.read_bytes()
        for origin,target in [('https://other.test',self.target),(self.origin,NoticeSession('claude-b','session-b','claude'))]:
            with self.assertRaises(SessionInboxError):SessionInbox(self.path,origin,target)
            self.assertEqual(self.path.read_bytes(),before)
        for origin in ['http://hearth.test','https://user:password@hearth.test','https://hearth.test/path','https://hearth.test/?query=1']:
            with self.assertRaises(DeliveryClientError):self.client(origin=origin)

    async def test_response_cookies_are_not_forwarded_with_session_bearer(self):
        def handler(request):
            self.assertNotIn('cookie',request.headers)
            response=self.handler(request)
            response.headers['set-cookie']='unrelated-browser-session=fixture; Path=/'
            return response
        await self.client(handler).poll_once()

    async def test_replaced_inbox_scope_is_rechecked_before_any_ack(self):
        from hearth2.session_inbox import SessionInbox,SessionInboxError
        client=self.client()
        foreign=SessionInbox(Path(self.tmp.name)/'foreign.db',self.origin,NoticeSession('claude-b','session-b','claude'))
        self.path.write_bytes(foreign.path.read_bytes());before=self.path.read_bytes()
        with self.assertRaises(SessionInboxError):await client.poll_once()
        self.assertFalse(any(r.url.path.endswith('/acknowledge') for r in self.calls))
        self.assertEqual(self.path.read_bytes(),before)

    async def test_batch_is_bounded_and_reports_unprocessed_notices(self):
        client=self.client(max_notices=1)
        def handler(request):
            if request.method=='GET':return httpx.Response(200,json=dict(notices=[
                dict(id=self.notice['id'],task_id=self.notice['task_id'],kind='interface_changed',recipient='claude',recipient_session='claude-a'),
                dict(id='notice_'+'8'*32,task_id=self.notice['task_id'],kind='blocked',recipient='claude',recipient_session='claude-a')],more_pending=False,restore_epoch='epoch-one'))
            return self.handler(request)
        client.transport=httpx.MockTransport(handler)
        result=await client.poll_once();self.assertTrue(result.more_pending);self.assertEqual(result.receipts_recorded,1)
