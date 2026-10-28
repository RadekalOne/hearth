"""Durable controller health, not native workload receipts."""
import unittest
import sqlite3
from contextlib import contextmanager
from datetime import timedelta
from pathlib import Path
import test_hearth2_receipts as fixtures
from hearth2.store import Store, Principal, RecordError
from hearth2.backup import export_record, restore_record
from unittest.mock import patch


class ControlLogTests(unittest.TestCase):
    def setUp(self):
        fixtures.ReceiptTests.setUp(self)

    def tick(self, **changes):
        fields = dict(request_id='cycle-one', expected_seq=0,
                      expected_epoch=self.store.control_snapshot()['restore_epoch'], evidence=['poll-complete'])
        fields.update(changes)
        return self.store.runner_tick(self.controller, **fields)

    def failure(self, **changes):
        fields = dict(kind='runner_stale', target=self.controller.id, key='missed-tick-one',
                      expected_epoch=self.store.control_snapshot()['restore_epoch'],
                      expected_seq=0, state='open', evidence=['supervisor-last-tick-ref'])
        fields.update(changes)
        return self.store.control_failure(Principal('supervisor','controller'), **fields)

    def test_tick_is_durable_cas_and_replay_does_not_refresh_liveness(self):
        first = self.tick()
        self.time += timedelta(minutes=3)
        self.assertEqual(self.tick(), first)
        with self.assertRaises(RecordError):
            self.tick(request_id='cycle-two')
        with self.assertRaises(RecordError):
            self.tick(evidence=['different'])
        second = self.tick(request_id='cycle-two', expected_seq=first['seq'])
        self.assertNotEqual(second['at'], first['at'])
        self.assertEqual(Store(self.path).control_snapshot()['ticks'][0], second)
        self.assertEqual(self.store.control_snapshot()['observed_at'], self.time.isoformat())

    def test_failures_have_no_fictitious_run_attempt_or_task_transition(self):
        before = self.store.snapshot()
        first = self.failure()
        self.assertEqual(self.failure(), first)
        with self.assertRaises(RecordError):
            self.failure(state='recovered')
        closed = self.failure(state='recovered', expected_seq=first['seq'], evidence=['recovered-proof'])
        self.assertEqual(closed['state'], 'recovered')
        after = self.store.snapshot()
        for table in ['tasks','runs','claims','incidents','incident_attempts']:
            self.assertEqual(before[table], after[table])
        self.assertEqual(self.store.control_snapshot()['failures'], [closed])

    def test_missing_evidence_unauthorized_and_foreign_task_are_rejected(self):
        for who in [self.rad, self.worker]:
            with self.assertRaises(RecordError):
                self.store.runner_tick(who, request_id='forged', expected_seq=0, expected_epoch='forged', evidence=['forged'])
            with self.assertRaises(RecordError):
                self.store.control_failure(who, kind='runner_stale', target='runner', key='x',
                    expected_seq=0, expected_epoch='forged', state='open', evidence=['forged'])
        for change in [dict(evidence=[]), dict(kind='unknown'), dict(expected_seq=True),
                       dict(kind='missed_start',target='not-a-task'), dict(state='recovered')]:
            with self.subTest(change=change), self.assertRaises(RecordError):
                self.failure(**change)

    def test_missed_start_requires_unlaunched_ready_work(self):
        task = self.store.create_task(self.controller, {**self.payload, 'action_id':'parallel'})
        self.failure(kind='missed_start', target=task['id'])
        with self.assertRaises(RecordError):
            self.failure(kind='missed_start', target=self.task['id'])
        self.assertEqual(self.store.snapshot()['tasks'][1]['attempts'], 0)

    def test_restore_preserves_history_but_never_restores_fresh_liveness(self):
        tick, failure = self.tick(), self.failure()
        bundle, restored = Path(self.tmp.name)/'control.json', Path(self.tmp.name)/'restored.db'
        export_record(self.path, bundle)
        restore_record(bundle, restored, controller_stopped=True)
        restored_store = Store(restored, clock=lambda:self.time)
        snap = restored_store.control_snapshot()
        self.assertNotEqual(snap['restore_epoch'], tick['restore_epoch'])
        self.assertEqual(snap['ticks'], [])
        self.assertEqual(snap['failures'], [failure])
        with self.assertRaises(RecordError):
            restored_store.runner_tick(self.controller, request_id='cycle-one', expected_seq=0,
                                       expected_epoch=tick['restore_epoch'], evidence=['poll-complete'])
        self.assertEqual(restored_store.control_snapshot()['ticks'], [])
        new = restored_store.runner_tick(self.controller, request_id='cycle-one', expected_seq=0,
                                        expected_epoch=snap['restore_epoch'], evidence=['fresh-poll'])
        self.assertGreater(new['seq'], tick['seq'])

    def test_failed_audit_transaction_publishes_no_tick(self):
        transaction=self.store.transaction
        @contextmanager
        def failing_transaction():
            with transaction() as db:
                db.set_authorizer(lambda action,*args: sqlite3.SQLITE_DENY
                                  if action == sqlite3.SQLITE_INSERT else sqlite3.SQLITE_OK)
                yield db
        with patch.object(self.store,'transaction',failing_transaction):
            with self.assertRaises(sqlite3.DatabaseError):self.tick()
        self.assertEqual(self.store.control_snapshot()['ticks'],[])

    def test_old_epoch_failure_recovery_is_refused_after_restore(self):
        first=self.failure()
        bundle,target=Path(self.tmp.name)/'failure.json',Path(self.tmp.name)/'failure-restored.db'
        export_record(self.path,bundle)
        restore_record(bundle,target,controller_stopped=True)
        restored=Store(target,clock=lambda:self.time)
        fields=dict(kind='runner_stale',target=self.controller.id,key='missed-tick-one',
                    expected_seq=first['seq'],expected_epoch=first['restore_epoch'],
                    state='recovered',evidence=['pre-restore-recovery'])
        before=restored.snapshot()
        with self.assertRaises(RecordError):
            restored.control_failure(Principal('supervisor','controller'),**fields)
        self.assertEqual(restored.snapshot(),before)
        self.assertEqual(restored.control_snapshot()['failures'],[first])
        fields['expected_epoch']=restored.control_snapshot()['restore_epoch']
        recovered=restored.control_failure(Principal('supervisor','controller'),**fields)
        self.assertEqual(recovered['state'],'recovered')
        self.assertEqual(recovered['restore_epoch'],fields['expected_epoch'])

    def test_older_failure_replay_is_refused_without_reopening_incident(self):
        first=self.failure()
        recovered=self.failure(state='recovered',expected_seq=first['seq'],evidence=['recovery-ref'])
        with self.assertRaises(RecordError):self.failure()
        self.assertEqual(self.store.control_snapshot()['failures'],[recovered])
