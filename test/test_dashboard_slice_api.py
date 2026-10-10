import unittest
import time
from unittest.mock import patch
from test import test_dashboard_auth as auth_tests


class DashboardSliceAPITests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        auth_tests.DashboardAuthTests.setUpClass.__func__(cls)

    @classmethod
    def tearDownClass(cls):
        auth_tests.DashboardAuthTests.tearDownClass.__func__(cls)

    async def asyncSetUp(self):
        await auth_tests.DashboardAuthTests.asyncSetUp(self)

    async def asyncTearDown(self):
        await auth_tests.DashboardAuthTests.asyncTearDown(self)

    async def test_projection_routes_require_auth_and_agents_remain_read_only(self):
        for path in ['/api/dashboard/work', '/api/dashboard/memory-health']:
            self.assertEqual((await self.client.get(path)).status_code, 401)
        headers = {'Authorization': 'Bearer codex-test-token'}
        self.assertEqual((await self.client.get('/api/dashboard/work', headers=headers)).status_code, 200)
        denied = await self.client.post('/api/work/projects', headers=headers, json={'title':'Forbidden','goal':'Test'})
        self.assertEqual(denied.status_code, 403)

    async def test_failed_checkpoint_beats_newer_chat_and_exposes_only_receipt_fields(self):
        got = {'ids':['checkpoint_fixture'], 'metadatas':[{'agent':'codex','surface':'laptop','monitor':'hourly-runner','updated_at':'2026-10-09T00:00:00Z'}],
               'documents':['{"process_exit":1,"closeout_verified":false,"secret":"fixture-private"}']}
        event = {'sender':'@codex:test','sig_agent':'codex','sig_surface':'laptop','sig_role':'heartbeat','ts':time.time()*1000,
                 'room':'Tasks','room_id':'!tasks:test','tag':'STATUS','event_id':'$recent'}
        with patch.object(self.memory.checkpoints,'get',return_value=got):
            result=self.memory._build_surfaces({'events':[event]}, {'codex'})
        self.assertEqual(result['surfaces'][0]['state'], 'failed')
        self.assertEqual(result['watchers'][0]['state'], 'failed')
        self.assertEqual(result['watchers'][0]['source_refs'], ['checkpoint_fixture'])
        self.assertNotIn('fixture-private', str(result))

    async def test_new_asset_has_static_csp(self):
        result=await self.client.get('/static/slice.js')
        self.assertEqual(result.status_code,200)
        self.assertNotIn('unsafe-inline',result.headers['content-security-policy'])

    async def test_listener_is_event_driven_even_if_name_contains_auto(self):
        self.assertIsNone(self.memory._cadence_for('auto-wake mention listener'))

    async def test_inbox_orders_oldest_after_failures(self):
        now=time.time()*1000
        def event(eid,kind,offset):
            return {'event_id':eid,'room_id':'!room:test','room':'Tasks','sender':'@codex:test','ts':now+offset,
                    'body':f'[{kind}] example','tag':kind,'tag_base':kind,'sig_surface':'laptop','reply_to':None,'mentions':[]}
        # Different senders prevent the existing same-agent closeout rule from resolving the blocker.
        old=event('$old','QUESTION',-86400000)
        old.update(body='Rad, can you review?',mentions=['@rad:test'])
        events=[old,event('$approval','PLAN',-500000),event('$blocked','BLOCKED',-1000)]
        result=self.memory._build_inbox({'events':events,'reactions':[]},{'codex'})
        self.assertEqual([i['event_id'] for i in result['items']],['$blocked','$old','$approval'])
