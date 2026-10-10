import unittest
import time
from unittest.mock import patch
from test import test_dashboard_auth as auth_tests
from test.test_dashboard_round1 import REGISTRY


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
        got = {'ids':['checkpoint_fixture'], 'metadatas':[{'agent':'claude','surface':'desktop (auto)','monitor':'hourly-room-sweep-runner','updated_at':'2026-10-09T00:00:00Z'}],
               'documents':['{"process_exit":1,"closeout_verified":false,"secret":"fixture-private"}']}
        event = {'sender':'@codex:test','sig_agent':'codex','sig_surface':'laptop','sig_role':'heartbeat','ts':time.time()*1000,
                 'room':'Tasks','room_id':'!tasks:test','tag':'STATUS','event_id':'$recent'}
        with patch.object(self.memory.checkpoints,'get',return_value=got), patch.object(self.memory,'WATCHER_REGISTRY',REGISTRY,create=True):
            result=self.memory._build_surfaces({'events':[event]}, {'codex'})
        self.assertEqual(next(s for s in result['surfaces'] if s['agent']=='claude')['state'], 'failed')
        self.assertEqual(result['watchers'][0]['state'], 'failed')
        self.assertEqual(result['watchers'][0]['source_refs'], ['checkpoint_fixture'])
        self.assertNotIn('fixture-private', str(result))

    async def test_new_asset_has_static_csp(self):
        result=await self.client.get('/static/slice.js')
        self.assertEqual(result.status_code,200)
        self.assertNotIn('unsafe-inline',result.headers['content-security-policy'])

    async def test_work_retains_old_unresolved_relays_beyond_recent_limit(self):
        got = {'ids':['relay_old'] + [f'relay_{i}' for i in range(501)],
               'metadatas':[{'state':'queued','updated_at':'2020-01-01'}] +
                           [{'state':'resolved','updated_at':'2026-10-09'} for _ in range(501)],
               'documents':['fixture'] * 502}
        with patch.object(self.memory.relays, 'get', return_value=got):
            result=self.memory.api_dashboard_work()
        self.assertEqual(len([i for i in result['items'] if i['id'].startswith('relay_')]),502)
        self.assertEqual(next(i for i in result['items'] if i['id']=='relay_old')['state'],'queued')
        self.assertEqual(result['counts']['queued'], 1)
        self.assertGreaterEqual(result['counts']['done'], 501)
        self.assertTrue(all(stage in result['counts'] for stage in ('queued','claimed','running','review','blocked','done')))

    async def test_unknown_monitor_has_unconfirmed_cadence(self):
        got={'ids':['checkpoint_unknown'], 'metadatas':[{'agent':'codex','surface':'laptop','monitor':'custom monitor'}], 'documents':['{}']}
        with patch.object(self.memory.checkpoints,'get',return_value=got),patch.object(self.memory,'WATCHER_REGISTRY',[],create=True):
            result=self.memory._build_surfaces({'events':[]},{'codex'})
        self.assertEqual(result['watchers'],[])
        self.assertEqual(result['surfaces'][0]['state'],'unknown')

    async def test_inbox_reads_durable_failures_and_old_queues(self):
        now=time.time()
        at=lambda age: self.memory.datetime.fromtimestamp(now-age*60,self.memory.timezone.utc).isoformat()
        self.memory.checkpoints.upsert(ids=['checkpoint_fail'],documents=['process_exit=1'],
                                      metadatas=[{'agent':'claude','surface':'desktop (auto)','monitor':'hourly-room-sweep-runner','updated_at':at(2)}])
        self.memory.relays.upsert(ids=['relay_old','relay_new'],documents=['Investigate stale work','Fresh handoff'],
                                 metadatas=[{'state':'queued','target_agent':'codex','updated_at':at(4321)},
                                            {'state':'queued','target_agent':'codex','updated_at':at(1)}])
        async def room_events(): return {'events':[],'reactions':[]}
        try:
            with patch.object(self.memory,'WATCHER_REGISTRY',REGISTRY,create=True),patch.object(self.memory,'_fetch_room_events',room_events):
                result=await self.client.get('/api/inbox',headers={'Authorization':'Bearer codex-test-token'})
            self.assertEqual(result.status_code,200)
            items=result.json()['items']
            self.assertEqual([i['kind'] for i in items],['failed_watcher','overdue_work'])
            self.assertEqual(items[1]['title'],'Investigate stale work')
        finally:
            self.memory.checkpoints.delete(ids=['checkpoint_fail']);self.memory.relays.delete(ids=['relay_old','relay_new'])

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
