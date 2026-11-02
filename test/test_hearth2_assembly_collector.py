"""Independent private facts; no actual Docker, image file or runtime probes."""
import copy
from dataclasses import replace
from datetime import timedelta
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest
import test_hearth2_claims as fixtures
from hearth2.store import RecordError,safe_payload,timestamp
from hearth2.dispatch import DispatchRegistry
from hearth2.creation import CreationRegistry
from hearth2.root_layout import RootLayoutPolicy
from hearth2.root_lifecycle import NativeAssemblySpec,NativeContainerPolicy,ASSEMBLY_STATES,RootLifecycleDriver
from hearth2.stopped_container import _COUNTS


class AssemblyCollectorTests(unittest.TestCase):
    def setUp(self):
        fixtures.ClaimTests.setUp(self)
        self.assertIsNotNone(importlib.util.find_spec('hearth2.assembly_collector'),'independent assembly collector missing')
        self.module=importlib.import_module('hearth2.assembly_collector')
        self.repo=Path(self.tmp.name)/'repo';self.repo.mkdir(mode=0o700)
        self.executable=Path(self.tmp.name)/'guard';self.executable.write_bytes(b'PRIVATE GUARD NOT EXECUTED');self.executable.chmod(0o500)
        exe_sha=hashlib.sha256(self.executable.read_bytes()).hexdigest()
        spec={'version':1,'kind':'hearth2-memory-only-bootstrap-v1','image_id':'sha256:'+'a'*64,
            'entrypoint':'/opt/hearth2/bootstrap','arguments':['--no-turn'],
            'native_policy_files':{'/opt/hearth2/bootstrap':'e'*64,'/etc/codex/requirements.toml':'b'*64}}
        spec_sha=self.artifact(spec);self.spec=NativeAssemblySpec.load(self.repo,spec_sha)
        native={'version':1,'kind':'hearth2-memory-only-container-v1','image_id':spec['image_id'],
            'native_profile_sha256':spec_sha,'user':'1000:1000','tools':['memory_search','memory_get'],
            'memory_bytes':2*1024**3,'nano_cpus':10**9,'pids_limit':128,'network_mode':'none'}
        native_sha=self.artifact(native);self.policy=NativeContainerPolicy.load(self.repo,native_sha)
        guard=self.artifact({'version':1,'abi':'hearth2-root-guard-v1','executable':str(self.executable),'executable_sha256':exe_sha})
        layout={'version':1,'host_id':'1'*64,'backend':'systemd-root-slice','cgroup_root':'/sys/fs/cgroup',
            'control_group_prefix':'/','guard_sha256':guard,'native_policy_sha256':native_sha}
        self.layout=RootLayoutPolicy.load(self.repo,self.artifact(layout))
        self.claim=self.store.claim(self.controller,self.task['id'],expected_revision=1,request_id='assembly')
        registry=DispatchRegistry(self.store,self.controller);registration=registry.prepare(self.claim,policy_sha256=self.layout.sha256)
        self.intent=CreationRegistry(registry).begin(registration,self.claim,host_id='1'*64)
        self.host='1'*64;self.uid=0;self.container='c'*64;self.calls=[]
        namespaces=tuple(sorted({'user':100,'pid':101,'mnt':102,'cgroup':103}.items()))
        self.anchor=self.module.RootAssemblyAnchor('1'*64,'11111111-1111-4111-8111-111111111111',namespaces,
            spec_sha,exe_sha,'d'*64,'e'*64,'f'*64,'private:trusted-enrollment')
        self.runtime={'host_id':self.host,'boot_id':self.anchor.boot_id,'uid':0,'euid':0,'namespaces':dict(namespaces),
            'guard_executable_sha256':exe_sha,'dependency_closure_sha256':'d'*64,'bootstrap_gate_sha256':'e'*64}
        self.image={'Id':spec['image_id'],'Os':'linux','Architecture':'amd64','UserMatch':True,
            'EnvironmentSafe':[True],'VolumesCount':0,'OnBuildCount':0,'HealthcheckDisabled':True,
            'ArgumentCount':1,'EntrypointMatch':True,'ArgumentsMatch':[True]}
        self.container_facts={'Id':self.container,'Image':spec['image_id'],'UserMatch':True,'EnvironmentSafe':[True],
            'HealthcheckDisabled':True,'ArgumentCount':1,'EntrypointMatch':True,'ArgumentsMatch':[True],
            'NetworkMode':'none','Privileged':False,'ReadonlyRootfs':True,'Counts':{k:0 for k in _COUNTS},
            'Labels':{'hearth2.run':self.intent['run_id'],'hearth2.creation_epoch':self.intent['creation_epoch'],
                'hearth2.policy_sha256':self.layout.sha256,'hearth2.workload':self.intent['workload_id']},
            'State':{'Status':'created','Running':False,'Pid':0,'StartedAt':'0001-01-01T00:00:00Z','FinishedAt':'0001-01-01T00:00:00Z'}}
        self.file_changes={};self.bad_runtime={};self.bad_image={};self.bad_container={};self.bad_credentials={};self.advance=False
        def stamp(value,kind):return {**copy.deepcopy(value),'observed_at':self.time.isoformat(),'references':['private:'+kind]}
        test=self
        class Metadata:
            def image(_,spec):test.calls.append('image');return stamp({**test.image,**test.bad_image},'image')
            def container(_,container,spec):test.calls.append('container');return stamp({**test.container_facts,**test.bad_container},'container')
        class Files:
            def observe(_,image,container,path):
                test.calls.append('file:'+path)
                data={'image_id':image,'container_id':container,'path':path,'sha256':dict(test.spec.files)[path],
                    'kind':'regular','uid':0,'mode':0o555 if path==test.spec.entrypoint else 0o444,'size':64}
                return stamp({**data,**test.file_changes},'file:'+path)
        class Runtime:
            def observe(_,context,container,spec):
                test.calls.append('runtime')
                if test.advance:test.time+=timedelta(seconds=61)
                return stamp({**test.runtime,**test.bad_runtime},'runtime')
        class Credentials:
            def observe(_,image,container,spec):
                test.calls.append('credentials')
                data={'image_id':image,'container_id':container,'native_profile_sha256':spec.sha256,
                    'inventory_policy_sha256':test.anchor.credential_policy_sha256,
                    'scope':'image-rootfs-env-native-consumers-v1' if container is None else 'image-container-rootfs-env-native-consumers-mounts-v1',
                    'complete':True,'credential_entries':0,'unknown_consumers':0,'unreadable_sources':0,'unscanned_sources':0}
                return {**stamp(data,'credential-inventory'),**test.bad_credentials}
        self.metadata=Metadata();self.files=Files();self.runtime_port=Runtime();self.credentials=Credentials()
        self.collector=self.module.RootAssemblyCollector(self.layout,self.repo,self.anchor,self.metadata,self.files,self.runtime_port,
            credential_facts=self.credentials,host_identity=lambda:self.host,clock=lambda:self.time,euid=lambda:self.uid)

    def artifact(self,value):
        raw=(safe_payload(value)+'\n').encode();sha=hashlib.sha256(raw).hexdigest();p=self.repo/(sha+'.json')
        p.write_bytes(raw);p.chmod(0o400);return sha

    def read(self,container=None):return self.collector.inspect(self.intent,container,self.policy,self.spec)

    def test_independent_rounds_derive_exact_driver_packet_and_reference_provenance(self):
        packet=self.read();self.assertEqual(packet['states'],dict(ASSEMBLY_STATES))
        self.assertEqual(self.calls.count('image'),2);self.assertEqual(self.calls.count('runtime'),2)
        self.assertEqual(self.calls.count('credentials'),2)
        self.assertIn('private:trusted-enrollment',packet['references']);self.assertIsNone(packet['container_id'])
        driver=RootLifecycleDriver(self.layout,self.repo,None,None,None,config_reader=None,timer_reader=None,service_reader=None,
            evidence_root='',host_identity=lambda:self.host,clock=lambda:self.time,euid=lambda:0,assembly_observer=self.collector)
        self.assertTrue(driver._assembly({'c':self.intent,'policy':self.policy,'spec':self.spec},None))

    def test_container_rounds_bind_exact_id_command_labels_and_no_mounts(self):
        self.assertEqual(self.read(self.container)['container_id'],self.container)
        self.assertEqual(self.calls.count('container'),2)
        self.bad_container={'EntrypointMatch':False}
        with self.assertRaises(RecordError):self.read(self.container)

    def test_policy_hashes_or_caller_states_never_replace_independent_facts(self):
        self.collector.runtime_facts=type('Caller',(),{'observe':lambda *args:dict(ASSEMBLY_STATES)})()
        with self.assertRaises(RecordError):self.read()

    def test_missing_anchor_or_any_independent_port_fails_closed(self):
        for key in ['anchor','metadata','file_digests','runtime_facts','credential_facts']:
            original=getattr(self.collector,key);setattr(self.collector,key,None)
            with self.assertRaises(RecordError):self.read()
            setattr(self.collector,key,original)

    def test_missing_credential_inventory_never_emits_credential_absence(self):
        self.collector.credential_facts=None
        with self.assertRaises(RecordError):self.read()

    def test_incomplete_dirty_or_wrong_scope_credential_inventory_refuses(self):
        for changes in [{'complete':False},{'credential_entries':1},{'unknown_consumers':1},
                {'unreadable_sources':1},{'unscanned_sources':1},{'scope':'env-only'},
                {'image_id':'sha256:'+'0'*64},{'container_id':'0'*64},
                {'inventory_policy_sha256':'0'*64},{'native_profile_sha256':'0'*64}]:
            self.bad_credentials=changes
            with self.subTest(changes=changes),self.assertRaises(RecordError):self.read()
        self.bad_credentials={'scope':'image-rootfs-env-native-consumers-v1'}
        with self.assertRaises(RecordError):self.read(self.container)

    def test_credential_inventory_is_fresh_not_historical_or_cached(self):
        self.bad_credentials={'observed_at':(self.time-timedelta(seconds=1)).isoformat()}
        with self.assertRaisesRegex(RecordError,'predates round'):self.read()

    def test_root_uid_boot_and_namespace_fences_cannot_follow_restore_host(self):
        for changes in [{'uid':1000},{'euid':False},{'boot_id':'22222222-2222-4222-8222-222222222222'},
                {'namespaces':{**dict(self.anchor.namespaces),'user':999}},{'host_id':'2'*64}]:
            self.bad_runtime=changes
            with self.subTest(changes=changes),self.assertRaises(RecordError):self.read()

    def test_guard_dependency_and_bootstrap_measurements_must_match_anchor(self):
        for key in ['guard_executable_sha256','dependency_closure_sha256','bootstrap_gate_sha256']:
            self.bad_runtime={key:'f'*64}
            with self.subTest(key=key),self.assertRaises(RecordError):self.read()

    def test_file_hash_kind_owner_permissions_or_wrong_image_refuse(self):
        for changes in [{'sha256':'f'*64},{'kind':'symlink'},{'uid':1000},{'mode':0o777},{'size':0},
                {'image_id':'sha256:'+'f'*64},{'container_id':'f'*64}]:
            self.file_changes=changes
            with self.subTest(changes=changes),self.assertRaises(RecordError):self.read()

    def test_unknown_environment_and_image_defaults_are_not_safe_by_declaration(self):
        for changes in [{'EnvironmentSafe':[False]},{'VolumesCount':1},{'ArgumentCount':False},
                {'ArgumentsMatch':[False]},{'UserMatch':False},{'Architecture':'arm64'}]:
            self.bad_image=changes
            with self.subTest(changes=changes),self.assertRaises(RecordError):self.read()

    def test_wrong_container_labels_state_network_and_counts_refuse(self):
        for changes in [{'Labels':{**self.container_facts['Labels'],'hearth2.creation_epoch':'wrong'}},
                {'State':{**self.container_facts['State'],'Running':True}},{'NetworkMode':'host'},
                {'Counts':{**self.container_facts['Counts'],'binds':1}}]:
            self.bad_container=changes
            with self.subTest(changes=changes),self.assertRaises(RecordError):self.read(self.container)

    def test_host_uid_and_original_deadline_are_checked_before_collecting(self):
        self.uid=1000
        with self.assertRaises(RecordError):self.read()
        self.uid=0;self.host='2'*64
        with self.assertRaises(RecordError):self.read()
        self.host='1'*64;self.time=timestamp(self.intent['deadline_at'])
        with self.assertRaises(RecordError):self.read()
        self.assertEqual(self.calls,[])

    def test_changed_facts_or_overlong_collection_refuse(self):
        original=self.runtime_port.observe
        def change(*args):
            result=original(*args);self.runtime['dependency_closure_sha256']='f'*64;return result
        self.runtime_port.observe=change
        with self.assertRaises(RecordError):self.read()
        self.runtime_port.observe=original;self.runtime['dependency_closure_sha256']='d'*64;self.advance=True
        with self.assertRaises(RecordError):self.read()

    def test_reused_mutable_fact_object_cannot_rewrite_first_snapshot(self):
        shared={**copy.deepcopy(self.image),'observed_at':self.time.isoformat(),'references':['private:shared']}
        calls=[0]
        def image(spec):
            calls[0]+=1
            if calls[0]>1:shared['EnvironmentSafe'].clear()
            return shared
        self.metadata.image=image
        with self.assertRaisesRegex(RecordError,'changed'):self.read()

    def test_unapproved_anchor_cannot_bless_different_assembly_or_bootstrap(self):
        for changes in [{'assembly_sha256':'f'*64},{'bootstrap_sha256':'f'*64}]:
            self.collector.anchor=replace(self.anchor,**changes)
            with self.subTest(changes=changes),self.assertRaises(RecordError):self.read()

    def test_mutable_namespace_pairs_cannot_change_trusted_enrollment(self):
        with self.assertRaises(RecordError):
            replace(self.anchor,namespaces=tuple(list(pair) for pair in self.anchor.namespaces))

    def test_cached_runtime_facts_or_monotonic_overrun_are_not_new_measurements(self):
        original=self.runtime_port.observe
        def cached(*args):return {**original(*args),'observed_at':(self.time-timedelta(seconds=1)).isoformat()}
        self.runtime_port.observe=cached
        with self.assertRaisesRegex(RecordError,'predates round'):self.read()
        self.runtime_port.observe=original;mono=iter([0,61]);self.collector.monotonic=lambda:next(mono)
        with self.assertRaises(RecordError):self.read()

    def test_metadata_port_refuses_unrequested_fields_before_returning_them(self):
        image={k:v for k,v in self.image.items() if k not in {'EntrypointMatch','ArgumentsMatch'}}
        class Runner:
            def run(_,args):return json.dumps({**image,'Env':['PRIVATE_NOT_FOR_OUTPUT']}).encode() if args[args.index('--format')+1].startswith('{"Id"') else b'true'
        port=self.module.DockerAssemblyMetadata(Runner(),clock=lambda:self.time)
        with self.assertRaises(RecordError):port.image(self.spec)

    def test_fixed_metadata_queries_are_read_only_and_do_not_emit_env_or_argv(self):
        calls=[]
        image={k:v for k,v in self.image.items() if k not in {'EntrypointMatch','ArgumentsMatch'}}
        class Runner:
            def run(_,args):
                calls.append(args);template=args[args.index('--format')+1]
                return json.dumps(image).encode() if template.startswith('{"Id"') else b'true'
        port=self.module.DockerAssemblyMetadata(Runner(),clock=lambda:self.time)
        observed=port.image(self.spec);self.assertEqual(observed['Id'],self.spec.image_id)
        self.assertEqual(observed['ArgumentsMatch'],[True])
        for args in calls:
            self.assertEqual(args[:4],['--host','unix:///var/run/docker.sock','image','inspect'])
            template=args[args.index('--format')+1]
            self.assertNotIn('json .Config.Env',template);self.assertNotIn('json .Config.Cmd',template)
            self.module.BoundedCommand.validate_arguments(args)

    def test_template_budget_handles_each_long_unicode_argument_independently(self):
        calls=[];spec=self.spec.manifest();spec['arguments']=['\u6f22'*900]*12
        candidate=NativeAssemblySpec.load(self.repo,self.artifact(spec))
        image={k:v for k,v in self.image.items() if k not in {'EntrypointMatch','ArgumentsMatch'}};image['ArgumentCount']=12
        class Runner:
            def run(_,args):
                self.module.BoundedCommand.validate_arguments(args);calls.append(args)
                return json.dumps(image).encode() if args[args.index('--format')+1].startswith('{"Id"') else b'true'
        port=self.module.DockerAssemblyMetadata(Runner(),clock=lambda:self.time)
        self.assertEqual(port.image(candidate)['ArgumentsMatch'],[True]*12)
        self.assertEqual(len(calls),14)


if __name__=='__main__':unittest.main()
