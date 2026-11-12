"""Deterministic relay acceptance; no Codex process, credentials or real messages."""
import concurrent.futures
from datetime import datetime,timezone
import importlib
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).parents[1]/'ops/hearth2'))


class RelayTests(unittest.TestCase):
    def setUp(self):
        self.core=importlib.import_module('offline_relay')
        self.state_mod=importlib.import_module('offline_relay_state')
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.state=self.state_mod.State(Path(self.tmp.name)/'relay.sqlite3')
        self.work={'work_id':'codex-work','aliases':['relay-one'],'generation':1,'review_event':'$review',
            'base_commit':'a'*40,'paths':['mcp/memory/hearth2/broker.py'],'scope':'hearth2-offline'}
        self.sent=[];self.launched=[];self.stopped=[]
        owner=self
        class Ports:
            def host_ok(self):return True
            def base_commit(self):return owner.work['base_commit']
            def poll(self):return [owner.work]
            def verify(self,work):return owner.core.Approval(owner.core.ROOM,owner.core.THREAD,
                '@rad:hearth.radekal.me',work['work_id'],work['generation'],work['base_commit'],tuple(work['paths']),'$approval','fixture',
                tuple(work['aliases']),work['review_event'])
            def allowance(self):return {'source':'fixture','included_only':True,'fresh':True,'fallback':False}
            def launch(self,job):
                owner.launched.append(job);return {'confirmed_empty':True,'exit_code':0,'commit':job['base_commit'],
                    'usage':{'state':'synthetic','input_tokens':2},'evidence':'fixture-only'}
            def stop(self,job):owner.stopped.append(job['id']);return True
            def disable(self):return True
            def post(self,room,thread,text):owner.sent.append((room,thread,text));return '$receipt'
        self.ports=Ports()
        self.runner=self.core.Dispatcher(self.state,self.ports,acceptance=True,
            clock=lambda:datetime(2026,11,12,17,tzinfo=timezone.utc))

    def enable_fixture(self):
        # Only the private acceptance DB; no public enable command exists.
        db=sqlite3.connect(self.state.path)
        try:
            with db:db.execute('UPDATE control SET paused=0, enabled=1')
        finally:db.close()

    def test_restart_drains_only_known_unsent_posts_even_when_held(self):
        self.enable_fixture()
        job=self.state.claim(self.core.admit(self.work,self.ports.verify(self.work),acceptance=True))
        self.state.finish(job,'held',{'confirmed_empty':False},'[STATUS] pending crash receipt')
        self.runner.check();self.runner.check()
        self.assertEqual(len(self.sent),1)
        self.assertEqual(self.state.outbox()[0]['state'],'sent')
        self.assertEqual(self.launched,[])

    def test_pause_does_not_depend_on_timezone_readiness(self):
        from unittest.mock import patch
        import contextlib,io
        with patch('offline_relay_ports.HostPorts.host_ok',return_value=False),patch(
            'offline_relay_ports.HostPorts.host_identity',return_value=True,create=True),patch(
            'offline_relay_ports.HostPorts.disable',return_value=True),patch.object(sys,'argv',
            ['relay','pause','--state',str(self.state.path)]),contextlib.redirect_stdout(io.StringIO()):
            self.core.main()
        self.assertTrue(self.state.control()['paused'])
        self.assertEqual(self.state.control()['status'],'paused')

    def test_default_paused_and_idle_make_no_calls_or_posts(self):
        self.assertEqual(self.runner.check()['state'],'paused')
        self.enable_fixture();self.ports.poll=lambda:[]
        self.assertEqual(self.runner.check()['state'],'idle')
        self.assertEqual(self.sent,[]);self.assertEqual(self.launched,[])

    def test_generation_executes_once_and_status_has_usage_and_fixed_thread(self):
        self.enable_fixture();self.runner.check();self.runner.check()
        self.assertEqual(len(self.launched),1);self.assertEqual(len(self.sent),1)
        self.assertEqual(self.sent[0][:2],(self.core.ROOM,self.core.THREAD))
        self.assertIn('seat_usage',self.sent[0][2]);self.assertIn('synthetic',self.sent[0][2])

    def test_wrong_source_scope_or_base_never_launches(self):
        self.enable_fixture();original=self.ports.verify
        for field,value in [('room','!other'),('sender','@claude:hearth.radekal.me'),('base_commit','b'*40)]:
            from dataclasses import replace
            self.ports.verify=lambda work,field=field,value=value:replace(original(work),**{field:value})
            self.runner.check()
        self.assertEqual(self.launched,[]);self.assertEqual(self.sent,[])

    def test_unknown_or_paid_fallback_refuses_without_launch_and_posts_once(self):
        self.enable_fixture();self.ports.allowance=lambda:{'included_only':True,'fresh':True,'fallback':True,'source':'fixture'}
        self.runner.check();self.runner.check()
        self.assertEqual(self.launched,[]);self.assertEqual(len(self.sent),1)
        self.assertIn('[BLOCKED]',self.sent[0][2]);self.assertIn('unavailable',self.sent[0][2])

    def test_claim_is_atomic_and_alias_collision_cannot_widen_work(self):
        self.enable_fixture();work=self.core.admit(self.work,self.ports.verify(self.work),acceptance=True)
        def claim(_):return self.state.claim(work)
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:results=list(pool.map(claim,range(8)))
        self.assertEqual(sum(x is not None for x in results),1)
        changed={**work,'work_id':'different'}
        self.assertIsNone(self.state.claim(changed))

    def test_dispatch_crash_is_held_never_replayed(self):
        self.enable_fixture()
        def crash(job):raise KeyboardInterrupt()
        self.ports.launch=crash
        with self.assertRaises(KeyboardInterrupt):self.runner.check()
        self.assertEqual(self.state.jobs()[0]['state'],'held')
        self.assertFalse(self.runner.check().get('launched',False))

    def test_lost_post_ack_is_not_reposted(self):
        self.enable_fixture()
        def lost(*args):self.sent.append(args);raise OSError('lost acknowledgment')
        self.ports.post=lost;self.runner.check();self.runner.check()
        self.assertEqual(len(self.sent),1);self.assertEqual(self.state.outbox()[0]['state'],'uncertain')

    def test_pause_persists_before_stopping_and_prevents_new_claims(self):
        self.enable_fixture();work=self.core.admit(self.work,self.ports.verify(self.work),acceptance=True)
        job=self.state.claim(work)
        def stop(row):
            self.assertTrue(self.state.control()['paused']);self.stopped.append(row['id']);return False
        self.ports.stop=stop;result=self.runner.pause()
        self.assertEqual(result['state'],'paused_pending_stop')
        self.assertEqual(self.stopped,[job['id']]);self.assertIsNone(self.state.claim(work))

    def test_live_mode_rejects_fixture_attestation_even_if_it_says_included(self):
        self.enable_fixture();runner=self.core.Dispatcher(self.state,self.ports,acceptance=False)
        runner.check();self.assertEqual(self.launched,[])

    def test_unknown_exhausted_and_stale_allowance_all_refuse(self):
        self.enable_fixture()
        cases=[None,{}, {'source':'fixture','included_only':False,'fresh':True,'fallback':False},
            {'source':'fixture','included_only':True,'fresh':False,'fallback':False},
            {'source':'unavailable','included_only':True,'fresh':True,'fallback':False}]
        for n,evidence in enumerate(cases,1):
            self.work['generation']=n;self.ports.allowance=lambda evidence=evidence:evidence
            self.assertEqual(self.runner.check()['state'],'blocked')
        self.assertEqual(self.launched,[])

    def test_fixture_allowance_cannot_pass_production_even_with_server_work_proof(self):
        from dataclasses import replace
        self.enable_fixture();old=self.ports.verify
        self.ports.verify=lambda work:replace(old(work),source='server_authenticated')
        runner=self.core.Dispatcher(self.state,self.ports,acceptance=False)
        self.assertEqual(runner.check()['state'],'blocked');self.assertEqual(self.launched,[])

    def test_lost_post_can_only_reconcile_with_matching_verified_receipt(self):
        self.enable_fixture()
        def lost(*args):raise OSError('unknown delivery')
        self.ports.post=lost;self.runner.check();row=self.state.outbox()[0]
        proof=self.core.PostReceipt(self.core.ROOM,self.core.THREAD,'@codex:hearth.radekal.me',
            '$existing',__import__('hashlib').sha256(row['body'].encode()).hexdigest(),'fixture')
        from dataclasses import replace
        self.assertFalse(self.runner.reconcile_post(row['id'],replace(proof,thread='$wrong')))
        self.assertTrue(self.runner.reconcile_post(row['id'],proof))
        self.assertEqual(self.state.outbox()[0]['state'],'sent');self.assertEqual(len(self.launched),1)

    def test_expanded_paths_and_room_instructions_are_untrusted(self):
        for path in ['../auth.json','.git/hooks/post-checkout','mcp/memory/hearth2/credential_sources.py']:
            bad={**self.work,'paths':[path]}
            with self.assertRaises(ValueError):self.core.admit(bad,self.ports.verify(bad),acceptance=True)

    def test_changed_checkout_base_is_not_admitted(self):
        self.enable_fixture();self.ports.base_commit=lambda:'b'*40
        self.runner.check();self.assertEqual(self.launched,[]);self.assertEqual(self.sent,[])

    def test_unapproved_alias_or_review_event_cannot_poison_work_identity(self):
        proof=self.ports.verify(self.work)
        for bad in [{**self.work,'aliases':['other-authorized-work']},{**self.work,'review_event':'$other'}]:
            with self.assertRaises(ValueError):self.core.admit(bad,proof,acceptance=True)

    def test_pause_wins_over_late_success_and_pending_stop_is_not_overwritten(self):
        self.enable_fixture()
        def late(job):
            self.runner.pause()
            return {'confirmed_empty':True,'exit_code':0,'commit':job['base_commit']}
        self.ports.launch=late
        result=self.runner.check();self.assertEqual(result['state'],'paused')
        self.assertEqual(self.sent,[]);self.assertEqual(self.state.jobs()[0]['state'],'paused')
        self.ports.disable=lambda:False
        self.runner.pause();self.runner.check()
        self.assertEqual(self.state.control()['status'],'paused_pending_stop')

    def test_transport_blocker_is_local_and_not_an_extra_task_or_repeated_post(self):
        self.enable_fixture()
        def broken():raise OSError('private transport detail')
        self.ports.poll=broken
        self.assertEqual(self.runner.check()['state'],'blocked');self.runner.check()
        self.assertEqual(self.launched,[]);self.assertEqual(self.state.jobs(),[])
        self.assertEqual(len(self.sent),1);self.assertNotIn('private transport detail',self.sent[0][2])


if __name__=='__main__':unittest.main()
