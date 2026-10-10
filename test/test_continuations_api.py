import unittest
from unittest.mock import patch
from test import test_coordination_api as coord_api


class ContinuationAPI(unittest.IsolatedAsyncioTestCase):
    setUpClass=coord_api.CoordinationAPITests.__dict__['setUpClass']
    tearDownClass=coord_api.CoordinationAPITests.__dict__['tearDownClass']
    asyncSetUp=coord_api.CoordinationAPITests.asyncSetUp
    asyncTearDown=coord_api.CoordinationAPITests.asyncTearDown
    post=coord_api.CoordinationAPITests.post
    project=coord_api.CoordinationAPITests.project
    answer=coord_api.CoordinationAPITests.answer

    async def test_reply_bootstrap_claim_and_cancel_with_explicit_surface(self):
        await self.post('/api/coordination/wait',{**self.wait_payload,'continuation':{'last_read_event':'$request','next_action':'Read Claude review and fix validation'}},'codex-test-token')
        self.assertEqual((await self.answer()).status_code,200)
        context=self.memory.CURRENT_PRINCIPAL.set('codex')
        try:
            bootstrap=self.memory.bootstrap('codex',compact=True)
            jobs=[r for r in bootstrap['relay_inbox']['entries'] if r.get('origin')=='continuation']
            self.assertEqual(len(jobs),1)
            job=jobs[0];self.assertEqual(job['next_action'],'Read Claude review and fix validation')
            self.assertFalse(job['grants_authority'])
            with self.assertRaises(ValueError):self.memory.claim_relay(job['relay_id'],'codex','laptop (auto)')
            self.assertEqual(self.memory.claim_relay(job['relay_id'],'codex','interactive')['state'],'claimed')
            self.assertEqual(len([r for r in self.memory.bootstrap('codex',compact=True)['relay_inbox']['entries'] if r.get('origin')=='continuation']),1)
            self.memory.coordination_store.set_wait('codex',False,owner='codex',expected_generation=1,
                parties=[{'kind':'agent','id':'claude','required_surface':'interactive'}],source_event='$new',since='2026-10-10T15:00:00Z',**self.identity)
            with self.assertRaises(self.memory._coordination_module.CoordinationError):self.memory.claim_relay(job['relay_id'],'codex','interactive')
            self.assertFalse(any(r['relay_id']==job['relay_id'] for r in self.memory.relay_inbox_for('codex')['entries']))
        finally:
            self.memory.CURRENT_PRINCIPAL.reset(context)
            if 'job' in locals():self.memory.relays.delete(ids=[job['relay_id']])

    async def test_delivery_before_ack_reconciles_existing_chroma_after_restart(self):
        await self.post('/api/coordination/wait',self.wait_payload,'codex-test-token');await self.answer()
        key=self.memory.coordination_store.deliveries('codex')[0]['delivery_id']
        original=self.memory.relays.upsert
        def crash(**args):original(**args);raise RuntimeError('crash')
        context=self.memory.CURRENT_PRINCIPAL.set('codex')
        try:
            with patch.object(self.memory.relays,'upsert',side_effect=crash):
                with self.assertRaises(RuntimeError):self.memory.bootstrap('codex',compact=True)
            restart=self.memory._coordination_module.CoordinationStore(self.memory.coordination_store.path,enabled=True)
            restart.initialize();self.memory.coordination_store=restart
            result=self.memory.bootstrap('codex',compact=True)
            self.assertEqual(sum(r['relay_id']==key for r in result['relay_inbox']['entries']),1)
            self.assertEqual(restart.deliveries('codex'),[])
        finally:
            self.memory.CURRENT_PRINCIPAL.reset(context);self.memory.relays.delete(ids=[key])
