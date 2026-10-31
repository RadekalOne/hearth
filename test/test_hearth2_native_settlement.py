"""Native output, trusted exit and authoritative record commit as one closeout."""
from datetime import timedelta
import json
from pathlib import Path
import unittest
from unittest.mock import patch
import test_hearth2_claims as fixtures
from hearth2.store import RecordError,Store
from hearth2.dispatch import DispatchRegistry
from hearth2.backup import export_record,restore_record


class NativeSettlementTests(unittest.TestCase):
    def setUp(self):
        fixtures.ClaimTests.setUp(self)
        self.registry=DispatchRegistry(self.store,self.controller)
        self.assertTrue(callable(getattr(self.registry,'record_native_result',None)),
                        'native result settlement is not implemented')
        bound=self.registry.claim_and_prepare(self.task['id'],expected_revision=1,
            request_id='native-one',expected_role_revision=1,policy_sha256='a'*64)
        self.claim=bound['claim'];self.registry.consume(self.claim)
        self.time+=timedelta(seconds=1)

    def result(self,state='completed',**changes):
        closeout={'task':self.task['id'],'attempt':1,'status':'done','produced':'fixture',
            'changed':'fixture','unblocked':'none','memory-used':['drawer_fixture'],
            'checks-run':[{'name':'Done check','passed':True,'evidence':'fixture'}],
            'next':'independent review'}
        stop=state if state.endswith('_stop') else None
        result={'provider':'openai','state':state,'text':json.dumps(closeout),
                'stop_reason':stop,'pause_role':stop is not None,'usage_scope':'unknown',
                'usage':{'state':'unknown','units':None,'estimated_cost':None,'actual_charge':None}}
        result.update(changes);return result

    def settle(self,result=None,**changes):
        fields={'ended_at':self.time.isoformat(),'exit_status':0,
                'containment_state':'verified_empty','termination_evidence':['outside-empty']}
        fields.update(changes)
        return self.registry.record_native_result(self.claim,result or self.result(),**fields)

    def test_completed_output_requires_real_exit_and_empty_evidence_to_reach_review(self):
        finished=self.settle()
        self.assertEqual(finished['registration']['phase'],'released')
        self.assertEqual(self.store.snapshot()['tasks'][0]['state'],'review')
        self.assertEqual(json.loads(finished['run']['data'])['native_state'],'completed')
        self.assertIsNone(finished['run']['actual_charge'])

    def test_unknown_output_preserves_known_exit_and_holds_without_retry(self):
        finished=self.settle(self.result('unknown'))
        self.assertEqual(finished['run']['exit_status'],0)
        self.assertEqual(finished['run']['containment_state'],'verified_empty')
        self.assertEqual(self.store.snapshot()['tasks'][0]['state'],'held')
        self.assertEqual(finished['registration']['phase'],'launching')
        with self.assertRaises(RecordError):self.registry.release(self.claim['run_id'])
        self.assertEqual(self.store.snapshot()['tasks'][0]['attempts'],1)

    def test_typed_native_stop_pauses_role_and_prevents_another_attempt(self):
        result=self.result('allowance_stop')
        finished=self.settle(result)
        snapshot=self.store.snapshot()
        self.assertEqual(snapshot['tasks'][0]['state'],'ready')
        self.assertEqual(snapshot['role_grants'][0]['state'],'paused')
        self.assertEqual(snapshot['role_grants'][0]['revision'],2)
        self.assertEqual(finished['registration']['phase'],'released')
        self.assertEqual(self.registry.pending(),[])
        before=self.store.snapshot()
        self.assertEqual(self.settle(result),finished)
        self.assertEqual(self.store.snapshot(),before)
        with self.assertRaises(RecordError):
            self.registry.claim_and_prepare(self.task['id'],expected_revision=2,
                request_id='native-two',expected_role_revision=2,policy_sha256='a'*64)
        self.assertEqual(self.store.snapshot()['tasks'][0]['attempts'],1)

    def test_unknown_output_after_observed_limit_keeps_both_task_and_role_held(self):
        self.settle(self.result('unknown',stop_reason='allowance_stop',pause_role=True))
        snapshot=self.store.snapshot()
        self.assertEqual(snapshot['tasks'][0]['state'],'held')
        self.assertEqual(snapshot['role_grants'][0]['state'],'paused')
        self.assertEqual(len(self.registry.pending()),1)

    def test_unknown_exit_or_unconfirmed_containment_cannot_be_cleared_by_native_success(self):
        self.settle(exit_status=None)
        self.assertEqual(self.store.snapshot()['tasks'][0]['state'],'held')
        self.assertEqual(len(self.registry.pending()),1)

    def test_mismatched_provider_invalid_stop_or_invented_charge_refuses_without_mutation(self):
        before=self.store.snapshot()
        for changes in [{'provider':'anthropic'},{'pause_role':True},
                        {'state':'unknown-new-state'}, {'stop_reason':'purchase-more'},
                        {'usage':{'state':'unknown','units':None,'estimated_cost':None,
                                  'actual_charge':{'amount':1,'currency':'USD','source':'worker claim'}}}]:
            with self.subTest(changes=changes),self.assertRaises(RecordError):
                self.settle(self.result(**changes))
        self.assertEqual(self.store.snapshot(),before)

    def test_role_pause_write_failure_rolls_back_receipt_release_and_pause(self):
        before=self.store.snapshot();original=self.store.audit
        def fail_pause(db,actor,entity,action,data):
            if action=='native_role_paused':raise RecordError('injected journal failure')
            return original(db,actor,entity,action,data)
        with patch.object(self.store,'audit',side_effect=fail_pause):
            with self.assertRaises(RecordError):self.settle(self.result('rate_limit_stop'))
        self.assertEqual(self.store.snapshot(),before)

    def test_pause_and_unknown_output_history_survive_export_restore(self):
        self.settle(self.result('unknown',stop_reason='allowance_stop',pause_role=True))
        bundle,target=Path(self.tmp.name)/'native.json',Path(self.tmp.name)/'restored.db'
        export_record(self.path,bundle);restore_record(bundle,target,controller_stopped=True)
        restored=Store(target,clock=lambda:self.time).snapshot()
        self.assertEqual(restored['tasks'][0]['state'],'held')
        self.assertEqual(restored['role_grants'][0]['state'],'paused')
        self.assertEqual(json.loads(restored['runs'][0]['data'])['native_state'],'unknown')

    def test_success_looking_closeout_cannot_override_unknown_native_protocol(self):
        receipt={'ended_at':self.time.isoformat(),'exit_status':0,
                 'closeout':json.loads(self.result()['text']),'containment_state':'verified_empty',
                 'termination_evidence':['outside-empty'],'usage':self.result()['usage'],
                 'native_state':'unknown','native_stop_reason':None,'native_usage_scope':'unknown'}
        self.registry.record_and_release(self.claim,receipt)
        before=self.store.snapshot()
        with self.assertRaises(RecordError):
            self.store.reconcile(self.controller,self.claim['run_id'],
                                 outcome='completed',termination_evidence=['fresh-empty'])
        self.assertEqual(self.store.snapshot(),before)

    def test_restore_refuses_unknown_native_state_even_when_body_claims_completed(self):
        from test_hearth2_backup import BackupTests
        self.settle()
        bundle,target=Path(self.tmp.name)/'forged.json',Path(self.tmp.name)/'target.db'
        export_record(self.path,bundle);value=json.loads(bundle.read_text())
        data=json.loads(value['tables']['runs'][0]['data']);data['native_state']='unknown'
        value['tables']['runs'][0]['data']=json.dumps(data)
        BackupTests.rehash(value);bundle.write_text(json.dumps(value))
        with self.assertRaises(RecordError):restore_record(bundle,target,controller_stopped=True)
        self.assertFalse(target.exists())

    def test_real_stream_decoder_to_record_preserves_task_and_receipt_binding(self):
        from hearth2.native_output import NativeStream
        stream=NativeStream('codex',thread_id='thread-one',turn_id='turn-one')
        event={'method':'turn/completed','params':{'threadId':'thread-one',
            'turn':{'id':'turn-one','status':'completed','error':None,'items':[
                {'id':'final','type':'agentMessage','phase':'final_answer','text':self.result()['text']}]}}}
        stream.feed(json.dumps(event).encode()+b'\n')
        finished=self.settle(stream.finish())
        self.assertEqual(self.store.snapshot()['tasks'][0]['state'],'review')
        self.assertEqual(finished['run']['task_id'],self.task['id'])
        self.assertEqual(finished['run']['usage_state'],'unknown')

    def test_stream_allowance_stop_is_atomically_persisted_as_a_role_pause(self):
        from hearth2.native_output import NativeStream
        stream=NativeStream('codex',thread_id='thread-one',turn_id='turn-one')
        event={'method':'error','params':{'threadId':'thread-one','turnId':'turn-one',
               'error':{'message':'synthetic limit','codexErrorInfo':'usageLimitExceeded'},'willRetry':True}}
        stream.feed(json.dumps(event).encode()+b'\n')
        finished=self.settle(stream.finish(),exit_status=137)
        self.assertEqual(self.store.snapshot()['role_grants'][0]['state'],'paused')
        self.assertEqual(json.loads(finished['run']['data'])['native_stop_reason'],'allowance_stop')
        self.assertEqual(self.registry.pending(),[])

    def test_native_success_never_overrides_unconfirmed_os_containment(self):
        finished=self.settle(containment_state='unconfirmed',termination_evidence=[])
        self.assertEqual(self.store.snapshot()['tasks'][0]['state'],'held')
        self.assertEqual(finished['run']['exit_status'],0)
        self.assertEqual(len(self.registry.pending()),1)

    def test_deeply_nested_closeout_text_cannot_crash_or_discard_observed_exit(self):
        text='{"x":'+'['*2000+'0'+']'*2000+'}'
        finished=self.settle(self.result(text=text))
        self.assertEqual(finished['run']['exit_status'],0)
        self.assertEqual(finished['run']['containment_state'],'verified_empty')
        self.assertEqual(finished['run']['closeout_validation'],'missing')
        self.assertEqual(self.store.snapshot()['tasks'][0]['state'],'ready')
        self.assertEqual(self.registry.pending(),[])

    def test_malformed_closeout_status_is_invalid_instead_of_crashing_settlement(self):
        closeout=json.loads(self.result()['text']);closeout['status']=[]
        finished=self.settle(self.result(text=json.dumps(closeout)))
        self.assertEqual(finished['run']['closeout_validation'],'invalid')
        self.assertEqual(finished['run']['exit_status'],0)
        self.assertEqual(self.store.snapshot()['tasks'][0]['state'],'ready')


if __name__=='__main__':unittest.main()
