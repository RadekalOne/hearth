"""Regression tests for the whole-branch review findings."""
import json
import unittest
import test_hearth2_receipts as fixtures
from hearth2.store import Store, Principal, RecordError


class ReviewFixTests(unittest.TestCase):
    def setUp(self):fixtures.ReceiptTests.setUp(self)

    def reviewer(self):
        self.store.set_role(self.rad,'claude',{'model':'claude','family':'anthropic','role':'senior'})
        return Principal('claude','worker')

    def test_approval_cannot_authorize_a_new_action_not_in_its_manifest(self):
        with self.assertRaises(RecordError):
            self.store.create_task(self.controller,{**self.payload,'action_id':'unapproved','ask':'Deploy somewhere else'})

    def test_approved_action_fields_cannot_be_rewritten_or_duplicated(self):
        with self.assertRaises(RecordError):self.store.create_task(self.controller,{**self.payload,'ask':'Different scope'})
        with self.assertRaises(RecordError):self.store.create_task(self.controller,self.payload)

    def test_changes_have_one_revision_path_with_original_identity_and_history(self):
        self.assertTrue(callable(getattr(Store,'revise_task',None)), 'revision path missing')
        self.store.record_run(self.controller,self.claim,self.receipt)
        changed=self.store.record_review(self.reviewer(),self.task['id'],3,'changes',['fix-explanation'])
        revised=self.store.revise_task(self.controller,self.task['id'],changed['revision'],'addressed review')
        self.assertEqual(revised['id'],self.task['id'])
        self.assertEqual(revised['state'],'ready')
        claim=self.store.claim(self.controller,self.task['id'],expected_revision=revised['revision'],request_id='revision')
        self.assertEqual(claim['attempt'],2)
        self.closeout['attempt']=2
        self.store.record_run(self.controller,claim,self.receipt)
        task=next(t for t in self.store.snapshot()['tasks'] if t['id']==self.task['id'])
        second=self.store.record_review(Principal('claude','worker'),task['id'],task['revision'],'changes',['still unclear'])
        self.assertEqual(second['state'],'needs_decision')
        with self.assertRaises(RecordError):self.store.revise_task(self.controller,task['id'],second['revision'],'try again')

    def test_verified_stop_of_held_success_preserves_output_without_retry(self):
        self.store.record_run(self.controller,self.claim,{**self.receipt,'containment_state':'unconfirmed','termination_evidence':[]})
        result=self.store.reconcile(self.controller,self.claim['run_id'],termination_evidence=['verified-empty-later'],outcome='completed')
        self.assertEqual(result['state'],'review')
        self.assertEqual(result['attempts'],1)
        self.assertEqual(len(self.store.snapshot()['runs']),1)
        self.assertEqual(self.store.snapshot()['runs'][0]['closeout_validation'],'valid')

    def test_output_dependency_allows_feasibility_review_before_human_acceptance(self):
        # Covered 'followup' action explicitly requests an output-ready edge.
        child=self.store.create_task(self.controller,{**self.payload,'action_id':'feasibility','dependencies':[self.task['id']]})
        self.store.record_run(self.controller,self.claim,self.receipt)
        claim=self.store.claim(self.controller,child['id'],expected_revision=child['revision'],request_id='feasibility')
        self.assertEqual(claim['attempt'],1)

    def test_human_acceptance_of_result_for_superseded_plan_is_rejected(self):
        self.store.record_run(self.controller,self.claim,self.receipt)
        reviewed=self.store.record_review(self.reviewer(),self.task['id'],3,'pass',['independent'])
        self.store.create_plan(self.rad,self.project['id'],{'content_ref':'new-scope'})
        with self.assertRaises(RecordError):
            self.store.accept_result(self.rad,self.task['id'],reviewed['revision'],['old-acceptance'])
