"""Real SQLite/immutable markers with private fake command/observer ports."""
import copy
from datetime import timedelta
import hashlib
import importlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch
import test_hearth2_claims as fixtures
from hearth2.store import RecordError,safe_payload,timestamp
from hearth2.dispatch import DispatchRegistry
from hearth2.creation import CreationRegistry
from hearth2.launch import LaunchCoordinator
from hearth2.guard_entrypoint import RootGuardBindings
from hearth2.root_layout import RootLayoutPolicy


class RootLifecycleTests(unittest.TestCase):
    def setUp(self):
        fixtures.ClaimTests.setUp(self)
        self.assertIsNotNone(importlib.util.find_spec('hearth2.root_lifecycle'),'concrete root lifecycle missing')
        self.module=importlib.import_module('hearth2.root_lifecycle')
        self.repo=Path(self.tmp.name)/'repo';self.repo.mkdir(mode=0o700)
        self.sealdir=Path(self.tmp.name)/'seals';self.sealdir.mkdir(mode=0o700)
        self.attemptdir=Path(self.tmp.name)/'attempts';self.attemptdir.mkdir(mode=0o700)
        self.evidence=Path(self.tmp.name)/'evidence';self.evidence.mkdir(mode=0o700)
        self.guard=Path(self.tmp.name)/'guard';self.guard.write_bytes(b'PRIVATE NEVER EXECUTED');self.guard.chmod(0o500)
        assembly={'version':1,'kind':'hearth2-memory-only-bootstrap-v1','image_id':'sha256:'+'a'*64,
            'entrypoint':'/opt/hearth2/bootstrap','arguments':['--no-turn'],
            'native_policy_files':{'/etc/codex/requirements.toml':'b'*64}}
        profile=self.artifact(assembly)
        native={'version':1,'kind':'hearth2-memory-only-container-v1','image_id':assembly['image_id'],
            'native_profile_sha256':profile,'user':'1000:1000','tools':['memory_search','memory_get'],
            'memory_bytes':2*1024**3,'nano_cpus':10**9,'pids_limit':128,'network_mode':'none'}
        native_sha=self.artifact(native)
        guard=self.artifact({'version':1,'abi':'hearth2-root-guard-v1','executable':str(self.guard),
            'executable_sha256':hashlib.sha256(self.guard.read_bytes()).hexdigest()})
        layout={'version':1,'host_id':'1'*64,'backend':'systemd-root-slice','cgroup_root':'/sys/fs/cgroup',
            'control_group_prefix':'/','native_policy_sha256':native_sha,'guard_sha256':guard}
        self.layout=RootLayoutPolicy.load(self.repo,self.artifact(layout))
        self.host='1'*64;self.uid=0;self.container='c'*64;self.calls=[];self.armed=False;self.failure_stage=None
        self.bad_assembly={};self.bad_config={};self.bad_timer={};self.bad_service={}
        self.registry=DispatchRegistry(self.store,self.controller)
        self.claim=self.store.claim(self.controller,self.task['id'],expected_revision=1,request_id='lifecycle')
        self.registration=self.registry.prepare(self.claim,policy_sha256=self.layout.sha256)
        self.creations=CreationRegistry(self.registry)
        test=self
        class Runner:
            def __init__(_,kind):_.kind=kind
            def run(_,args):
                stage='arm' if _.kind=='systemd' else ('create' if 'create' in args else 'start')
                test.calls.append((stage,args))
                if stage=='arm':
                    assert list(test.sealdir.glob('*.json')),'arm before durable seal'
                    test.armed=True
                assert list(test.attemptdir.glob(stage+'-*.json')),'command before durable attempt'
                if test.failure_stage==stage:raise RecordError('private lost acknowledgement')
                return (test.container+'\n').encode() if stage=='create' else b''
        commands=self.module.FixedLifecycleCommands(docker=Runner('docker'),systemd_run=Runner('systemd'))
        def config(context,container):
            return {'container_config_state':'matched','host_id':context['host_id'],'container_id':container,
                'policy_sha256':context['policy_sha256'],'native_policy_sha256':self.layout.native_policy_sha256,
                'native_profile_sha256':profile,'observed_at':self.time.isoformat(),'references':['private:config'],**self.bad_config}
        def timer(binding):
            return {'timer_state':'armed' if self.armed else 'unknown','host_id':binding['host_id'],
                'guard_id':binding['guard_id'],'deadline_at':binding['deadline_at'],'observed_at':self.time.isoformat(),
                'service_id':binding['guard_id']+'.service','invocation_id':'1'*32,'references':['private:timer'],**self.bad_timer}
        def service(binding):
            return {'service_state':'matched','host_id':binding['host_id'],'guard_id':binding['guard_id'],
                'deadline_at':binding['deadline_at'],'guard_sha256':self.layout.guard_sha256,
                'native_policy_sha256':native_sha,'observed_at':self.time.isoformat(),
                'references':['private:service'],**self.bad_service}
        def assembly_observation(context,container,policy,spec):
            return {'host_id':context['host_id'],'container_id':container,'run_id':context['run_id'],
                'creation_epoch':context['creation_epoch'],'policy_sha256':context['policy_sha256'],
                'native_profile_sha256':profile,'observed_at':self.time.isoformat(),
                'states':dict(self.module.ASSEMBLY_STATES),'references':['private:independent-assembly'],**self.bad_assembly}
        port=lambda method,fn:type('Port',(),{method:staticmethod(fn)})()
        self.observer=port('inspect',assembly_observation)
        self.seals=RootGuardBindings(self.sealdir,clock=lambda:self.time)
        self.attempts=self.module.RootLaunchAttempts(self.attemptdir,clock=lambda:self.time)
        self.driver=self.module.RootLifecycleDriver(self.layout,self.repo,self.seals,self.attempts,commands,
            config_reader=port('inspect',config),timer_reader=port('inspect',timer),service_reader=port('inspect',service),
            assembly_observer=self.observer,evidence_root=str(self.evidence),host_identity=lambda:self.host,
            clock=lambda:self.time,euid=lambda:self.uid)

    def artifact(self,value):
        raw=(safe_payload(value)+'\n').encode();sha=hashlib.sha256(raw).hexdigest();p=self.repo/(sha+'.json')
        p.write_bytes(raw);p.chmod(0o400);return sha

    def intent(self):return self.creations.begin(self.registration,self.claim,host_id=self.host)

    def launch(self):return LaunchCoordinator(self.registry,self.driver).launch(self.registration,self.claim,host_id=self.host)

    def test_complete_synthetic_pipeline_seals_before_arm_consumes_before_one_start(self):
        result=self.launch()
        self.assertEqual([stage for stage,_ in self.calls],['create','arm','start'])
        self.assertEqual(result['registration']['phase'],'launching')
        self.assertEqual(len(list(self.attemptdir.glob('*.json'))),4)
        self.assertEqual(self.seals.read(result['binding'],host_identity=lambda:self.host)['binding'],result['binding'])

    def test_missing_assembly_observer_fails_before_any_external_command(self):
        self.driver.assembly_observer=None
        with self.assertRaises(RecordError):self.launch()
        self.assertEqual(self.calls,[]);self.assertEqual(list(self.attemptdir.iterdir()),[])
        with self.store.transaction() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM audit_events WHERE action='creation_intent'").fetchone()[0],0)

    def test_partial_packets_or_bad_assembly_states_never_become_creation_authority(self):
        self.bad_assembly={'states':{'native_profile':'hash-only'}}
        with self.assertRaises(RecordError):self.launch()
        self.assertEqual(self.calls,[])

    def test_lost_create_ack_is_durable_and_never_replayed_by_new_driver(self):
        intent=self.intent();self.failure_stage='create'
        with self.assertRaises(RecordError):self.driver.create_stopped(intent)
        self.failure_stage=None
        self.driver.attempts=self.module.RootLaunchAttempts(self.attemptdir,clock=lambda:self.time)
        with self.assertRaises(RecordError):self.driver.create_stopped(intent)
        self.assertEqual([s for s,_ in self.calls],['create'])
        self.assertEqual(len(list(self.attemptdir.glob('create-*.json'))),1)

    def test_lost_arm_ack_retains_seal_and_never_rearms(self):
        self.failure_stage='arm'
        with self.assertRaises(RecordError):self.launch()
        binding=self.creations.read(self.claim['run_id']);self.failure_stage=None
        with self.assertRaises(RecordError):self.driver.arm_guard(binding)
        self.assertEqual([s for s,_ in self.calls],['create','arm'])
        self.assertTrue(self.seals.read(binding,host_identity=lambda:self.host))

    def test_lost_start_ack_never_restarts_after_driver_recreation(self):
        self.failure_stage='start'
        with self.assertRaises(RecordError):self.launch()
        binding=self.creations.read(self.claim['run_id']);self.failure_stage=None
        self.driver.attempts=self.module.RootLaunchAttempts(self.attemptdir,clock=lambda:self.time)
        with self.assertRaises(RecordError):self.driver.start(binding)
        self.assertEqual([s for s,_ in self.calls],['create','arm','start'])

    def test_wrong_stopped_configuration_blocks_binding_arm_and_start(self):
        self.bad_config={'container_config_state':'unknown'}
        with self.assertRaises(RecordError):self.launch()
        self.assertEqual([s for s,_ in self.calls],['create']);self.assertEqual(list(self.sealdir.iterdir()),[])

    def test_bad_timer_or_service_prevents_consumption_and_start(self):
        self.bad_timer={'deadline_at':(self.time+timedelta(days=2)).isoformat()}
        with self.assertRaises(RecordError):self.launch()
        self.assertEqual([s for s,_ in self.calls],['create','arm'])
        with self.store.transaction() as db:self.assertEqual(self.registry._owned(self.registry._latest(db),self.claim['run_id'])['phase'],'reserved')

    def test_wrong_service_artifact_prevents_consumption(self):
        self.bad_service={'native_policy_sha256':'e'*64}
        with self.assertRaises(RecordError):self.launch()
        self.assertEqual([s for s,_ in self.calls],['create','arm'])
        with self.store.transaction() as db:self.assertEqual(self.registry._owned(self.registry._latest(db),self.claim['run_id'])['phase'],'reserved')

    def test_bound_id_must_be_root_recorded_create_result(self):
        intent=self.intent();self.driver.create_stopped(intent)
        binding=self.creations.bind(self.registration,self.claim,host_id=self.host,container_id='d'*64)
        with self.assertRaises(RecordError):self.driver.arm_guard(binding)
        self.assertEqual([s for s,_ in self.calls],['create']);self.assertEqual(list(self.sealdir.iterdir()),[])

    def test_lost_created_receipt_ack_does_not_duplicate_unbound_container(self):
        original=self.attempts.mark
        def lose(stage,context,container=None):
            result=original(stage,context,container)
            if stage=='created':raise RecordError('private lost created receipt ack')
            return result
        intent=self.intent()
        with patch.object(self.attempts,'mark',side_effect=lose):
            with self.assertRaises(RecordError):self.driver.create_stopped(intent)
        with self.assertRaises(RecordError):self.driver.create_stopped(intent)
        self.assertEqual([s for s,_ in self.calls],['create'])
        self.assertTrue(list(self.attemptdir.glob('created-*.json')))
        self.assertIsNone(self.creations.read(self.claim['run_id']))

    def test_seal_failure_prevents_arm_and_retains_bound_id(self):
        with patch.object(self.seals,'seal',side_effect=RecordError('private seal fault')):
            with self.assertRaises(RecordError):self.launch()
        self.assertEqual([s for s,_ in self.calls],['create'])
        self.assertEqual(self.creations.read(self.claim['run_id'])['container_id'],self.container)
        self.assertEqual(list(self.attemptdir.glob('arm-*.json')),[])

    def test_expired_assembly_after_consumption_prevents_start(self):
        intent=self.intent();container=self.driver.create_stopped(intent)
        self.driver.inspect_created(intent,container)
        binding=self.creations.bind(self.registration,self.claim,host_id=self.host,container_id=container)
        self.driver.arm_guard(binding);proof=self.driver.inspect_armed(binding)
        self.creations.consume_armed(self.claim,binding,proof=proof)
        self.bad_assembly={'observed_at':(self.time-timedelta(seconds=61)).isoformat()}
        with self.assertRaises(RecordError):self.driver.start(binding)
        self.assertEqual([s for s,_ in self.calls],['create','arm'])
        self.assertEqual(list(self.attemptdir.glob('start-*.json')),[])

    def test_expired_original_deadline_and_new_host_refuse_before_create(self):
        intent=self.intent();self.host='2'*64
        with self.assertRaises(RecordError):self.driver.create_stopped(intent)
        self.host='1'*64;self.time=timestamp(intent['deadline_at'])
        with self.assertRaises(RecordError):self.driver.create_stopped(intent)
        self.assertEqual(self.calls,[])

    def test_root_uid_and_attempt_fsync_failure_prevent_external_commands(self):
        intent=self.intent();self.uid=1000
        with self.assertRaises(RecordError):self.driver.create_stopped(intent)
        self.uid=0
        with patch.object(self.module.os,'fsync',side_effect=OSError('private sync failure')):
            with self.assertRaises(RecordError):self.driver.create_stopped(intent)
        self.assertEqual(self.calls,[])
        self.assertTrue(list(self.attemptdir.glob('create-*.json')))

    def test_native_assembly_unknown_fields_tools_and_image_change_refuse(self):
        policy=self.module.NativeContainerPolicy.load(self.repo,self.layout.native_policy_sha256)
        spec=self.module.NativeAssemblySpec.load(self.repo,policy.native_profile_sha256)
        for changes in [{'version':True},{'kind':'other'},{'entrypoint':'/bin/sh/../other'},
                {'arguments':[]},{'unknown':True}]:
            with self.subTest(changes=changes),self.assertRaises(RecordError):
                self.module.NativeAssemblySpec.encode({**spec.manifest(),**changes})

    def test_assembly_arg_count_fits_fixed_40_argument_command_transport(self):
        policy=self.module.NativeContainerPolicy.load(self.repo,self.layout.native_policy_sha256)
        spec=self.module.NativeAssemblySpec.load(self.repo,policy.native_profile_sha256)
        with self.assertRaises(RecordError):
            self.module.NativeAssemblySpec.encode({**spec.manifest(),'arguments':['x']*13})

    def test_twelve_arguments_fit_real_budget_but_utf8_overflow_refuses_without_command(self):
        policy=self.module.NativeContainerPolicy.load(self.repo,self.layout.native_policy_sha256)
        spec=self.module.NativeAssemblySpec.load(self.repo,policy.native_profile_sha256)
        intent=self.intent();mapping=self.layout.resolve(intent,host_identity=lambda:self.host)
        for argument,allowed in [('x',True),('\u6f22'*900,False)]:
            sha=self.artifact({**spec.manifest(),'arguments':[argument]*12})
            candidate=self.module.NativeAssemblySpec.load(self.repo,sha)
            native=self.artifact({**policy.manifest(),'native_profile_sha256':sha})
            matched=self.module.NativeContainerPolicy.load(self.repo,native)
            if allowed:
                args=self.module.FixedLifecycleCommands.create_arguments(intent,matched,mapping,candidate)
                self.assertEqual(len(args),40)
                self.module.BoundedCommand.validate_arguments(args)
            else:
                with self.assertRaisesRegex(RecordError,'bounded root command'):
                    self.module.FixedLifecycleCommands.create_arguments(intent,matched,mapping,candidate)
        self.assertEqual(self.calls,[]);self.assertEqual(list(self.attemptdir.iterdir()),[])

    def test_create_command_has_exact_bounded_policy_and_no_env_mount_shell_or_pull(self):
        intent=self.intent();self.driver.create_stopped(intent);args=self.calls[0][1]
        for item in ['--pull=never','--network=none','--no-healthcheck','--read-only','--user=1000:1000','--pids-limit=128',
                '--memory=2147483648','--memory-swap=2147483648','--cpus=1','--entrypoint=/opt/hearth2/bootstrap']:
            self.assertIn(item,args)
        self.assertFalse(any(a.startswith('--env') or a.startswith('--mount') or a in ['run','rm','--privileged'] for a in args))
        self.assertEqual(args[-3:],['--','sha256:'+'a'*64,'--no-turn'])

    def test_arm_uses_original_absolute_calendar_literal_json_and_no_replace(self):
        self.launch();args=self.calls[1][1]
        self.assertIn('--expand-environment=no',args)
        self.assertTrue(any(a.startswith('--on-calendar=') and a.endswith(' UTC') for a in args))
        self.assertFalse(any(a.startswith('--on-active') or a=='--replace' for a in args))
        self.assertEqual(args[-2],'--binding-json')
        self.assertEqual(json.loads(args[-1])['container_id'],self.container)

    def test_start_command_only_targets_sealed_immutable_id(self):
        self.launch();self.assertEqual(self.calls[-1][1],['--host','unix:///var/run/docker.sock','container','start','--',self.container])


if __name__=='__main__':unittest.main()
