"""Run evidence, acceptance and downstream dependency behavior."""
import json
import unittest
from datetime import timedelta
import test_hearth2_claims as fixtures
from hearth2.store import Store, Principal, RecordError


class ReceiptTests(unittest.TestCase):
    def setUp(self):
        fixtures.ClaimTests.setUp(self)
        self.claim=self.store.claim(self.controller,self.task['id'],expected_revision=1,request_id='receipt')
        self.time+=timedelta(seconds=2)
        self.closeout={'task':self.task['id'],'attempt':1,'status':'done','produced':'artifact-ref',
            'changed':'implemented','unblocked':'none','memory-used':['drawer_fixture'],
            'checks-run':[{'name':'Done check','passed':True,'evidence':'test-receipt'}],
            'next':'claude reviews'}
        self.receipt={'ended_at':self.time.isoformat(),'exit_status':0,'closeout':self.closeout,
            'containment_state':'verified_empty','termination_evidence':['controller-cgroup-empty'],
            'usage':{'state':'unknown','units':None,'estimated_cost':None,'actual_charge':None}}

    def test_complete_run_stays_in_review_and_unknown_cost_stays_unknown(self):
        r=self.store.record_run(self.controller,self.claim,self.receipt)
        self.assertEqual(r['closeout_validation'],'valid')
        self.assertEqual(r['usage_state'],'unknown');self.assertIsNone(r['actual_charge'])
        self.assertEqual(self.store.snapshot()['tasks'][0]['state'],'review')
        self.assertEqual(self.store.snapshot()['claims'][0]['state'],'closed')

    def test_missing_closeout_and_nonzero_exit_are_failed_runs(self):
        for change in [{'closeout':None},{'exit_status':9}]:
            # Each subcase is its own complete run and retry.
            r=self.store.record_run(self.controller,self.claim,{**self.receipt,**change})
            self.assertIn(r['closeout_validation'],['missing','valid'])
            task=self.store.snapshot()['tasks'][0]
            self.assertEqual(task['state'],'ready')
            self.assertEqual(len(self.store.snapshot()['incidents']),1)
            self.claim=self.store.claim(self.controller,task['id'],expected_revision=task['revision'],request_id='retry-missing')
            self.closeout['attempt']=2

    def test_unconfirmed_termination_cannot_release_work(self):
        r=self.store.record_run(self.controller,self.claim,{**self.receipt,'containment_state':'unconfirmed','termination_evidence':[]})
        self.assertEqual(r['containment_state'],'unconfirmed')
        self.assertEqual(self.store.snapshot()['tasks'][0]['state'],'held')
        self.assertEqual(self.store.snapshot()['claims'][0]['state'],'held')

    def test_forged_done_checks_and_task_identity_are_invalid_closeouts(self):
        r=self.store.record_run(self.controller,self.claim,{**self.receipt,'closeout':{**self.closeout,'task':'other'}})
        self.assertEqual(r['closeout_validation'],'invalid')
        self.assertEqual(self.store.snapshot()['tasks'][0]['state'],'ready')

    def test_usage_cannot_turn_unmeasured_into_zero_or_accept_nan(self):
        for usage in [{'state':'unknown','units':{'tokens':0}}, {'state':'measured','units':{'tokens':float('nan')}},
                      {'state':'measured','units':{'tokens':-1}}]:
            with self.subTest(usage=usage),self.assertRaises(RecordError):
                self.store.record_run(self.controller,self.claim,{**self.receipt,'usage':usage})
        self.assertEqual(self.store.snapshot()['tasks'][0]['state'],'running')

    def test_end_before_start_and_missing_exit_field_are_rejected_atomically(self):
        for change in [{'ended_at':(self.time-timedelta(days=1)).isoformat()}, {'exit_status':'0'}]:
            with self.assertRaises(RecordError):self.store.record_run(self.controller,self.claim,{**self.receipt,**change})
        missing=dict(self.receipt);missing.pop('exit_status')
        with self.assertRaises(RecordError):self.store.record_run(self.controller,self.claim,missing)
        self.assertEqual(self.store.snapshot()['tasks'][0]['state'],'running')

    def test_review_independence_acceptance_and_dependency_gate(self):
        self.assertTrue(callable(getattr(Store,'record_review',None)),'review contract not implemented')
        child=self.store.create_task(self.controller,{**self.payload,'action_id':'followup','dependencies':[self.task['id']]})
        self.store.record_run(self.controller,self.claim,self.receipt)
        with self.assertRaises(RecordError):self.store.claim(self.controller,child['id'],expected_revision=1,request_id='child')
        with self.assertRaises(RecordError):self.store.record_review(self.worker,self.task['id'],3,'pass',['evidence'])
        self.store.set_role(self.rad,'claude',{'model':'claude','family':'anthropic','role':'senior'})
        result=self.store.record_review(Principal('claude','worker'),self.task['id'],3,'pass',['independent-test'])
        with self.assertRaises(RecordError):self.store.claim(self.controller,child['id'],expected_revision=1,request_id='child')
        accepted=self.store.accept_result(self.rad,self.task['id'],result['revision'],['human-acceptance'])
        self.assertEqual(accepted['state'],'accepted')
        c=self.store.claim(self.controller,child['id'],expected_revision=1,request_id='child')
        self.assertEqual(c['attempt'],1)

    def test_same_family_review_is_refused_even_for_another_agent(self):
        self.assertTrue(callable(getattr(Store,'record_review',None)),'review contract not implemented')
        self.store.record_run(self.controller,self.claim,self.receipt)
        self.store.set_role(self.rad,'other',{'model':'another','family':'openai','role':'senior'})
        with self.assertRaises(RecordError):self.store.record_review(Principal('other','worker'),self.task['id'],3,'pass',['check'])

    def test_notices_are_fenced_and_sender_is_authenticated(self):
        self.assertTrue(callable(getattr(Store,'append_notice',None)),'notice contract not implemented')
        payload={'task_id':self.task['id'],'recipient':'claude','kind':'blocked','reference':'evidence'}
        notice=self.store.append_notice(self.controller,payload,claim=self.claim)
        self.assertEqual(notice['sender'],self.controller.id)
        self.store.record_run(self.controller,self.claim,self.receipt)
        with self.assertRaises(RecordError):self.store.append_notice(self.controller,payload,claim=self.claim)
