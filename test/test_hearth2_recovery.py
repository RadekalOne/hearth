"""Fresh root OS/removal proofs gate atomic recovery, never worker closeouts."""
from datetime import timedelta
import importlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch
import test_hearth2_termination_observation as fixtures
from hearth2.store import RecordError,Store,Principal
from hearth2.dispatch import DispatchRegistry
from hearth2.backup import export_record,restore_record


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        fixtures.TerminationObservationTests.setUp(self)
        self.assertIsNotNone(importlib.util.find_spec('hearth2.recovery'),'atomic root recovery missing')
        self.coordinator=importlib.import_module('hearth2.recovery').RecoveryCoordinator(self.registry)

    def packet(self,**changes):
        osproof=fixtures.TerminationObservationTests.observation(self)
        value={'recovery_id':'recover-one','observation':osproof,
            'removal':{'container_id':osproof['container_id'],'workload_id':osproof['workload_id'],
                'observed_at':self.time.isoformat(),'references':['root:successful-ID-absence-query']},
            'classification_evidence':['root:deadline-enforced']}
        return {**value,**changes}

    def recover(self,outcome='failed',**changes):
        return self.coordinator.recover(self.registration,expected_epoch=self.epoch,
            expected_generation=self.claim['generation'],outcome=outcome,proof=self.packet(**changes))

    def test_expired_failed_run_records_real_exit_and_releases_atomically(self):
        roles=self.store.snapshot()['role_grants'];result=self.recover()
        self.assertEqual(result['registration']['phase'],'released')
        self.assertEqual(result['run']['exit_status'],137)
        self.assertEqual(result['task']['state'],'ready');self.assertEqual(result['task']['attempts'],1)
        self.assertEqual(self.registry.pending(),[]);self.assertEqual(self.store.snapshot()['role_grants'],roles)
        self.assertEqual(len(self.store.snapshot()['incidents']),1)

    def test_unknown_exit_cannot_be_classified_for_retry_or_release(self):
        proof=self.packet();proof['observation'].update(exit_status=None,ended_at=None)
        before=self.store.snapshot()
        with self.assertRaises(RecordError):self.coordinator.recover(self.registration,expected_epoch=self.epoch,
            expected_generation=self.claim['generation'],outcome='failed',proof=proof)
        self.assertEqual(self.store.snapshot(),before)

    def test_missing_or_mismatched_removal_proof_cannot_release_empty_process_group(self):
        before=self.store.snapshot()
        for removal in [{},{**self.packet()['removal'],'container_id':'c'*64},
                {**self.packet()['removal'],'references':[]},
                {**self.packet()['removal'],'workload_id':'other'}]:
            with self.subTest(removal=removal),self.assertRaises(RecordError):self.recover(removal=removal)
        self.assertEqual(self.store.snapshot(),before)

    def test_unknown_protocol_cannot_be_promoted_to_completed(self):
        before=self.store.snapshot()
        with self.assertRaises(RecordError):self.recover(outcome='completed')
        self.assertEqual(self.store.snapshot(),before)

    def test_zero_exit_with_unknown_protocol_stays_uncertain_without_automatic_retry(self):
        proof=self.packet();proof['observation']['exit_status']=0
        before=self.store.snapshot()
        with self.assertRaises(RecordError):self.recover(observation=proof['observation'])
        self.assertEqual(self.store.snapshot(),before)

    def test_freshness_owner_and_current_context_are_fenced(self):
        before=self.store.snapshot()
        for values in [{'expected_epoch':'old'},{'expected_generation':99},
                {'registration':{**self.registration,'seq':self.registration['seq']-1}}]:
            args={'registration':self.registration,'expected_epoch':self.epoch,
                'expected_generation':self.claim['generation'],'outcome':'failed','proof':self.packet(),**values}
            with self.assertRaises(RecordError):self.coordinator.recover(**args)
        self.time+=timedelta(seconds=61)
        stale=self.packet();stale['observation']['observed_at']=(self.time-timedelta(seconds=61)).isoformat()
        with self.assertRaises(RecordError):self.recover(observation=stale['observation'])
        foreign=importlib.import_module('hearth2.recovery').RecoveryCoordinator(
            DispatchRegistry(self.store,Principal('foreign','controller')))
        with self.assertRaises(RecordError):foreign.recover(self.registration,expected_epoch=self.epoch,
            expected_generation=self.claim['generation'],outcome='failed',proof=self.packet())
        self.assertEqual(self.store.snapshot(),before)

    def test_exact_lost_ack_replay_is_read_only_and_conflict_refused(self):
        proof=self.packet();result=self.recover();before=self.store.snapshot()
        self.time+=timedelta(seconds=61)
        replay=self.coordinator.recover(self.registration,expected_epoch=self.epoch,
            expected_generation=self.claim['generation'],outcome='failed',proof=proof)
        self.assertEqual(replay,result);self.assertEqual(self.store.snapshot(),before)
        with self.assertRaises(RecordError):self.recover(outcome='completed')
        self.assertEqual(self.store.snapshot(),before)

    def test_journal_failure_rolls_back_observation_reconciliation_and_slot_release(self):
        before=self.store.snapshot();audit=self.store.audit
        def fail_recovery(db,actor,entity,action,data=None):
            if action=='dispatch_recovery':raise RuntimeError('simulated recovery journal failure')
            return audit(db,actor,entity,action,data)
        with patch.object(self.store,'audit',side_effect=fail_recovery):
            with self.assertRaises(RuntimeError):self.recover()
        self.assertEqual(self.store.snapshot(),before)

    def test_closed_pre_restore_slot_recovery_preserves_task_run_and_claim_history(self):
        self.store.reconcile(self.controller,self.claim['run_id'],outcome='failed',termination_evidence=['earlier-empty'])
        bundle,target=Path(self.tmp.name)/'closed.json',Path(self.tmp.name)/'closed-restored.db'
        export_record(self.path,bundle);restore_record(bundle,target,controller_stopped=True)
        store=Store(target,clock=lambda:self.time);registry=DispatchRegistry(store,self.controller)
        recovery=importlib.import_module('hearth2.recovery').RecoveryCoordinator(registry)
        with store.transaction() as db:epoch=db.execute('SELECT restore_epoch FROM record_meta WHERE id=1').fetchone()[0]
        before=store.snapshot()
        with self.assertRaises(RecordError):registry.release(self.claim['run_id'])
        result=recovery.recover(self.registration,expected_epoch=epoch,
            expected_generation=before['claims'][0]['generation'],outcome='preserve',proof=self.packet())
        after=store.snapshot()
        for table in ['tasks','runs','claims','role_grants','incidents']:self.assertEqual(after[table],before[table])
        self.assertEqual(result['registration']['phase'],'released');self.assertEqual(registry.pending(),[])

    def test_pre_restore_recovery_packet_cannot_release_after_restore(self):
        proof=self.packet();self.recover()
        bundle,target=Path(self.tmp.name)/'released.json',Path(self.tmp.name)/'released-restored.db'
        export_record(self.path,bundle);restore_record(bundle,target,controller_stopped=True)
        store=Store(target,clock=lambda:self.time)
        recovery=importlib.import_module('hearth2.recovery').RecoveryCoordinator(DispatchRegistry(store,self.controller))
        before=store.snapshot()
        with self.assertRaises(RecordError):recovery.recover(self.registration,expected_epoch=self.epoch,
            expected_generation=self.claim['generation'],outcome='failed',proof=proof)
        self.assertEqual(store.snapshot(),before)

    def successful_receipt(self,status='done'):
        from test_hearth2_native_settlement import NativeSettlementTests
        self.time-=timedelta(seconds=900)
        closeout=json.loads(NativeSettlementTests.result(self)['text']);closeout['status']=status
        self.store.record_run(self.controller,self.claim,{'ended_at':self.time.isoformat(),'exit_status':0,
            'closeout':closeout,'containment_state':'unconfirmed','termination_evidence':[],
            'usage':{'state':'unknown','units':None},'native_state':'completed',
            'native_stop_reason':None,'native_usage_scope':'unknown'})
        self.time+=timedelta(seconds=901)
        proof=self.packet();proof['observation']['exit_status']=0
        return proof

    def test_existing_successful_native_receipt_can_reach_review_with_fresh_os_proof(self):
        proof=self.successful_receipt();prior=self.store.snapshot()['runs'][0]
        result=self.recover(outcome='completed',observation=proof['observation'])
        self.assertEqual(result['task']['state'],'review')
        self.assertEqual(result['run']['ended_at'],prior['ended_at'])
        self.assertEqual(result['registration']['phase'],'released')

    def test_failed_classification_cannot_override_valid_zero_exit_success(self):
        proof=self.successful_receipt();before=self.store.snapshot()
        with self.assertRaises(RecordError):self.recover(outcome='failed',observation=proof['observation'])
        self.assertEqual(self.store.snapshot(),before)

    def test_positive_native_failure_evidence_allows_zero_exit_failure_recovery(self):
        self.time-=timedelta(seconds=900)
        self.store.record_run(self.controller,self.claim,{'ended_at':self.time.isoformat(),'exit_status':0,
            'closeout':None,'containment_state':'unconfirmed','termination_evidence':[],
            'usage':{'state':'unknown','units':None},'native_state':'failed',
            'native_stop_reason':None,'native_usage_scope':'unknown'})
        self.time+=timedelta(seconds=901)
        proof=self.packet();proof['observation']['exit_status']=0
        result=self.recover(outcome='failed',observation=proof['observation'])
        self.assertEqual(result['task']['state'],'ready');self.assertEqual(result['task']['attempts'],1)
        self.assertEqual(result['registration']['phase'],'released')

    def test_same_epoch_closed_slot_preserves_history(self):
        self.store.reconcile(self.controller,self.claim['run_id'],outcome='failed',termination_evidence=['earlier-empty'])
        before=self.store.snapshot();result=self.recover(outcome='preserve');after=self.store.snapshot()
        for table in ['tasks','runs','claims','role_grants','incidents']:self.assertEqual(after[table],before[table])
        self.assertEqual(result['registration']['phase'],'released');self.assertEqual(self.registry.pending(),[])

    def test_needs_decision_receipt_remains_a_human_wait_after_recovery(self):
        proof=self.successful_receipt(status='needs-decision')
        result=self.recover(outcome='completed',observation=proof['observation'])
        self.assertEqual(result['task']['state'],'needs_decision');self.assertEqual(self.registry.pending(),[])
        with self.assertRaises(RecordError):self.registry.claim_and_prepare(self.task['id'],
            expected_revision=result['task']['revision'],request_id='must-not-retry',
            expected_role_revision=1,policy_sha256='a'*64)

    def test_stale_removal_or_missing_classification_evidence_refuses_without_mutation(self):
        before=self.store.snapshot()
        for changes in [{'removal':{**self.packet()['removal'],'observed_at':(self.time-timedelta(seconds=61)).isoformat()}},
                        {'classification_evidence':[]},
                        {'observation':{**self.packet()['observation'],'closeout':{'status':'done'}}}]:
            with self.subTest(changes=changes),self.assertRaises(RecordError):self.recover(**changes)
        self.assertEqual(self.store.snapshot(),before)

    def test_superseded_os_observation_cannot_be_replayed_to_release(self):
        first=self.packet()['observation']
        self.registry.observe_termination(self.registration,expected_epoch=self.epoch,
            expected_generation=self.claim['generation'],observation=first)
        later={**first,'observation_id':'later-uncertain','containment_state':'unconfirmed',
               'termination_evidence':['root:uncertain-later']}
        self.registry.observe_termination(self.registration,expected_epoch=self.epoch,
            expected_generation=self.claim['generation'],observation=later)
        before=self.store.snapshot()
        with self.assertRaises(RecordError):self.recover(observation=first)
        self.assertEqual(self.store.snapshot(),before)

    def test_classifying_failure_does_not_reactivate_a_paused_role(self):
        self.store.set_role(self.rad,'codex',{'model':'changed-model','family':'openai','role':'senior'})
        roles=self.store.snapshot()['role_grants'];result=self.recover()
        self.assertEqual(result['task']['state'],'ready');self.assertEqual(self.store.snapshot()['role_grants'],roles)
        with self.assertRaises(RecordError):self.registry.claim_and_prepare(self.task['id'],
            expected_revision=result['task']['revision'],request_id='paused-must-not-retry',
            expected_role_revision=roles[0]['revision'],policy_sha256='a'*64)

    def test_release_journal_failure_rolls_back_the_whole_recovery(self):
        before=self.store.snapshot();audit=self.store.audit
        def fail_release(db,actor,entity,action,data=None):
            if action=='dispatch' and data.get('phase')=='released':raise RuntimeError('release journal failure')
            return audit(db,actor,entity,action,data)
        with patch.object(self.store,'audit',side_effect=fail_release):
            with self.assertRaises(RuntimeError):self.recover()
        self.assertEqual(self.store.snapshot(),before)

    def test_three_failed_attempts_escalate_without_a_fourth_claim(self):
        for attempt in range(1,4):
            result=self.recover()
            self.assertEqual(result['task']['attempts'],attempt)
            self.assertEqual(result['task']['state'],'ready' if attempt<3 else 'failed')
            if attempt<3:
                bound=self.registry.claim_and_prepare(self.task['id'],expected_revision=result['task']['revision'],
                    request_id='retry-'+str(attempt),expected_role_revision=1,policy_sha256='a'*64)
                self.claim=bound['claim'];self.registration=self.registry.consume(self.claim)
                self.time+=timedelta(seconds=901)
        self.assertEqual(len(self.store.snapshot()['incidents']),1)
        self.assertEqual(self.store.snapshot()['incidents'][0]['state'],'escalated')
        with self.assertRaises(RecordError):self.registry.claim_and_prepare(self.task['id'],
            expected_revision=result['task']['revision'],request_id='forbidden-fourth',
            expected_role_revision=1,policy_sha256='a'*64)

    def test_current_epoch_active_restore_can_recover_but_old_context_cannot(self):
        self.registry.observe_termination(self.registration,expected_epoch=self.epoch,
            expected_generation=self.claim['generation'],observation=self.packet()['observation'])
        bundle,target=Path(self.tmp.name)/'held.json',Path(self.tmp.name)/'held-restored.db'
        export_record(self.path,bundle);restore_record(bundle,target,controller_stopped=True)
        store=Store(target,clock=lambda:self.time);registry=DispatchRegistry(store,self.controller)
        recovery=importlib.import_module('hearth2.recovery').RecoveryCoordinator(registry)
        before=store.snapshot()
        with self.assertRaises(RecordError):recovery.recover(self.registration,expected_epoch=self.epoch,
            expected_generation=self.claim['generation'],outcome='failed',proof=self.packet())
        self.assertEqual(store.snapshot(),before)
        with store.transaction() as db:epoch=db.execute('SELECT restore_epoch FROM record_meta WHERE id=1').fetchone()[0]
        proof=self.packet();proof['observation']['observation_id']='after-held-restore'
        result=recovery.recover(self.registration,expected_epoch=epoch,
            expected_generation=before['claims'][0]['generation'],outcome='failed',proof=proof)
        self.assertEqual(result['registration']['phase'],'released')
        self.assertEqual(result['task']['state'],'ready');self.assertEqual(result['run']['exit_status'],137)


if __name__=='__main__':unittest.main()
