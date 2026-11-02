"""Service-only private artifact/typed command contracts; no real OS services."""
from datetime import timedelta
import copy
import hashlib
import importlib
import json
from pathlib import Path
import unittest
import test_hearth2_claims as fixtures
from hearth2.store import RecordError,safe_payload,timestamp
from hearth2.dispatch import DispatchRegistry
from hearth2.creation import CreationRegistry
from hearth2.root_layout import RootLayoutPolicy


class GuardServiceTests(unittest.TestCase):
    def setUp(self):
        fixtures.ClaimTests.setUp(self)
        self.assertIsNotNone(importlib.util.find_spec('hearth2.guard_service'),'guard service readback missing')
        self.module=importlib.import_module('hearth2.guard_service')
        self.repo=Path(self.tmp.name)/'artifacts';self.repo.mkdir(mode=0o700)
        self.executable=Path(self.tmp.name)/'guard';self.executable.write_bytes(b'PRIVATE NOT EXECUTED GUARD');self.executable.chmod(0o500)
        self.manifest={'version':1,'abi':'hearth2-root-guard-v1','executable':str(self.executable),
            'executable_sha256':hashlib.sha256(self.executable.read_bytes()).hexdigest()}
        guard=self.artifact(self.manifest);native=self.artifact({'version':1,'native_policy':'private-fixture-not-enforced'})
        manifest={'version':1,'host_id':'1'*64,'backend':'systemd-root-slice','cgroup_root':'/sys/fs/cgroup',
            'control_group_prefix':'/','guard_sha256':guard,'native_policy_sha256':native}
        digest=self.artifact(manifest);self.policy=RootLayoutPolicy.load(self.repo,digest)
        self.claim=self.store.claim(self.controller,self.task['id'],expected_revision=1,request_id='service')
        self.registry=DispatchRegistry(self.store,self.controller)
        registration=self.registry.prepare(self.claim,policy_sha256=digest)
        self.binding=CreationRegistry(self.registry).bind(registration,self.claim,host_id='1'*64,container_id='b'*64)
        self.host='1'*64
        self.artifacts=self.module.RootGuardArtifacts(self.repo)
        self.argv=[str(self.executable),'--binding-json',safe_payload(self.binding)]
        self.state={'service_path':'/org/freedesktop/systemd1/unit/test',
            'unit':{'Id':self.binding['guard_id']+'.service','LoadState':'loaded','ActiveState':'inactive',
                'SubState':'dead','Transient':True,'InvocationID':[]},
            'service':{'User':'0','Group':'0','DynamicUser':False,'Type':'oneshot','Restart':'no',
                'RemainAfterExit':False,'RootDirectory':'','RootImage':'','WorkingDirectory':'/',
                'MainPID':0,'Result':'success','Slice':'system.slice',
                'ExecStartEx':[[str(self.executable),self.argv,['no-env-expand'],0,0,0,0,0,0,0]],
                **{k:[] for k in ['ExecConditionEx','ExecStartPreEx','ExecStartPostEx','ExecReloadEx','ExecStopEx','ExecStopPostEx']}}}
        self.snapshots=0
        def snapshot(guard):self.snapshots+=1;return copy.deepcopy(self.state)
        self.port=type('Port',(),{'snapshot':staticmethod(snapshot)})()
        self.reader=self.module.RootGuardServiceReadback(self.port,self.artifacts,self.policy,
            host_identity=lambda:self.host,clock=lambda:self.time)

    def artifact(self,value):
        raw=(safe_payload(value)+'\n').encode();digest=hashlib.sha256(raw).hexdigest()
        path=self.repo/(digest+'.json');path.write_bytes(raw);path.chmod(0o400);return digest

    def read(self):return self.reader.inspect(self.binding)

    def test_exact_sealed_service_is_service_only_and_two_stable_reads(self):
        proof=self.read();self.assertEqual(proof['service_state'],'matched')
        self.assertEqual(self.snapshots,2);self.assertNotIn('guard_state',proof)
        self.assertEqual(proof['native_policy_sha256'],self.policy.native_policy_sha256)
        with self.assertRaises(RecordError):CreationRegistry(self.registry).consume_armed(self.claim,self.binding,proof=proof)

    def test_missing_literal_argument_flag_refuses(self):
        self.state['service']['ExecStartEx'][0][2]=[]
        with self.assertRaises(RecordError):self.read()

    def test_wrong_binding_arguments_or_shell_wrapper_refuses(self):
        for command in [['/bin/sh',['/bin/sh','-c','true'],[],0,0,0,0,0,0,0],
                [str(self.executable),self.argv+['--other'],[],0,0,0,0,0,0,0]]:
            self.state['service']['ExecStartEx']=[command]
            with self.assertRaises(RecordError):self.read()

    def test_exec_prefix_flags_and_alternate_commands_refuse(self):
        for changes in [{'ExecStartEx':[[str(self.executable),self.argv,['ignore-failure'],0,0,0,0,0,0,0]]},
                {'ExecStartPreEx':[[str(self.executable),self.argv,['no-env-expand'],0,0,0,0,0,0,0]]}]:
            original=copy.deepcopy(self.state['service']);self.state['service'].update(changes)
            with self.assertRaises(RecordError):self.read()
            self.state['service']=original

    def test_root_configuration_must_be_explicit_numeric_no_dynamic_user(self):
        for key,value in [('User','root'),('User','1000'),('Group',''),('DynamicUser',True)]:
            original=self.state['service'][key];self.state['service'][key]=value
            with self.assertRaises(RecordError):self.read()
            self.state['service'][key]=original

    def test_alternate_root_or_workload_slice_refuses(self):
        for key,value in [('RootDirectory','/other'),('RootImage','/image'),('WorkingDirectory','/tmp'),
                ('Slice',self.policy.resolve(self.binding,host_identity=lambda:self.host)['daemon_parent'])]:
            original=self.state['service'][key];self.state['service'][key]=value
            with self.assertRaises(RecordError):self.read()
            self.state['service'][key]=original

    def test_prior_execution_or_running_guard_refuses(self):
        for section,key,value in [('unit','ActiveState','active'),('unit','InvocationID',[1]*16),('service','MainPID',1),
                ('service','ExecStartEx',[[str(self.executable),self.argv,['no-env-expand'],1,0,0,0,0,0,0]])]:
            original=self.state[section][key];self.state[section][key]=value
            with self.assertRaises(RecordError):self.read()
            self.state[section][key]=original

    def test_host_policy_or_deadline_mismatch_refuses(self):
        self.host='2'*64
        with self.assertRaises(RecordError):self.read()
        self.host='1'*64
        with self.assertRaises(RecordError):self.reader.inspect({**self.binding,'policy_sha256':'a'*64})
        self.time=timestamp(self.binding['deadline_at'])+timedelta(seconds=1)
        with self.assertRaises(RecordError):self.read()

    def test_artifact_checksum_permissions_and_native_artifact_required(self):
        path=self.repo/(self.policy.native_policy_sha256+'.json');path.chmod(0o600)
        with self.assertRaises(RecordError):self.read()
        path.write_bytes(b'{}\n');path.chmod(0o400)
        with self.assertRaises(RecordError):self.read()
        path.unlink()
        with self.assertRaises(RecordError):self.read()

    def test_executable_checksum_mode_and_symlink_refuse(self):
        self.executable.chmod(0o700)
        with self.assertRaises(RecordError):self.read()
        self.executable.write_bytes(b'changed');self.executable.chmod(0o500)
        with self.assertRaises(RecordError):self.read()
        self.executable.unlink();other=Path(self.tmp.name)/'other';other.write_bytes(b'PRIVATE NOT EXECUTED GUARD');other.chmod(0o500)
        self.executable.symlink_to(other)
        with self.assertRaises(RecordError):self.read()

    def test_changing_snapshot_or_host_during_read_refuses(self):
        def change(guard):
            result=copy.deepcopy(self.state);self.state['service']['Result']='failed';return result
        self.port.snapshot=change
        with self.assertRaises(RecordError):self.read()
        self.state['service']['Result']='success'
        def change_host(guard):self.host='2'*64;return copy.deepcopy(self.state)
        self.port.snapshot=change_host
        with self.assertRaises(RecordError):self.read()

    def test_typed_decoder_rejects_bool_in_integer_exec_history(self):
        self.state['service']['MainPID']=False
        with self.assertRaisesRegex(RecordError,'property type'):self.read()
        self.state['service']['MainPID']=0;self.state['service']['ExecStartEx'][0][3]=False
        with self.assertRaisesRegex(RecordError,'property type'):self.read()

    def test_stale_rollback_and_expired_collection_windows_refuse(self):
        for finish in [self.time+timedelta(seconds=61),self.time-timedelta(seconds=1),
                timestamp(self.binding['deadline_at'])]:
            times=iter([self.time,finish]);self.reader.clock=lambda:next(times)
            with self.assertRaises(RecordError):self.read()
        self.reader.clock=lambda:self.time
        monotonic=iter([0,61]);self.reader.monotonic=lambda:next(monotonic)
        with self.assertRaises(RecordError):self.read()

    def test_unknown_guard_abi_and_boolean_schema_version_refuse(self):
        for value in [{**self.manifest,'abi':'unknown'}, {**self.manifest,'version':True}]:
            digest=self.artifact(value)
            manifest={k:v for k,v in vars(self.policy).items() if k!='sha256'};manifest.update(version=1,guard_sha256=digest)
            raw=RootLayoutPolicy.encode(manifest);sha=hashlib.sha256(raw).hexdigest()
            self.reader.policy=RootLayoutPolicy(sha,**{k:v for k,v in manifest.items() if k!='version'})
            with self.assertRaisesRegex(RecordError,'artifact ABI'):self.artifacts.read(self.reader.policy)

    def test_private_repository_and_guard_artifact_symlink_refuse(self):
        self.repo.chmod(0o755)
        with self.assertRaises(RecordError):self.read()
        self.repo.chmod(0o700);path=self.repo/(self.policy.guard_sha256+'.json')
        path.unlink();outside=Path(self.tmp.name)/'outside';outside.write_text(safe_payload(self.manifest)+'\n');outside.chmod(0o400)
        path.symlink_to(outside)
        with self.assertRaises(RecordError):self.read()

    def test_fixed_typed_command_port_never_queries_environment_or_mutates_units(self):
        calls=[]
        class Runner:
            def run(_,args):
                calls.append(args)
                if 'call' in args:return json.dumps({'type':'o','data':[self.state['service_path']]})
                interface=args[args.index('get-property')+3]
                fields=self.module._UNIT if interface.endswith('.Unit') else self.module._SERVICE_FIELDS
                values=self.state['unit' if interface.endswith('.Unit') else 'service']
                return '\n'.join(json.dumps({'type':kind,'data':values[name]}) for name,kind in fields)
        port=self.module.SystemdGuardServiceProperties(Runner());snapshot=port.snapshot(self.binding['guard_id'])
        self.assertEqual(snapshot,self.state)
        self.assertTrue(all('GetUnit' in a or 'get-property' in a for a in calls))
        self.assertFalse(any('Environment' in a or 'StartUnit' in a or 'LoadUnit' in a for a in calls))
        with self.assertRaises(RecordError):port.snapshot('../foreign')


if __name__=='__main__':unittest.main()
