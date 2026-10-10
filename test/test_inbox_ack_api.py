import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from test import test_dashboard_auth as auth


class InboxAcknowledgementAPI(unittest.IsolatedAsyncioTestCase):
    setUpClass=classmethod(auth.DashboardAuthTests.setUpClass.__func__)
    tearDownClass=classmethod(auth.DashboardAuthTests.tearDownClass.__func__)
    async def asyncSetUp(self):
        await auth.DashboardAuthTests.asyncSetUp(self)
        self.temp=tempfile.TemporaryDirectory()
        self.original=self.memory.inbox_acknowledgements
        self.memory.inbox_acknowledgements=self.memory._ack_module.Acknowledgements(Path(self.temp.name)/'ack.sqlite3')
        self.item={'kind':'blocked','event_id':'$blocked','room_id':'!tasks:test','thread_root':'$root'}
        self.data={'events':[],'reactions':[]}
        async def fetch(force=False):return self.data
        self.patches=[patch.object(self.memory,'_fetch_room_events',fetch),
                      patch.object(self.memory,'_build_inbox',lambda *a:{'items':[self.item],'total':1}),
                      patch.object(self.memory,'_build_surfaces',lambda *a:{'watchers':[]}),
                      patch.object(self.memory,'_dashboard_work_items',lambda:[])]
        for p in self.patches:p.start()
    async def asyncTearDown(self):
        for p in self.patches:p.stop()
        self.memory.inbox_acknowledgements=self.original
        self.temp.cleanup()
        await auth.DashboardAuthTests.asyncTearDown(self)
    async def get(self):return (await self.client.get('/api/inbox')).json()
    async def send(self,item,acknowledged=True):
        return await self.client.post('/api/inbox/acknowledgement',json={'kind':item['kind'],'item_id':item['event_id'],'state_key':item['state_key'],'acknowledged':acknowledged})
    async def test_bearer_agent_reviewer_and_csrf_denied_both_actions(self):
        for principal,kind in [('codex','token'),('claude-review','reviewer')]:
            self.client.cookies.set(self.memory.SESSION_COOKIE,self.memory.create_session(principal,kind,'codex-test-token'))
            for value in [True,False]:
                self.assertEqual((await self.client.post('/api/inbox/acknowledgement',json={'acknowledged':value},headers={'Authorization':'Bearer codex-test-token'})).status_code,403)
        self.client.cookies.clear()
        self.assertEqual((await self.client.post('/api/inbox/acknowledgement',headers={'Authorization':'Bearer admin-test-token'},json={})).status_code,403)
        self.client.cookies.set(self.memory.SESSION_COOKIE,self.memory.create_session('@rad:hearth.test','matrix'))
        self.assertEqual((await self.client.post('/api/inbox/acknowledgement',headers={'Origin':'https://evil.test'},json={})).status_code,403)
    async def test_human_session_stale_key_and_new_thread_message(self):
        self.client.cookies.set(self.memory.SESSION_COOKIE,self.memory.create_session('@rad:hearth.test','matrix'))
        inbox=await self.get();self.assertTrue(inbox['can_acknowledge']);item=inbox['items'][0]
        self.assertEqual((await self.send(item)).status_code,200)
        self.assertEqual((await self.get())['open_total'],0)
        self.data['events'].append({'event_id':'$new','room_id':'!tasks:test','thread_root':'$root','ts':2,'body':'New finding','tag_base':'REVIEW'})
        self.assertEqual((await self.get())['open_total'],1)
        self.assertEqual((await self.send(item)).status_code,409)
        self.assertEqual(len(self.memory.inbox_acknowledgements.audit()),1)
        fresh=(await self.get())['items'][0]
        self.assertEqual((await self.send(fresh)).status_code,200)
        self.assertEqual((await self.send(fresh,False)).status_code,200)
        self.assertEqual((await self.get())['open_total'],1)

    async def test_mutation_forces_source_refresh_and_ignores_self_ack(self):
        self.client.cookies.set(self.memory.SESSION_COOKIE,self.memory.create_session('@rad:hearth.test','matrix'))
        self.item['sender']='codex'
        item=(await self.get())['items'][0]
        stale=self.data
        new={'events':[{'event_id':'$fresh','room_id':'!tasks:test','thread_root':'$root','ts':3,'body':'New failure','tag_base':'REVIEW','sender':'@claude:test'}],'reactions':[]}
        async def cached(force=False):return new if force else stale
        with patch.object(self.memory,'_fetch_room_events',cached):
            self.assertEqual((await self.send(item)).status_code,409)
        self.data['events'].append({'event_id':'$self_ack','room_id':'!tasks:test','thread_root':'$root','ts':4,'body':'Received.\n— codex @ laptop','tag_base':'STATUS','sender':'@codex:test'})
        self.assertEqual((await self.get())['items'][0]['state_key'],item['state_key'])
