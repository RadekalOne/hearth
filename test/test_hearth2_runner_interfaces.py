"""Runner prerequisites exercised without provider calls."""
import json
import unittest
from datetime import timedelta
from pathlib import Path
import test_hearth2_receipts as fixtures
from hearth2.store import Store, Principal, RecordError, timestamp
from hearth2.backup import export_record, restore_record, validate_domain


class RunnerInterfaceTests(unittest.TestCase):
    def setUp(self):
        fixtures.ReceiptTests.setUp(self)

    def wait_for_answer(self):
        self.store.record_run(self.controller, self.claim, {
            **self.receipt, 'closeout': {**self.closeout, 'status': 'needs-decision'}})
        return self.store.snapshot()['tasks'][0]

    def answer(self, **changes):
        fields = dict(expected_revision=3, run_id=self.claim['run_id'],
                      answer='Use the existing approved input.', evidence=['human-answer-ref'])
        fields.update(changes)
        return self.store.answer_task(self.rad, self.task['id'], **fields)

    def test_answer_releases_one_more_attempt_with_scope_and_history_intact(self):
        waiting = self.wait_for_answer()
        result = self.answer()
        self.assertEqual((result['state'], result['revision'], result['attempts']), ('ready', 4, 1))
        data = json.loads(result['data'])
        for field in ['inputs', 'ask', 'done_means', 'return']:
            self.assertEqual(data[field], json.loads(waiting['data'])[field])
        self.assertEqual(data['human_answers'][0]['actor'], self.rad.id)
        c = self.store.claim(self.controller, result['id'], expected_revision=4, request_id='answered')
        self.assertEqual(c['attempt'], 2)
        self.assertEqual(len(self.store.snapshot()['runs']), 2)

    def test_answer_requires_original_human_run_revision_evidence_and_single_use(self):
        self.wait_for_answer()
        for actor in [self.controller, self.worker, Principal('other', 'human')]:
            with self.subTest(actor=actor), self.assertRaises(RecordError):
                self.store.answer_task(actor, self.task['id'], expected_revision=3,
                    run_id=self.claim['run_id'], answer='answer', evidence=['ref'])
        for change in [dict(expected_revision=True), dict(expected_revision=2),
                       dict(run_id='wrong-run'), dict(answer=' '), dict(evidence=[])]:
            with self.subTest(change=change), self.assertRaises(RecordError):
                self.answer(**change)
        self.answer()
        # A pre-answer card uses revision 3; the answered task is revision 4.
        with self.assertRaises(RecordError):
            self.answer()
        with self.assertRaises(RecordError):
            self.store.claim(self.controller,self.task['id'],expected_revision=3,request_id='stale-answer-card')
        with self.assertRaises(RecordError):
            self.store.renew(self.controller,self.claim,lease_until=self.claim['lease_until'])
        self.assertEqual(sum(a['action'] == 'human_answered' for a in self.store.snapshot()['audit_events']), 1)

    def test_held_unknown_exit_cannot_be_answered(self):
        self.store.record_run(self.controller, self.claim, {**self.receipt, 'exit_status': None,
            'closeout': {**self.closeout, 'status': 'needs-decision'}})
        with self.assertRaises(RecordError):
            self.answer()
        # A trusted failed reconciliation can release the unknown-exit run;
        # this was never a known-exit human wait and must still export.
        self.store.reconcile(self.controller,self.claim['run_id'],outcome='failed',termination_evidence=['confirmed-empty'])
        bundle=Path(self.tmp.name)/'reconciled.json'
        export_record(self.path,bundle)
        self.assertTrue(bundle.exists())

    def test_answer_cannot_reset_three_launch_limit(self):
        for attempt in (1,2,3):
            self.store.record_run(self.controller, self.claim, {**self.receipt,
                'closeout':{**self.closeout,'attempt':attempt,'status':'needs-decision'}})
            task=self.store.snapshot()['tasks'][0]
            if attempt == 3:
                with self.assertRaises(RecordError):
                    self.answer(expected_revision=task['revision'],run_id=self.claim['run_id'])
            else:
                ready=self.answer(expected_revision=task['revision'],run_id=self.claim['run_id'])
                self.claim=self.store.claim(self.controller,task['id'],expected_revision=ready['revision'],request_id='answer-'+str(attempt))
        self.assertEqual(self.store.snapshot()['tasks'][0]['attempts'],3)

    def test_superseded_plan_does_not_gain_authority_from_answer(self):
        self.wait_for_answer()
        plan=self.store.create_plan(self.rad,self.project['id'],{'content_ref':'replacement','actions':self.action_manifest})
        d=self.store.create_decision(self.controller,plan['id'],intended_subject=self.rad.id,
            expires_at=(self.time+timedelta(days=1)).isoformat())
        self.store.record_decision(self.rad,d['id'],1,'approve','replacement-approval')
        with self.assertRaises(RecordError):self.answer()

    def test_second_review_disagreement_cannot_be_answered_as_a_run_question(self):
        self.store.set_role(self.rad, 'claude', {'model':'claude','family':'anthropic','role':'senior'})
        reviewer = Principal('claude', 'worker')
        self.store.record_run(self.controller, self.claim, self.receipt)
        self.store.record_review(reviewer, self.task['id'], 3, 'changes', ['first review'])
        self.store.revise_task(self.controller, self.task['id'], 4, 'revision ref')
        claim = self.store.claim(self.controller, self.task['id'], expected_revision=5, request_id='revision')
        self.store.record_run(self.controller, claim, {**self.receipt,
            'closeout': {**self.closeout, 'attempt': 2}})
        self.store.record_review(reviewer, self.task['id'], 7, 'changes', ['second review'])
        with self.assertRaises(RecordError):
            self.answer(expected_revision=8, run_id=claim['run_id'])

    def test_answer_survives_restore_and_unanswered_ready_bundle_is_rejected(self):
        self.wait_for_answer()
        broken = self.store.snapshot()
        broken['tasks'][0]['state'] = 'ready'
        with self.assertRaises(RecordError):
            validate_domain({k:v for k,v in broken.items() if isinstance(v, list)})
        self.answer()
        bundle, restored = Path(self.tmp.name)/'answered.json', Path(self.tmp.name)/'restored.db'
        export_record(self.path, bundle)
        restore_record(bundle, restored, controller_stopped=True)
        self.assertEqual(Store(restored).snapshot()['tasks'][0]['state'], 'ready')

    def test_short_timing_and_renewal_are_bounded_by_deadline(self):
        store = Store(self.path, clock=lambda:self.time, lease_seconds=10, deadline_seconds=5)
        task = store.create_task(self.controller, {**self.payload, 'action_id':'parallel'})
        c = store.claim(self.controller, task['id'], expected_revision=1, request_id='short')
        run = next(r for r in store.snapshot()['runs'] if r['id'] == c['run_id'])
        self.assertEqual(timestamp(c['lease_until']), self.time+timedelta(seconds=5))
        self.assertEqual(timestamp(run['deadline_at']), self.time+timedelta(seconds=5))
        with self.assertRaises(RecordError):
            store.renew(self.controller, c, lease_until=(self.time+timedelta(seconds=6)).isoformat())
        self.time += timedelta(seconds=5)
        with self.assertRaises(RecordError):
            store.claim(self.controller, task['id'], expected_revision=2, request_id='short')

    def test_invalid_timing_never_expands_approved_ceiling(self):
        for value in [0, -1, True, 1.5, '10', 7201]:
            for field in ['lease_seconds','deadline_seconds']:
                with self.subTest(value=value, field=field), self.assertRaises(RecordError):
                    Store(self.path, **{field:value})
