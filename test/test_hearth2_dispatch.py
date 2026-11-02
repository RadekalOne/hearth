"""Durable single-workload registration, without a native process or credentials."""
import importlib
import multiprocessing
from pathlib import Path
from datetime import timedelta
import unittest
import test_hearth2_claims as fixtures
from hearth2.store import Store, Principal, RecordError
from hearth2.backup import export_record, restore_record


def consume_race(path, claim, barrier, queue):
    registry = importlib.import_module('hearth2.dispatch').DispatchRegistry(
        Store(path), Principal('controller', 'controller'))
    try:
        barrier.wait(timeout=10)
        registry.consume(claim)
        queue.put('launch')
    except RecordError:
        queue.put('refused')


class DispatchTests(unittest.TestCase):
    def setUp(self):
        fixtures.ClaimTests.setUp(self)
        self.assertIsNotNone(importlib.util.find_spec('hearth2.dispatch'),
                             'durable launch registry is not implemented')
        self.registry_type = importlib.import_module('hearth2.dispatch').DispatchRegistry
        self.registry = self.registry_type(self.store, self.controller)
        self.claim = self.store.claim(self.controller, self.task['id'], expected_revision=1,
                                      request_id='dispatch-first')

    def prepare(self, **changes):
        fields = dict(policy_sha256='a' * 64)
        fields.update(changes)
        return self.registry.prepare(self.claim, **fields)

    def other_claim(self):
        task = self.store.create_task(self.controller, {**self.payload, 'action_id':'parallel'})
        return self.store.claim(self.controller, task['id'], expected_revision=1,
                                request_id='dispatch-other')

    def test_prepare_survives_restart_but_never_reissues_consumed_launch(self):
        reserved = self.prepare()
        self.assertEqual(reserved['phase'], 'reserved')
        self.assertEqual(reserved['workload_id'], 'hearth2-' + self.claim['run_id'][4:])
        self.registry = self.registry_type(Store(self.path, clock=lambda:self.time), self.controller)
        self.assertEqual(self.prepare(), reserved)
        launching = self.registry.consume(self.claim)
        self.assertEqual(launching['phase'], 'launching')
        self.assertEqual(launching['deadline_at'],
                         self.store.snapshot()['runs'][0]['deadline_at'])
        self.registry = self.registry_type(self.store, self.controller)
        self.assertEqual(self.registry.pending(), [launching])
        self.assertEqual(self.prepare(), launching)
        with self.assertRaises(RecordError):
            self.registry.consume(self.claim)

    def test_other_task_or_controller_cannot_bypass_instance_slot(self):
        self.prepare()
        claim = self.other_claim()
        with self.assertRaises(RecordError):
            self.registry.prepare(claim, policy_sha256='a' * 64)
        other = self.registry_type(self.store, Principal('other-controller', 'controller'))
        with self.assertRaises(RecordError):
            other.prepare(claim, policy_sha256='a' * 64)
        self.assertEqual(len(self.registry.pending()), 1)

    def test_policy_change_unknown_claim_and_untrusted_actor_are_refused(self):
        self.prepare()
        for digest in ['b' * 64, 'not-a-digest', 'a' * 65]:
            with self.subTest(digest=digest), self.assertRaises(RecordError):
                self.prepare(policy_sha256=digest)
        for who in [self.rad, self.worker]:
            with self.assertRaises(RecordError):
                self.registry_type(self.store, who)
        with self.assertRaises(RecordError):
            self.registry.consume({**self.claim, 'generation':99})
        with self.assertRaises(RecordError):
            self.registry.consume({**self.claim, 'restore_epoch':'old'})

    def test_expiry_blocks_launch_without_releasing_the_uncertain_slot(self):
        self.prepare()
        self.time += timedelta(hours=1)
        with self.assertRaises(RecordError):
            self.registry.consume(self.claim)
        with self.assertRaises(RecordError):
            self.registry.release(self.claim['run_id'])
        self.assertEqual(len(self.registry.pending()), 1)

    def test_unregistered_claim_cannot_be_consumed_or_released(self):
        with self.assertRaises(RecordError):
            self.registry.consume(self.claim)
        with self.assertRaises(RecordError):
            self.registry.release(self.claim['run_id'])

    def test_unknown_outcome_stays_reserved_until_record_confirms_termination(self):
        first = self.prepare()
        self.registry.consume(self.claim)
        self.store.reconcile(self.controller, self.claim['run_id'], outcome='unknown',
                             termination_evidence=[])
        with self.assertRaises(RecordError):
            self.registry.release(self.claim['run_id'])
        self.assertEqual(len(self.registry.pending()), 1)
        self.store.reconcile(self.controller, self.claim['run_id'], outcome='failed',
                             termination_evidence=['outside-observer-empty'])
        released = self.registry.release(self.claim['run_id'])
        self.assertEqual(released['phase'], 'released')
        self.assertEqual(released['workload_id'], first['workload_id'])
        self.assertEqual(self.registry.release(self.claim['run_id']), released)
        self.assertEqual(self.registry.pending(), [])
        claim = self.other_claim()
        self.registry.prepare(claim, policy_sha256='a' * 64)
        self.assertEqual(len(self.registry.pending()), 1)

    def test_old_controller_cannot_release_another_owners_registration(self):
        self.prepare()
        self.store.reconcile(self.controller, self.claim['run_id'], outcome='failed',
                             termination_evidence=['outside-observer-empty'])
        other = self.registry_type(self.store, Principal('other-controller', 'controller'))
        with self.assertRaises(RecordError):
            other.release(self.claim['run_id'])
        self.assertEqual(len(other.pending()), 1)

    def test_restore_keeps_identity_and_blocks_launch_until_reconciled(self):
        registered = self.prepare()
        bundle, target = Path(self.tmp.name)/'backup.json', Path(self.tmp.name)/'restored.db'
        export_record(self.path, bundle)
        restore_record(bundle, target, controller_stopped=True)
        store = Store(target, clock=lambda:self.time)
        registry = self.registry_type(store, self.controller)
        self.assertEqual(registry.pending(), [registered])
        with self.assertRaises(RecordError):
            registry.consume(self.claim)
        with self.assertRaises(RecordError):
            registry.release(self.claim['run_id'])
        store.reconcile(self.controller, self.claim['run_id'], outcome='failed',
                        termination_evidence=['post-restore-outside-empty'])
        registry.release(self.claim['run_id'])
        self.assertEqual(registry.pending(), [])

    def test_two_independent_consumers_get_exactly_one_launch(self):
        self.prepare()
        ctx = multiprocessing.get_context('fork')
        barrier, queue = ctx.Barrier(2), ctx.Queue()
        processes = [ctx.Process(target=consume_race,
                     args=(self.path, self.claim, barrier, queue)) for _ in range(2)]
        for process in processes:
            process.start()
        results = [queue.get(timeout=15) for _ in processes]
        for process in processes:
            process.join(10)
            self.assertEqual(process.exitcode, 0)
        self.assertEqual(sorted(results), ['launch', 'refused'])
        self.assertEqual(self.registry.pending()[0]['phase'], 'launching')

    def test_restore_cannot_release_unresolved_slot_using_pre_restore_closed_run_proof(self):
        self.prepare()
        launching = self.registry.consume(self.claim)
        self.store.reconcile(self.controller, self.claim['run_id'], outcome='failed',
                             termination_evidence=['pre-restore-empty'])
        bundle, target = Path(self.tmp.name)/'closed.json', Path(self.tmp.name)/'closed-restored.db'
        export_record(self.path, bundle)
        restore_record(bundle, target, controller_stopped=True)
        registry = self.registry_type(Store(target, clock=lambda:self.time), self.controller)
        with self.assertRaises(RecordError):
            registry.release(self.claim['run_id'])
        self.assertEqual(registry.pending(), [launching])


if __name__ == '__main__':
    unittest.main()
