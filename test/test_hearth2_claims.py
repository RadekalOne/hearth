"""Real process races and stale-attempt fencing; no model/provider calls."""
import multiprocessing
import sqlite3
import unittest
from datetime import datetime, timedelta, timezone
import test_hearth2_store as fixtures
from hearth2.store import Store, Principal, RecordError


def race_claim(path, task, revision, barrier, queue, name):
    try:
        barrier.wait(timeout=10)
        claim = Store(path).claim(Principal(name,'controller'),task,expected_revision=revision,request_id=name)
        queue.put(('claimed',claim['id']))
    except RecordError:
        queue.put(('conflict',None))
    except BaseException as e:
        queue.put(('error',type(e).__name__))


class ClaimTests(unittest.TestCase):
    def setUp(self):
        fixtures.StoreTests.setUp(self)
        # Wall-clock matches subprocess clocks while race tests run.
        self.time=datetime.now(timezone.utc)
        d=self.store.create_decision(self.controller,self.plan['id'],intended_subject=self.rad.id,
                                     expires_at=(self.time+timedelta(days=1)).isoformat())
        self.store.record_decision(self.rad,d['id'],1,'approve','approved-source')
        self.role={'model':'gpt-6.1-sol','family':'openai','role':'senior'}
        self.store.set_role(self.rad,'codex',self.role)
        self.task=self.store.create_task(self.controller,self.payload)

    def claim(self, request='request-one'):
        return self.store.claim(self.controller,self.task['id'],expected_revision=self.task['revision'],request_id=request)

    def test_claim_interface_exists(self):
        self.assertTrue(callable(getattr(Store,'claim',None)), 'atomic claim is not implemented')

    def test_a5_two_independent_processes_claim_exactly_once(self):
        self.assertTrue(callable(getattr(Store,'claim',None)), 'atomic claim is not implemented')
        ctx=multiprocessing.get_context('fork');barrier=ctx.Barrier(2);queue=ctx.Queue()
        procs=[ctx.Process(target=race_claim,args=(self.path,self.task['id'],1,barrier,queue,'runner'+str(n))) for n in range(2)]
        for p in procs:p.start()
        results=[queue.get(timeout=15) for _ in procs]
        for p in procs:p.join(10);self.assertEqual(p.exitcode,0)
        self.assertEqual(sorted(r[0] for r in results),['claimed','conflict'])
        snap=self.store.snapshot()
        self.assertEqual(len(snap['claims']),1);self.assertEqual(len(snap['runs']),1)
        self.assertEqual(snap['tasks'][0]['attempts'],1)
        self.assertEqual(sum(a['action']=='claimed' for a in snap['audit_events']),1)

    def test_expired_lease_never_requeues_without_verified_termination(self):
        self.assertTrue(callable(getattr(Store,'claim',None)), 'atomic claim is not implemented')
        c=self.claim();self.time+=timedelta(hours=1)
        with self.assertRaises(RecordError):self.store.renew(self.controller,c,lease_until=(self.time+timedelta(minutes=15)).isoformat())
        with self.assertRaises(RecordError):self.store.record_run(self.controller,c,{})
        with self.assertRaises(RecordError):self.store.claim(self.controller,self.task['id'],expected_revision=2,request_id='next')
        self.assertEqual(len(self.store.snapshot()['runs']),1)

    def test_same_request_retry_is_idempotent_and_cannot_alias_task(self):
        self.assertTrue(callable(getattr(Store,'claim',None)), 'atomic claim is not implemented')
        one=self.claim();self.assertEqual(self.claim()['id'],one['id'])
        other=self.store.create_task(self.controller,{**self.payload,'action_id':'parallel'})
        with self.assertRaises(RecordError):self.store.claim(self.controller,other['id'],expected_revision=1,request_id='request-one')
        self.assertEqual(len(self.store.snapshot()['runs']),1)

    def test_three_failed_attempts_one_incident_no_fourth(self):
        self.assertTrue(callable(getattr(Store,'claim',None)), 'atomic claim is not implemented')
        for n in range(1,4):
            current=next(t for t in self.store.snapshot()['tasks'] if t['id']==self.task['id'])
            c=self.store.claim(self.controller,self.task['id'],expected_revision=current['revision'],request_id='attempt'+str(n))
            result=self.store.reconcile(self.controller,c['run_id'],termination_evidence=['controller-confirmed-empty'],outcome='failed')
            self.assertEqual(result['state'],'ready' if n<3 else 'failed')
        snap=self.store.snapshot();self.assertEqual(len(snap['incidents']),1)
        self.assertEqual(len(snap['incident_attempts']),3)
        self.assertEqual(snap['incidents'][0]['state'],'escalated')
        with self.assertRaises(RecordError):self.store.claim(self.controller,self.task['id'],expected_revision=result['revision'],request_id='fourth')

    def test_old_generation_epoch_and_runner_are_fenced(self):
        self.assertTrue(callable(getattr(Store,'claim',None)), 'atomic claim is not implemented')
        c=self.claim()
        for altered in [{**c,'generation':c['generation']-1},{**c,'restore_epoch':'old-epoch'},{**c,'attempt':9}]:
            with self.assertRaises(RecordError):self.store.renew(self.controller,altered,lease_until=c['lease_until'])
        with self.assertRaises(RecordError):self.store.renew(Principal('another-runner','controller'),c,lease_until=c['lease_until'])
        self.store.reconcile(self.controller,c['run_id'],termination_evidence=['verified empty'],outcome='failed')
        with self.assertRaises(RecordError):self.store.record_run(self.controller,c,{})

    def test_unknown_outcome_stays_held_and_worker_cannot_attest_stop(self):
        self.assertTrue(callable(getattr(Store,'claim',None)), 'atomic claim is not implemented')
        c=self.claim()
        self.store.reconcile(self.controller,c['run_id'],termination_evidence=[],outcome='unknown')
        task=next(t for t in self.store.snapshot()['tasks'] if t['id']==self.task['id'])
        self.assertEqual(task['state'],'held')
        with self.assertRaises(RecordError):self.store.reconcile(self.worker,c['run_id'],termination_evidence=['yes'],outcome='failed')
        with self.assertRaises(RecordError):self.store.claim(self.controller,task['id'],expected_revision=task['revision'],request_id='retry')

    def test_plan_and_role_are_rechecked_at_claim(self):
        self.assertTrue(callable(getattr(Store,'claim',None)), 'atomic claim is not implemented')
        self.store.create_plan(self.rad,self.project['id'],{'content_ref':'new scope'})
        with self.assertRaises(RecordError):self.claim()
        self.assertEqual(self.store.snapshot()['runs'],[])

    def test_model_change_after_claim_invalidates_renewal(self):
        self.assertTrue(callable(getattr(Store,'claim',None)), 'atomic claim is not implemented')
        c=self.claim();self.store.set_role(self.rad,'codex',{**self.role,'model':'other-model'})
        with self.assertRaises(RecordError):self.store.renew(self.controller,c,lease_until=c['lease_until'])
