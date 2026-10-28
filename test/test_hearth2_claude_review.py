"""Claude's PR33 findings: preserve approval, uncertainty and receipt facts."""
import json
import os
import subprocess
import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path
import test_hearth2_receipts as fixtures
from hearth2.backup import export_record, restore_record
from hearth2.store import RecordError, Principal


class ClaudeReviewTests(unittest.TestCase):
    def setUp(self):
        fixtures.ReceiptTests.setUp(self)

    def next_plan(self):
        return self.store.create_plan(self.rad, self.project['id'],
            {'content_ref':'next draft', 'actions':self.action_manifest})

    def approve(self, plan):
        decision=self.store.create_decision(self.controller, plan['id'],
            intended_subject=self.rad.id, expires_at=(self.time+timedelta(days=1)).isoformat())
        return self.store.record_decision(self.rad, decision['id'], 1, 'approve', 'new explicit human approval')

    def reviewer(self):
        self.store.set_role(self.rad, 'claude', {'model':'claude','family':'anthropic','role':'senior'})
        return Principal('claude','worker')

    def test_1_draft_does_not_freeze_approved_live_claim_or_receipt(self):
        self.next_plan()
        renewed=self.store.renew(self.controller, self.claim,
            lease_until=(datetime.fromisoformat(self.claim['lease_until'])+timedelta(minutes=1)).isoformat())
        self.assertEqual(renewed['id'], self.claim['id'])
        run=self.store.record_run(self.controller, renewed, self.receipt)
        self.assertEqual(run['closeout_validation'], 'valid')
        task=next(t for t in self.store.snapshot()['tasks'] if t['id']==self.task['id'])
        self.assertEqual((task['state'],task['attempts']), ('review',1))
        self.assertEqual(self.store.snapshot()['incidents'], [])

    def test_1_draft_does_not_freeze_reviewed_result_acceptance(self):
        self.store.record_run(self.controller,self.claim,self.receipt)
        reviewed=self.store.record_review(self.reviewer(),self.task['id'],3,'pass',['review evidence'])
        self.next_plan()
        result=self.store.accept_result(self.rad,self.task['id'],reviewed['revision'],['accept original result'])
        self.assertEqual(result['state'],'accepted')

    def test_1_approval_explicitly_supersedes_old_plan_and_fences_old_work(self):
        plan=self.next_plan();self.approve(plan)
        plans={p['id']:p for p in self.store.snapshot()['plans']}
        self.assertEqual(plans[self.plan['id']]['state'],'superseded')
        self.assertEqual(plans[plan['id']]['state'],'approved')
        with self.assertRaises(RecordError):
            self.store.renew(self.controller,self.claim,lease_until=self.claim['lease_until'])
        self.assertEqual(self.store.snapshot()['tasks'][0]['attempts'],1)
        # Historical approved scope remains exportable after explicit supersession.
        bundle=Path(self.tmp.name)/'superseded.json'
        export_record(self.path,bundle)
        restore_record(bundle,Path(self.tmp.name)/'superseded.sqlite3',controller_stopped=True)

    def test_1_stale_card_still_rejected_when_newer_draft_exists(self):
        draft=self.next_plan()
        card=self.store.create_decision(self.controller,draft['id'],intended_subject=self.rad.id,
                                       expires_at=(self.time+timedelta(days=1)).isoformat())
        self.next_plan()
        with self.assertRaises(RecordError):
            self.store.record_decision(self.rad,card['id'],1,'approve','stale card')

    def test_2_needs_decision_preserves_request_without_automatic_retry(self):
        request='Asking: choose the scope. Why now: work awaits that choice.'
        closeout={**self.closeout,'status':'needs-decision','next':request}
        run=self.store.record_run(self.controller,self.claim,{**self.receipt,'closeout':closeout})
        snapshot=self.store.snapshot();task=snapshot['tasks'][0]
        self.assertEqual(task['state'],'needs_decision')
        self.assertEqual(json.loads(run['closeout'])['next'],request)
        self.assertEqual(snapshot['claims'][0]['state'],'closed')
        self.assertEqual(snapshot['incidents'],[])
        self.assertEqual(snapshot['incident_attempts'],[])
        self.assertEqual((task['attempts'],len(snapshot['runs'])),(1,1))
        with self.assertRaises(RecordError):
            self.store.claim(self.controller,task['id'],expected_revision=task['revision'],request_id='unrequested retry')
        bundle=Path(self.tmp.name)/'human-wait.json'
        export_record(self.path,bundle)
        restore_record(bundle,Path(self.tmp.name)/'human-wait.sqlite3',controller_stopped=True)

    def test_2_unknown_exit_is_held_even_when_containment_is_verified(self):
        self.store.record_run(self.controller,self.claim,{**self.receipt,'exit_status':None})
        snapshot=self.store.snapshot();task=snapshot['tasks'][0]
        self.assertEqual(task['state'],'held')
        self.assertEqual(snapshot['claims'][0]['state'],'held')
        self.assertEqual(snapshot['incidents'][0]['state'],'held')
        self.assertIsNone(snapshot['runs'][0]['exit_status'])
        with self.assertRaises(RecordError):
            self.store.claim(self.controller,task['id'],expected_revision=task['revision'],request_id='uncertain retry')
        self.assertEqual(len(snapshot['runs']),1)

    def test_3_completed_reconciliation_preserves_receipt_end_and_records_its_own_time(self):
        self.store.record_run(self.controller,self.claim,
            {**self.receipt,'containment_state':'unconfirmed','termination_evidence':[]})
        self.time+=timedelta(minutes=3)
        self.store.reconcile(self.controller,self.claim['run_id'],termination_evidence=['verified later'],outcome='completed')
        run=self.store.snapshot()['runs'][0]
        self.assertEqual(run['ended_at'],self.receipt['ended_at'])
        self.assertEqual(json.loads(run['termination_evidence'])['reconciled_at'],self.time.isoformat())

    def test_4a_revision_requires_integer_even_when_float_equals_counter(self):
        self.store.record_run(self.controller,self.claim,self.receipt)
        changed=self.store.record_review(self.reviewer(),self.task['id'],3,'changes',['revise'])
        for value in [True,float(changed['revision'])]:
            with self.subTest(value=value),self.assertRaises(RecordError):
                self.store.revise_task(self.controller,self.task['id'],value,'not an integer')

    def test_4b_missing_source_identity_is_sanitized_by_restore_cli(self):
        bundle=Path(self.tmp.name)/'no-source.json';target=Path(self.tmp.name)/'restored.sqlite3'
        export_record(self.path,bundle)
        data=json.loads(bundle.read_text());data['manifest'].pop('instance_id');bundle.write_text(json.dumps(data))
        env={**os.environ,'PYTHONPATH':str(Path(__file__).parents[1]/'mcp/memory')}
        result=subprocess.run([sys.executable,'-m','hearth2','restore','--database',str(target),
            '--bundle',str(bundle),'--controller-stopped'],env=env,capture_output=True,text=True)
        self.assertEqual(result.returncode,1)
        self.assertNotIn('Traceback',result.stderr)
        self.assertIn('Operation refused',result.stderr)
        self.assertFalse(target.exists())

    def test_4c_idempotent_replay_refuses_closed_claim(self):
        self.store.record_run(self.controller,self.claim,self.receipt)
        with self.assertRaises(RecordError):
            self.store.claim(self.controller,self.task['id'],expected_revision=1,request_id='receipt')

    def test_4c_idempotent_replay_refuses_held_claim(self):
        self.store.reconcile(self.controller,self.claim['run_id'],termination_evidence=[],outcome='unknown')
        with self.assertRaises(RecordError):
            self.store.claim(self.controller,self.task['id'],expected_revision=1,request_id='receipt')

    def test_4c_idempotent_replay_refuses_expired_claim(self):
        self.time+=timedelta(minutes=16)
        with self.assertRaises(RecordError):
            self.store.claim(self.controller,self.task['id'],expected_revision=1,request_id='receipt')

    def test_2_delayed_containment_of_human_wait_reconciles_without_retry(self):
        closeout={**self.closeout,'status':'needs-decision','next':'Rad must choose the scope'}
        self.store.record_run(self.controller,self.claim,{**self.receipt,'closeout':closeout,
            'containment_state':'unconfirmed','termination_evidence':[]})
        result=self.store.reconcile(self.controller,self.claim['run_id'],
            termination_evidence=['verified empty later'],outcome='completed')
        self.assertEqual((result['state'],result['attempts']),('needs_decision',1))
        self.assertEqual(self.store.snapshot()['runs'][0]['ended_at'],self.receipt['ended_at'])
        with self.assertRaises(RecordError):
            self.store.claim(self.controller,result['id'],expected_revision=result['revision'],request_id='blind retry')
        bundle=Path(self.tmp.name)/'reconciled-human-wait.json'
        export_record(self.path,bundle)
        restore_record(bundle,Path(self.tmp.name)/'reconciled-human-wait.sqlite3',controller_stopped=True)

    def test_2_failed_reconciliation_does_not_retry_preserved_human_request(self):
        closeout={**self.closeout,'status':'needs-decision','next':'Rad must choose the scope'}
        self.store.record_run(self.controller,self.claim,{**self.receipt,'closeout':closeout,'exit_status':9,
            'containment_state':'unconfirmed','termination_evidence':[]})
        result=self.store.reconcile(self.controller,self.claim['run_id'],
            termination_evidence=['verified failed process stopped'],outcome='failed')
        self.assertEqual(result['state'],'needs_decision')
        self.assertEqual(self.store.snapshot()['incidents'][0]['state'],'escalated')
        with self.assertRaises(RecordError):
            self.store.claim(self.controller,result['id'],expected_revision=result['revision'],request_id='blind retry')
