"""Late OS observations never become late worker closeouts or launch authority."""
from datetime import timedelta
import json
from pathlib import Path
import unittest
from unittest.mock import patch
import test_hearth2_claims as fixtures
from hearth2.dispatch import DispatchRegistry
from hearth2.store import RecordError,Store,Principal
from hearth2.backup import export_record,restore_record


class TerminationObservationTests(unittest.TestCase):
    def setUp(self):
        fixtures.ClaimTests.setUp(self)
        self.registry=DispatchRegistry(self.store,self.controller)
        self.assertTrue(callable(getattr(self.registry,'observe_termination',None)),
                        'trusted OS-only observation path missing')
        self.claim=self.store.claim(self.controller,self.task['id'],expected_revision=1,request_id='os-observe')
        self.registry.prepare(self.claim,policy_sha256='a'*64)
        self.registration=self.registry.consume(self.claim)
        self.epoch=self.claim['restore_epoch']
        self.time+=timedelta(seconds=901)

    def observation(self,**changes):
        value={'observation_id':'observation-one','workload_id':self.registration['workload_id'],
            'container_id':'b'*64,'observed_at':self.time.isoformat(),
            'ended_at':(self.time-timedelta(seconds=1)).isoformat(),'exit_status':137,
            'containment_state':'verified_empty','termination_evidence':['root-observer:actual-empty']}
        return {**value,**changes}

    def observe(self,**changes):
        return self.registry.observe_termination(self.registration,expected_epoch=self.epoch,expected_generation=self.claim['generation'],
                                                  observation=self.observation(**changes))

    def test_expired_ordinary_receipt_refuses_but_os_exit_is_retained_without_success_or_release(self):
        receipt={'ended_at':self.time.isoformat(),'exit_status':0,'closeout':None,
            'containment_state':'verified_empty','termination_evidence':['old-worker'],'usage':{'state':'unknown','units':None}}
        with self.assertRaises(RecordError):self.store.record_run(self.controller,self.claim,receipt)
        before=self.store.snapshot();run=self.observe();after=self.store.snapshot()
        self.assertEqual(run['exit_status'],137)
        self.assertEqual(run['ended_at'],self.observation()['ended_at'])
        self.assertEqual(json.loads(run['data'])['native_state'],'unknown')
        self.assertIsNone(run['closeout']);self.assertEqual(after['tasks'][0]['state'],'held')
        self.assertEqual(after['claims'][0]['state'],'held');self.assertEqual(after['tasks'][0]['attempts'],1)
        self.assertEqual(after['role_grants'],before['role_grants'])
        self.assertEqual(len(self.registry.pending()),1)
        with self.assertRaises(RecordError):self.registry.release(self.claim['run_id'])
        with self.assertRaises(RecordError):self.registry.consume(self.claim)
        with self.assertRaises(RecordError):self.store.reconcile(self.controller,self.claim['run_id'],outcome='completed',termination_evidence=['new-os-proof'])

    def test_unknown_exit_or_unconfirmed_containment_remains_explicit_and_held(self):
        run=self.observe(exit_status=None,ended_at=None,containment_state='unconfirmed',termination_evidence=[])
        self.assertIsNone(run['exit_status']);self.assertIsNone(run['ended_at'])
        self.assertEqual(run['containment_state'],'unconfirmed')
        self.assertEqual(self.store.snapshot()['tasks'][0]['state'],'held')
        self.assertEqual(len(self.registry.pending()),1)

    def test_exact_observation_replay_is_read_only_but_conflicting_same_id_is_refused(self):
        run=self.observe();before=self.store.snapshot()
        self.assertEqual(self.observe(),run);self.assertEqual(self.store.snapshot(),before)
        with self.assertRaises(RecordError):self.observe(exit_status=0)
        self.assertEqual(self.store.snapshot(),before)

    def test_foreign_owner_and_changed_registration_or_workload_identity_are_refused(self):
        before=self.store.snapshot()
        for registration in [{**self.registration,'seq':self.registration['seq']-1},
                {**self.registration,'generation':2},{**self.registration,'workload_id':'other'},
                {**self.registration,'controller':'other'}]:
            with self.assertRaises(RecordError):
                self.registry.observe_termination(registration,expected_epoch=self.epoch,expected_generation=self.claim['generation'],observation=self.observation())
        for actor in [self.worker,self.rad,Principal('other-controller','controller')]:
            with self.assertRaises(RecordError):
                DispatchRegistry(self.store,actor).observe_termination(self.registration,expected_epoch=self.epoch,expected_generation=self.claim['generation'],observation=self.observation())
        with self.assertRaises(RecordError):self.observe(workload_id='other')
        self.assertEqual(self.store.snapshot(),before)

    def test_stale_future_malformed_or_worker_fields_are_refused_without_mutation(self):
        before=self.store.snapshot()
        for changes in [{'observed_at':(self.time-timedelta(seconds=61)).isoformat()},
                {'observed_at':(self.time+timedelta(seconds=1)).isoformat()},
                {'ended_at':(self.time+timedelta(seconds=1)).isoformat()},
                {'ended_at':'not-a-time'},{'exit_status':False},{'container_id':'other'},
                {'termination_evidence':[]},{'closeout':{'status':'done'}},
                {'usage':{'state':'measured','units':{'tokens':0}}},{'observation_id':''}]:
            with self.subTest(changes=changes),self.assertRaises(RecordError):self.observe(**changes)
        self.assertEqual(self.store.snapshot(),before)

    def test_restore_rejects_old_epoch_and_requires_fresh_bound_observation(self):
        self.observe()
        bundle,target=Path(self.tmp.name)/'os.json',Path(self.tmp.name)/'restored.db'
        export_record(self.path,bundle);restore_record(bundle,target,controller_stopped=True)
        store=Store(target,clock=lambda:self.time);registry=DispatchRegistry(store,self.controller)
        with store.transaction() as db:epoch=db.execute('SELECT restore_epoch FROM record_meta WHERE id=1').fetchone()[0]
        self.assertNotEqual(epoch,self.epoch)
        before=store.snapshot()
        with self.assertRaises(RecordError):
            registry.observe_termination(self.registration,expected_epoch=self.epoch,expected_generation=self.claim['generation'],observation=self.observation())
        self.assertEqual(store.snapshot(),before)
        run=registry.observe_termination(self.registration,expected_epoch=epoch,expected_generation=store.snapshot()['claims'][0]['generation'],
            observation=self.observation(observation_id='after-restore'))
        self.assertEqual(run['exit_status'],137)
        self.assertEqual(json.loads(run['data'])['os_observation']['restore_epoch'],epoch)
        self.assertEqual(store.snapshot()['tasks'][0]['state'],'held')
        with self.assertRaises(RecordError):registry.release(self.claim['run_id'])

    def test_actual_known_exit_and_end_from_earlier_receipt_are_preserved(self):
        self.time-=timedelta(seconds=900)
        self.store.record_run(self.controller,self.claim,{'ended_at':self.time.isoformat(),
            'exit_status':137,'closeout':None,'containment_state':'unconfirmed',
            'termination_evidence':[],'usage':{'state':'unknown','units':None},
            'native_state':'unknown','native_stop_reason':None,'native_usage_scope':'unknown'})
        prior=self.store.snapshot()['runs'][0]
        self.time+=timedelta(seconds=901)
        run=self.observe();self.assertEqual(run['ended_at'],prior['ended_at'])
        self.assertEqual(run['exit_status'],137)
        before=self.store.snapshot()
        with self.assertRaises(RecordError):self.observe(observation_id='different-exit',exit_status=0)
        self.assertEqual(self.store.snapshot(),before)

    def test_wrong_current_generation_cannot_observe_or_reuse_pre_restore_authority(self):
        before=self.store.snapshot()
        with self.assertRaises(RecordError):
            self.registry.observe_termination(self.registration,expected_epoch=self.epoch,
                expected_generation=self.claim['generation']+1,observation=self.observation())
        self.assertEqual(self.store.snapshot(),before)

    def test_closed_historical_receipt_cannot_be_rewritten_by_observation(self):
        self.time-=timedelta(seconds=900)
        self.store.record_run(self.controller,self.claim,{'ended_at':self.time.isoformat(),
            'exit_status':137,'closeout':None,'containment_state':'verified_empty',
            'termination_evidence':['earlier-real-exit'],'usage':{'state':'unknown','units':None}})
        self.time+=timedelta(seconds=901)
        before=self.store.snapshot()
        with self.assertRaises(RecordError):self.observe(containment_state='unconfirmed',termination_evidence=[])
        self.assertEqual(self.store.snapshot(),before)

    def test_later_observer_cannot_replace_the_known_immutable_container_identity(self):
        self.observe();before=self.store.snapshot()
        with self.assertRaises(RecordError):self.observe(observation_id='second-container',container_id='c'*64)
        self.assertEqual(self.store.snapshot(),before)

    def test_journal_failure_rolls_back_os_receipt_task_claim_and_incident_together(self):
        before=self.store.snapshot()
        with patch.object(self.store,'audit',side_effect=RuntimeError('simulated journal failure')):
            with self.assertRaises(RuntimeError):self.observe()
        self.assertEqual(self.store.snapshot(),before)


if __name__=='__main__':unittest.main()
