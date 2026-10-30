"""Controller transaction cuts: a slot and its run must commit together."""
from datetime import timedelta
import multiprocessing
import unittest
from unittest.mock import patch
import test_hearth2_claims as fixtures
from hearth2.dispatch import DispatchRegistry
from hearth2.store import Store, Principal, RecordError


def reserve_race(path, task_id, barrier, queue, owner):
    registry = DispatchRegistry(Store(path), Principal(owner, 'controller'))
    try:
        barrier.wait(timeout=10)
        registry.claim_and_prepare(task_id, expected_revision=1, request_id=owner,
                                   expected_role_revision=1, policy_sha256='a'*64)
        queue.put('reserved')
    except RecordError:
        queue.put('refused')


class AtomicDispatchTests(unittest.TestCase):
    def setUp(self):
        fixtures.ClaimTests.setUp(self)
        self.registry = DispatchRegistry(self.store, self.controller)
        self.assertTrue(callable(getattr(self.registry,'claim_and_prepare',None)),
                        'atomic claim and reservation not implemented')
        self.assertTrue(callable(getattr(self.registry,'record_and_release',None)),
                        'atomic receipt and release not implemented')

    def reserve(self, **changes):
        fields = dict(expected_revision=1, request_id='one', expected_role_revision=1,
                      policy_sha256='a'*64)
        fields.update(changes)
        return self.registry.claim_and_prepare(self.task['id'], **fields)

    def receipt(self, claim, **changes):
        receipt = {'ended_at':self.time.isoformat(), 'exit_status':0,
                   'containment_state':'verified_empty', 'termination_evidence':['outside-empty'],
                   'usage':{'state':'unknown','units':None,'estimated_cost':None,'actual_charge':None},
                   'closeout':{'task':self.task['id'],'attempt':claim['attempt'],'status':'done',
                       'produced':'fixture','changed':'fixture','unblocked':'none',
                       'memory-used':['drawer_fixture'],
                       'checks-run':[{'name':'Done check','passed':True,'evidence':'fixture'}],
                       'next':'independent review'}}
        receipt.update(changes)
        return receipt

    def test_atomic_claim_replay_and_role_change_before_claim(self):
        first = self.reserve()
        self.assertEqual(self.reserve(), first)
        self.assertEqual(first['claim']['run_id'], first['registration']['run_id'])
        self.assertEqual(len(self.store.snapshot()['runs']),1)
        with self.assertRaises(RecordError):
            self.reserve(expected_role_revision=2)

    def test_role_changed_after_preflight_consumes_no_attempt(self):
        self.store.set_role(self.rad,'codex',{**self.role,'model':'new-model'})
        before=self.store.snapshot()
        with self.assertRaises(RecordError):
            self.reserve()
        self.assertEqual(self.store.snapshot(),before)
        self.assertEqual(self.store.snapshot()['tasks'][0]['attempts'],0)

    def test_reservation_failure_rolls_back_claim_and_attempt(self):
        before=self.store.snapshot()
        with patch.object(self.registry,'_append',side_effect=RecordError('injected write failure')):
            with self.assertRaises(RecordError):self.reserve()
        self.assertEqual(self.store.snapshot(),before)

    def test_receipt_and_release_commit_together_without_export_window(self):
        result=self.reserve();claim=result['claim'];self.registry.consume(claim)
        self.time+=timedelta(seconds=1)
        finished=self.registry.record_and_release(claim,self.receipt(claim))
        self.assertEqual(finished['run']['closeout_validation'],'valid')
        self.assertEqual(finished['registration']['phase'],'released')
        self.assertEqual(self.registry.pending(),[])
        self.assertEqual(self.store.snapshot()['tasks'][0]['state'],'review')
        before=self.store.snapshot()
        with self.assertRaises(RecordError):
            self.registry.record_and_release(claim,self.receipt(claim))
        self.assertEqual(self.store.snapshot(),before)

    def test_release_failure_rolls_back_receipt_and_claim_closure(self):
        result=self.reserve();claim=result['claim'];self.registry.consume(claim)
        before=self.store.snapshot()
        with patch.object(self.registry,'_append',side_effect=RecordError('injected write failure')):
            with self.assertRaises(RecordError):
                self.registry.record_and_release(claim,self.receipt(claim))
        self.assertEqual(self.store.snapshot(),before)
        self.assertEqual(self.registry.pending()[0]['phase'],'launching')

    def test_unknown_outcome_keeps_slot_and_task_held(self):
        result=self.reserve();claim=result['claim'];self.registry.consume(claim)
        finished=self.registry.record_and_release(claim,self.receipt(claim,exit_status=None))
        self.assertEqual(finished['registration']['phase'],'launching')
        self.assertEqual(self.store.snapshot()['tasks'][0]['state'],'held')
        self.assertEqual(len(self.registry.pending()),1)

    def test_receipt_before_launch_consumption_is_refused_without_state_change(self):
        result=self.reserve();claim=result['claim'];before=self.store.snapshot()
        with self.assertRaises(RecordError):
            self.registry.record_and_release(claim,self.receipt(claim))
        self.assertEqual(self.store.snapshot(),before)

    def test_two_controllers_racing_different_tasks_only_consume_one_attempt(self):
        other=self.store.create_task(self.controller,{**self.payload,'action_id':'parallel'})
        ctx=multiprocessing.get_context('fork');barrier=ctx.Barrier(2);queue=ctx.Queue()
        processes=[ctx.Process(target=reserve_race,args=(self.path,task,barrier,queue,owner))
                   for task,owner in [(self.task['id'],'runner-one'),(other['id'],'runner-two')]]
        for process in processes:process.start()
        results=[queue.get(timeout=15) for _ in processes]
        for process in processes:
            process.join(10);self.assertEqual(process.exitcode,0)
        self.assertEqual(sorted(results),['refused','reserved'])
        snap=self.store.snapshot()
        self.assertEqual(len(snap['runs']),1)
        self.assertEqual(sum(task['attempts'] for task in snap['tasks']),1)


if __name__ == '__main__':
    unittest.main()
