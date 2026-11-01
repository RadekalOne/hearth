"""Synthetic privileged inventory plus real SQLite; never launches a worker."""
from datetime import timedelta
import importlib
import json
import multiprocessing
from pathlib import Path
import unittest
from unittest.mock import patch
import test_hearth2_creation_binding as fixtures
from hearth2.store import Store, RecordError
from hearth2.dispatch import DispatchRegistry
from hearth2.creation import CreationRegistry
from hearth2.backup import export_record, restore_record


class SimulatedCrash(BaseException):
    pass


class InventoryDriver:
    """An actual stateful synthetic inventory, not an OS containment claim."""
    def __init__(self, store):
        self.store = store
        self.steps = []
        self.created = self.started = 0
        self.container = None
        self.guard = None
        self.stop_after = None
        self.tamper_created = {}
        self.tamper_armed = {}
        self.tamper_removal = {}

    def step(self, name):
        self.steps.append(name)
        if self.stop_after == name:raise SimulatedCrash(name)

    def create_stopped(self, intent):
        # A durable pre-create intent must already be externally visible.
        with self.store.transaction() as db:
            row = db.execute("SELECT data FROM audit_events WHERE action='creation_intent' AND entity_id=?",
                             (intent['run_id'],)).fetchone()
            if row is None:raise AssertionError('create before intent commit')
        self.intent = dict(intent)
        self.container = {'id':'b'*64, 'state':'created'}
        self.created += 1
        self.step('create')
        return self.container['id']

    def identity(self, descriptor):
        return {key:descriptor[key] for key in ['host_id','workload_id','guard_id',
            'parent_cgroup','deadline_at','policy_sha256']} | {'container_id':self.container['id']}

    def inspect_created(self, intent, container_id):
        if container_id != self.container['id']:raise AssertionError('wrong immutable ID')
        proof = self.identity(intent) | {'observed_at':self.store.now().isoformat(),
            'container_state':self.container['state'], 'references':['independent:stopped-policy-host']}
        self.step('inspect-created')
        return proof | self.tamper_created

    def arm_guard(self, binding):
        self.guard = dict(binding)
        self.step('arm')

    def inspect_armed(self, binding):
        proof = self.identity(binding) | {'observed_at':self.store.now().isoformat(),
            'container_state':self.container['state'], 'guard_state':'armed' if self.guard else 'inactive',
            'references':['independent:PID1-fixed-timer']}
        self.step('inspect-armed')
        return proof | self.tamper_armed

    def start(self, binding):
        with self.store.transaction() as db:
            registration = DispatchRegistry._latest(db)[binding['run_id']]
            armed = db.execute("SELECT seq FROM audit_events WHERE action='creation_armed' AND entity_id=?",
                               (binding['run_id'],)).fetchone()
            if registration['phase'] != 'launching' or armed is None:
                raise AssertionError('start before atomic guarded consume commit')
        if binding['container_id'] != self.container['id']:raise AssertionError('wrong ID started')
        if self.guard is None:raise AssertionError('unguarded start')
        self.container['state'] = 'running'
        self.started += 1
        self.step('start')

    def inspect_termination(self, binding):
        if self.container is None or self.container['state']!='removed':
            raise RecordError('synthetic original-host container still present')
        self.step('termination')
        observed = self.store.now().isoformat()
        return {'recovery_id':'composed-recovery', 'observation':{
            'observation_id':'composed-observation', 'host_id':binding['host_id'],
            'workload_id':binding['workload_id'], 'container_id':binding['container_id'],
            'observed_at':observed, 'ended_at':observed, 'exit_status':137,
            'containment_state':'verified_empty', 'termination_evidence':['independent:kernel-empty']},
            'removal':{'host_id':binding['host_id'], 'container_id':binding['container_id'],
                'workload_id':binding['workload_id'], 'observed_at':observed,
                'references':['independent:immutable-ID-absent']} | self.tamper_removal,
            'classification_evidence':['root:deadline']}


def race_launch(path, claim, registration, barrier, queue):
    from hearth2.launch import LaunchCoordinator
    store = Store(path); driver = InventoryDriver(store)
    launcher = LaunchCoordinator(DispatchRegistry(store, fixtures.Principal('controller','controller')),driver)
    try:
        barrier.wait(timeout=10)
        launcher.launch(registration,claim,host_id='1'*64)
        result = 'started'
    except RecordError:
        result = 'refused'
    except BaseException as exc:
        result = type(exc).__name__
    queue.put((result,driver.created,driver.started))


class LaunchCompositionTests(unittest.TestCase):
    def setUp(self):
        fixtures.CreationBindingTests.setUp(self)
        self.assertIsNotNone(importlib.util.find_spec('hearth2.launch'),'root launch composition missing')
        self.launch_type = importlib.import_module('hearth2.launch').LaunchCoordinator
        self.driver = InventoryDriver(self.store)
        self.launcher = self.launch_type(self.registry,self.driver)

    def launch(self):
        return self.launcher.launch(self.registration,self.claim,host_id='1'*64)

    def assert_retry_refused(self):
        before = self.store.snapshot(); created = self.driver.created; started = self.driver.started
        restarted = self.launch_type(DispatchRegistry(Store(self.path,clock=lambda:self.time),self.controller),self.driver)
        with self.assertRaises(RecordError):restarted.launch(self.registration,self.claim,host_id='1'*64)
        self.assertEqual(self.driver.created,created);self.assertEqual(self.driver.started,started)
        self.assertEqual(self.store.snapshot(),before)

    def crash_at(self, step):
        self.driver.stop_after = step
        with self.assertRaises(SimulatedCrash):self.launch()
        self.assert_retry_refused()

    def test_intent_precedes_create_and_guarded_consume_precedes_start(self):
        result = self.launch()
        self.assertEqual(self.driver.steps,['create','inspect-created','arm','inspect-armed','start'])
        self.assertEqual(self.driver.started,1)
        self.assertEqual(result['registration']['phase'],'launching')
        self.assertEqual(result['binding']['creation_epoch'],self.claim['restore_epoch'])
        self.assertEqual(self.driver.intent['guard_id'],result['binding']['guard_id'])
        self.assert_retry_refused()

    def test_crash_after_create_does_not_create_again_or_start(self):
        self.crash_at('create');self.assertEqual(self.driver.created,1);self.assertEqual(self.driver.started,0)

    def test_crash_after_created_inspection_requires_inventory_not_adoption(self):
        self.crash_at('inspect-created');self.assertIsNone(self.driver.guard)

    def test_crash_after_arm_keeps_guard_and_refuses_restart(self):
        self.crash_at('arm');self.assertIsNotNone(self.driver.guard);self.assertEqual(self.driver.started,0)

    def test_crash_after_guard_inspection_keeps_guard_and_refuses_restart(self):
        self.crash_at('inspect-armed');self.assertIsNotNone(self.driver.guard)

    def test_crash_after_start_cannot_duplicate_the_workload(self):
        self.crash_at('start');self.assertEqual(self.driver.started,1)

    def test_lost_intent_ack_before_create_is_conservatively_held(self):
        begin = self.launcher.creations.begin
        def lose(*args,**kwargs):begin(*args,**kwargs);raise SimulatedCrash('lost-intent-ack')
        with patch.object(self.launcher.creations,'begin',side_effect=lose),self.assertRaises(SimulatedCrash):self.launch()
        self.assertEqual(self.driver.created,0);self.assert_retry_refused()

    def test_lost_consume_ack_never_starts_or_disarms(self):
        consume = self.launcher.creations.consume_armed
        def lose(*args,**kwargs):consume(*args,**kwargs);raise SimulatedCrash('lost-consume-ack')
        with patch.object(self.launcher.creations,'consume_armed',side_effect=lose),self.assertRaises(SimulatedCrash):self.launch()
        self.assertEqual(self.driver.started,0);self.assertIsNotNone(self.driver.guard)
        self.assertEqual(self.registry.pending()[0]['phase'],'launching');self.assert_retry_refused()

    def test_deadline_after_consume_refuses_start_without_disarming(self):
        consume = self.launcher.creations.consume_armed
        def expire(*args,**kwargs):
            result = consume(*args,**kwargs);self.time += timedelta(hours=3);return result
        with patch.object(self.launcher.creations,'consume_armed',side_effect=expire),self.assertRaises(RecordError):self.launch()
        self.assertEqual(self.driver.started,0);self.assertIsNotNone(self.driver.guard);self.assert_retry_refused()

    def test_changed_role_after_consume_refuses_start(self):
        consume = self.launcher.creations.consume_armed
        def change(*args,**kwargs):
            result = consume(*args,**kwargs)
            self.store.set_role(self.rad,'codex',{**self.role,'model':'different'})
            return result
        with patch.object(self.launcher.creations,'consume_armed',side_effect=change),self.assertRaises(RecordError):self.launch()
        self.assertEqual(self.driver.started,0);self.assertIsNotNone(self.driver.guard)

    def test_wrong_original_host_inspection_cannot_bind(self):
        self.driver.tamper_created = {'host_id':'2'*64}
        with self.assertRaises(RecordError):self.launch()
        self.assertIsNone(self.bindings.read(self.claim['run_id']))
        self.assertIsNone(self.driver.guard);self.assertEqual(self.driver.started,0);self.assert_retry_refused()

    def test_inactive_guard_never_consumes_or_starts(self):
        self.driver.tamper_armed = {'guard_state':'inactive'}
        with self.assertRaises(RecordError):self.launch()
        self.assertEqual(self.registry.pending()[0]['phase'],'reserved')
        self.assertEqual(self.driver.started,0);self.assertIsNotNone(self.driver.guard);self.assert_retry_refused()

    def test_binding_journal_failure_preserves_intent_and_created_container(self):
        original = self.store.audit
        def fail(db,actor,entity,action,data=None):
            original(db,actor,entity,action,data)
            if action=='creation_bound':raise RuntimeError('disk failure')
        with patch.object(self.store,'audit',side_effect=fail),self.assertRaises(RuntimeError):self.launch()
        self.assertEqual(self.driver.created,1);self.assertEqual(self.driver.started,0)
        self.assertIsNone(self.bindings.read(self.claim['run_id']));self.assert_retry_refused()

    def test_preexisting_bound_or_consumed_registration_cannot_start(self):
        self.bind()
        with self.assertRaises(RecordError):self.launch()
        self.assertEqual(self.driver.created,0)

    def bind(self):
        return self.bindings.bind(self.registration,self.claim,host_id='1'*64,container_id='b'*64)

    def test_two_independent_controllers_create_and_start_once(self):
        ctx = multiprocessing.get_context('fork');barrier = ctx.Barrier(2);queue = ctx.Queue()
        processes=[ctx.Process(target=race_launch,args=(self.path,self.claim,self.registration,barrier,queue)) for _ in range(2)]
        for process in processes:process.start()
        results=[queue.get(timeout=20) for _ in processes]
        for process in processes:process.join(10);self.assertEqual(process.exitcode,0)
        self.assertEqual(sorted(value[0] for value in results),['refused','started'])
        self.assertEqual(sum(value[1] for value in results),1);self.assertEqual(sum(value[2] for value in results),1)

    def test_restored_intent_cannot_create_on_new_host(self):
        self.crash_at('create')
        bundle=Path(self.tmp.name)/'launch.json';target=Path(self.tmp.name)/'launch-restored.db'
        export_record(self.path,bundle);restore_record(bundle,target,controller_stopped=True)
        store=Store(target,clock=lambda:self.time);driver=InventoryDriver(store)
        restored=self.launch_type(DispatchRegistry(store,self.controller),driver)
        with self.assertRaises(RecordError):restored.launch(self.registration,self.claim,host_id='2'*64)
        self.assertEqual(driver.created,0);self.assertEqual(driver.started,0)

    def test_composed_recovery_requires_original_host_removal_and_uses_strict_path(self):
        self.launch();self.time += timedelta(seconds=901)
        self.driver.container['state']='removed'  # Separate synthetic outside cleanup.
        before=self.store.snapshot();self.driver.tamper_removal={'host_id':'2'*64}
        with self.assertRaises(RecordError):self.launcher.recover(self.claim['run_id'],outcome='failed')
        self.assertEqual(self.store.snapshot(),before)
        self.driver.tamper_removal={}
        result=self.launcher.recover(self.claim['run_id'],outcome='failed')
        self.assertEqual(result['registration']['phase'],'released');self.assertEqual(result['task']['state'],'ready')
        self.assertIsNotNone(self.driver.guard)  # No cleanup/disarm interface in this coordinator.

    def test_unbound_recovery_facade_cannot_use_legacy_release(self):
        before=self.store.snapshot()
        with self.assertRaises(RecordError):self.launcher.recover(self.claim['run_id'],outcome='failed')
        self.assertEqual(self.driver.steps,[]);self.assertEqual(self.store.snapshot(),before)


if __name__=='__main__':unittest.main()
