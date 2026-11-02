"""Original host/immutable container survive restart and fence recovery."""
from datetime import timedelta
import importlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch
import test_hearth2_claims as fixtures
from hearth2.store import Store, Principal, RecordError
from hearth2.dispatch import DispatchRegistry
from hearth2.recovery import RecoveryCoordinator
from hearth2.backup import export_record, restore_record


class CreationBindingTests(unittest.TestCase):
    def setUp(self):
        fixtures.ClaimTests.setUp(self)
        self.registry = DispatchRegistry(self.store, self.controller)
        self.claim = self.store.claim(self.controller, self.task['id'],
            expected_revision=1, request_id='creation-first')
        self.registration = self.registry.prepare(self.claim, policy_sha256='a'*64)
        self.assertIsNotNone(importlib.util.find_spec('hearth2.creation'),
                             'immutable creation binding missing')
        self.binding_type = importlib.import_module('hearth2.creation').CreationRegistry
        self.bindings = self.binding_type(self.registry)

    def bind(self, **changes):
        args = dict(registration=self.registration, claim=self.claim,
                    host_id='1'*64, container_id='b'*64)
        return self.bindings.bind(**{**args, **changes})

    def launch(self):
        binding = self.bind()
        self.registration = self.bindings.consume_armed(self.claim, binding, proof=self.arm_proof(binding))
        self.time += timedelta(seconds=901)
        return binding

    def arm_proof(self, binding):
        return {key:binding[key] for key in ['host_id','container_id','workload_id',
            'guard_id','parent_cgroup','deadline_at','policy_sha256']} | {
                'observed_at':self.time.isoformat(), 'guard_state':'armed',
                'container_state':'created', 'references':['root:PID1-guard-verified-stopped-ID']}

    def packet(self):
        return {'recovery_id':'bound-recovery', 'observation':{
            'observation_id':'bound-observation', 'host_id':'1'*64,
            'workload_id':self.registration['workload_id'], 'container_id':'b'*64,
            'observed_at':self.time.isoformat(),
            'ended_at':(self.time-timedelta(seconds=1)).isoformat(),
            'exit_status':137, 'containment_state':'verified_empty',
            'termination_evidence':['original-host:kernel-empty']},
            'removal':{'host_id':'1'*64, 'container_id':'b'*64,
                'workload_id':self.registration['workload_id'],
                'observed_at':self.time.isoformat(), 'references':['original-host:ID-absent']},
            'classification_evidence':['root:deadline']}

    def recover(self, proof=None, store=None):
        store = store or self.store
        with store.transaction() as db:
            epoch = db.execute('SELECT restore_epoch FROM record_meta WHERE id=1').fetchone()[0]
            generation = store.row(db, 'claims', self.claim['id'])['generation']
        return RecoveryCoordinator(DispatchRegistry(store, self.controller)).recover(
            self.registration, expected_epoch=epoch, expected_generation=generation,
            outcome='failed', proof=proof or self.packet())

    def test_binding_persists_original_identity_and_is_read_only_on_restart_replay(self):
        bound = self.bind(); before = self.store.snapshot()
        self.bindings = self.binding_type(DispatchRegistry(
            Store(self.path, clock=lambda:self.time), self.controller))
        self.assertEqual(self.bind(), bound)
        self.assertEqual(self.bindings.read(self.claim['run_id']), bound)
        self.assertEqual(self.store.snapshot(), before)
        for key in ['run_id','claim_id','workload_id','deadline_at','policy_sha256']:
            self.assertEqual(bound[key], self.registration[key])
        self.assertEqual(bound['creation_epoch'], self.claim['restore_epoch'])
        self.assertEqual(bound['host_id'], '1'*64)
        self.assertEqual(bound['container_id'], 'b'*64)
        self.assertTrue(bound['guard_id'].startswith('hearth2-deadline-'))

    def test_rebinding_host_or_container_is_refused_without_mutation(self):
        self.bind(); before = self.store.snapshot()
        for changes in [{'host_id':'2'*64}, {'container_id':'c'*64}]:
            with self.subTest(changes=changes), self.assertRaises(RecordError):self.bind(**changes)
        self.assertEqual(self.store.snapshot(), before)

    def test_binding_requires_exact_reserved_live_owned_registration(self):
        before = self.store.snapshot()
        with self.assertRaises(RecordError):
            self.bind(registration={**self.registration,'seq':self.registration['seq']-1})
        other = self.binding_type(DispatchRegistry(self.store, Principal('other','controller')))
        with self.assertRaises(RecordError):
            other.bind(self.registration, self.claim, host_id='1'*64, container_id='b'*64)
        self.assertEqual(self.store.snapshot(), before)
        self.registry.consume(self.claim)
        with self.assertRaises(RecordError):self.bind()

    def test_expired_unbound_claim_cannot_seal_a_new_identity(self):
        self.time += timedelta(seconds=901); before = self.store.snapshot()
        with self.assertRaises(RecordError):self.bind()
        self.assertEqual(self.store.snapshot(), before)

    def test_malformed_host_and_container_ids_never_enter_backup(self):
        before = self.store.snapshot()
        for value in [None, False, '', '../host', 'A'*64, 'a'*65]:
            for key in ['host_id','container_id']:
                with self.subTest(key=key,value=value), self.assertRaises(RecordError):
                    self.bind(**{key:value})
        self.assertEqual(self.store.snapshot(), before)

    def test_binding_audit_failure_rolls_back_and_retry_can_seal_once(self):
        original = self.store.audit; before = self.store.snapshot()
        def fail(db, actor, entity, action, data=None):
            original(db, actor, entity, action, data)
            if action == 'creation_bound':raise RuntimeError('disk failure after append')
        with patch.object(self.store,'audit',side_effect=fail), self.assertRaises(RuntimeError):self.bind()
        self.assertEqual(self.store.snapshot(), before)
        self.assertEqual(self.bind()['container_id'], 'b'*64)

    def restored(self):
        bundle = Path(self.tmp.name)/'creation.json'; target = Path(self.tmp.name)/'restored.db'
        export_record(self.path, bundle); restore_record(bundle, target, controller_stopped=True)
        return Store(target, clock=lambda:self.time)

    def test_restore_keeps_original_guard_epoch_host_and_refuses_rebinding(self):
        bound = self.bind(); store = self.restored()
        restored = self.binding_type(DispatchRegistry(store, self.controller))
        self.assertEqual(restored.read(self.claim['run_id']), bound)
        with self.assertRaises(RecordError):
            restored.bind(self.registration, self.claim, host_id='2'*64, container_id='c'*64)
        with self.assertRaises(RecordError):
            restored.bind(self.registration, self.claim, host_id='1'*64, container_id='b'*64)

    def test_original_host_known_failure_recovers_and_replay_is_read_only(self):
        bound = self.launch(); result = self.recover()
        self.assertEqual(result['registration']['phase'],'released')
        self.assertEqual(result['task']['state'],'ready')
        self.assertEqual(result['task']['attempts'],1)
        before = self.store.snapshot()
        self.assertEqual(self.recover(), result)
        self.assertEqual(self.store.snapshot(), before)
        self.assertEqual(self.bindings.read(self.claim['run_id']), bound)

    def test_new_host_absence_after_restore_cannot_release_original_host_slot(self):
        self.launch(); store = self.restored(); before = store.snapshot()
        proof = self.packet()
        proof['observation']['host_id'] = '2'*64
        proof['removal']['host_id'] = '2'*64
        with self.assertRaises(RecordError):self.recover(proof,store)
        self.assertEqual(store.snapshot(),before)
        self.assertEqual(self.recover(store=store)['registration']['phase'],'released')

    def test_bound_recovery_requires_original_host_on_both_independent_proofs(self):
        self.launch(); before = self.store.snapshot()
        for part in ['observation','removal']:
            for value in [None,'2'*64]:
                proof = self.packet()
                if value is None:del proof[part]['host_id']
                else:proof[part]['host_id'] = value
                with self.subTest(part=part,value=value), self.assertRaises(RecordError):self.recover(proof)
        self.assertEqual(self.store.snapshot(),before)

    def test_bound_recovery_refuses_matching_but_unsealed_container(self):
        self.launch(); before = self.store.snapshot(); proof = self.packet()
        proof['observation']['container_id'] = 'c'*64
        proof['removal']['container_id'] = 'c'*64
        with self.assertRaises(RecordError):self.recover(proof)
        self.assertEqual(self.store.snapshot(),before)

    def test_os_only_observation_cannot_introduce_unsealed_host_or_container(self):
        self.launch(); before = self.store.snapshot()
        for changes in [{'host_id':'2'*64}, {'container_id':'c'*64}, {'host_id':None}]:
            proof = {**self.packet()['observation'], **changes}
            with self.subTest(changes=changes),self.assertRaises(RecordError):
                self.registry.observe_termination(self.registration,
                    expected_epoch=self.claim['restore_epoch'],
                    expected_generation=self.claim['generation'],observation=proof)
        self.assertEqual(self.store.snapshot(),before)
        run = self.registry.observe_termination(self.registration,
            expected_epoch=self.claim['restore_epoch'],expected_generation=self.claim['generation'],
            observation=self.packet()['observation'])
        self.assertEqual(json.loads(run['data'])['os_observation']['host_id'],'1'*64)
        self.assertEqual(len(self.registry.pending()),1)

    def test_bound_plain_consume_cannot_bypass_guard_attestation(self):
        self.bind(); before = self.store.snapshot()
        with self.assertRaises(RecordError):self.registry.consume(self.claim)
        self.assertEqual(self.store.snapshot(), before)

    def test_arm_consume_commits_once_and_restart_cannot_reissue_start_authority(self):
        bound = self.bind()
        result = self.bindings.consume_armed(self.claim, bound, proof=self.arm_proof(bound))
        self.assertEqual(result['phase'],'launching')
        before = self.store.snapshot()
        restarted = self.binding_type(DispatchRegistry(Store(self.path, clock=lambda:self.time),self.controller))
        with self.assertRaises(RecordError):
            restarted.consume_armed(self.claim, bound, proof=self.arm_proof(bound))
        self.assertEqual(self.store.snapshot(), before)
        self.assertEqual(restarted.read(self.claim['run_id'])['guard_id'],bound['guard_id'])

    def test_arm_attestation_cannot_change_guard_parent_deadline_host_or_policy(self):
        bound = self.bind(); before = self.store.snapshot()
        for changes in [{'guard_id':'another'}, {'parent_cgroup':'another'},
                {'deadline_at':(self.time+timedelta(days=1)).isoformat()}, {'host_id':'2'*64},
                {'container_id':'c'*64}, {'policy_sha256':'c'*64},
                {'container_state':'running'}, {'guard_state':'inactive'}, {'references':[]}]:
            proof = {**self.arm_proof(bound), **changes}
            with self.subTest(changes=changes), self.assertRaises(RecordError):
                self.bindings.consume_armed(self.claim, bound, proof=proof)
        self.assertEqual(self.store.snapshot(), before)

    def test_arm_attestation_expired_future_or_before_binding_is_refused(self):
        bound = self.bind(); before = self.store.snapshot()
        for observed in [self.time-timedelta(seconds=1), self.time+timedelta(seconds=1)]:
            with self.subTest(observed=observed), self.assertRaises(RecordError):
                self.bindings.consume_armed(self.claim, bound,
                    proof={**self.arm_proof(bound),'observed_at':observed.isoformat()})
        self.time += timedelta(seconds=61)
        with self.assertRaises(RecordError):
            self.bindings.consume_armed(self.claim, bound,
                proof={**self.arm_proof(bound),'observed_at':(self.time-timedelta(seconds=61)).isoformat()})
        self.assertEqual(self.store.snapshot(), before)

    def test_arm_and_consume_audit_failure_is_atomic_and_does_not_disarm(self):
        bound = self.bind(); original = self.store.audit; before = self.store.snapshot()
        for action_to_fail in ['creation_armed', 'dispatch']:
            def fail(db, actor, entity, action, data=None):
                original(db, actor, entity, action, data)
                if action == action_to_fail:raise RuntimeError('disk failure')
            with self.subTest(action=action_to_fail), patch.object(self.store,'audit',side_effect=fail):
                with self.assertRaises(RuntimeError):
                    self.bindings.consume_armed(self.claim,bound,proof=self.arm_proof(bound))
            self.assertEqual(self.store.snapshot(), before)
        # Only a fresh independent attestation can authorize another attempt.
        self.assertEqual(self.bindings.consume_armed(self.claim,bound,
            proof=self.arm_proof(bound))['phase'],'launching')

    def test_restore_or_role_change_cannot_use_old_guard_to_start(self):
        bound = self.bind(); store = self.restored()
        restored = self.binding_type(DispatchRegistry(store,self.controller))
        before = store.snapshot()
        with self.assertRaises(RecordError):
            restored.consume_armed(self.claim,bound,proof=self.arm_proof(bound))
        self.assertEqual(store.snapshot(), before)
        self.store.set_role(self.rad,'codex',{**self.role,'state':'paused'})
        before = self.store.snapshot()
        with self.assertRaises(RecordError):
            self.bindings.consume_armed(self.claim,bound,proof=self.arm_proof(bound))
        self.assertEqual(self.store.snapshot(), before)


if __name__ == '__main__':unittest.main()
