"""Private files/injected Docker projection; no actual containers or workers."""
import copy
from datetime import timedelta
import hashlib
import importlib
import json
from pathlib import Path
import unittest
from dataclasses import replace
import test_hearth2_claims as fixtures
from hearth2.store import RecordError,safe_payload,timestamp
from hearth2.dispatch import DispatchRegistry
from hearth2.creation import CreationRegistry
from hearth2.root_layout import RootLayoutPolicy


class StoppedContainerTests(unittest.TestCase):
    def setUp(self):
        fixtures.ClaimTests.setUp(self)
        self.assertIsNotNone(importlib.util.find_spec('hearth2.stopped_container'),'stopped resource readback missing')
        self.module=importlib.import_module('hearth2.stopped_container')
        self.repo=Path(self.tmp.name)/'policies';self.repo.mkdir(mode=0o700)
        self.manifest={'version':1,'kind':'hearth2-memory-only-container-v1','image_id':'sha256:'+'a'*64,
            'native_profile_sha256':'b'*64,'user':'1000:1000','tools':['memory_search','memory_get'],
            'memory_bytes':2*1024**3,'nano_cpus':10**9,'pids_limit':128,'network_mode':'none'}
        native=self.artifact(self.manifest)
        layout={'version':1,'host_id':'1'*64,'backend':'systemd-root-slice','cgroup_root':'/sys/fs/cgroup',
            'control_group_prefix':'/','guard_sha256':'c'*64,'native_policy_sha256':native}
        self.layout=RootLayoutPolicy.load(self.repo,self.artifact(layout))
        self.policy=self.module.NativeContainerPolicy.load(self.repo,native)
        self.claim=self.store.claim(self.controller,self.task['id'],expected_revision=1,request_id='stopped')
        self.registry=DispatchRegistry(self.store,self.controller)
        self.registration=self.registry.prepare(self.claim,policy_sha256=self.layout.sha256)
        self.creations=CreationRegistry(self.registry);self.host='1'*64;self.container='d'*64
        self.intent=self.creations.begin(self.registration,self.claim,host_id=self.host)
        self.binding=self.creations.bind(self.registration,self.claim,host_id=self.host,container_id=self.container)
        parent=self.layout.resolve(self.intent,host_identity=lambda:self.host)['daemon_parent']
        self.state={'Id':self.container,'Image':self.manifest['image_id'],
            'Config':{'User':'1000:1000','Labels':{'hearth2.run':self.binding['run_id'],
                'hearth2.creation_epoch':self.binding['creation_epoch'],'hearth2.policy_sha256':self.layout.sha256,
                'hearth2.workload':self.binding['workload_id']}},
            'HostConfig':{'CgroupParent':parent,'Memory':2*1024**3,'MemorySwap':2*1024**3,'NanoCpus':10**9,
                'PidsLimit':128,'ReadonlyRootfs':True,'Privileged':False,'CapAdd':None,'CapDrop':['ALL'],
                'NetworkMode':'none','PidMode':'','IpcMode':'private','UTSMode':'','UsernsMode':'',
                'CgroupnsMode':'private','SecurityOpt':['no-new-privileges:true'],'AutoRemove':False,
                'RestartPolicy':{'Name':'no','MaximumRetryCount':0}},
            'State':{'Status':'created','Running':False,'Paused':False,'Restarting':False,'Dead':False,'Pid':0,
                'ExitCode':0,'StartedAt':'0001-01-01T00:00:00Z','FinishedAt':'0001-01-01T00:00:00Z'},
            'Counts':{name:0 for name in self.module._COUNTS}}
        self.calls=0
        def inspect(container):self.calls+=1;return copy.deepcopy(self.state)
        self.port=type('Port',(),{'inspect':staticmethod(inspect)})()
        self.reader=self.module.RootStoppedContainerReadback(self.port,self.layout,self.repo,
            host_identity=lambda:self.host,clock=lambda:self.time)

    def artifact(self,value):
        raw=(safe_payload(value)+'\n').encode();digest=hashlib.sha256(raw).hexdigest()
        path=self.repo/(digest+'.json');path.write_bytes(raw);path.chmod(0o400);return digest

    def read(self,context=None):return self.reader.inspect(self.binding if context is None else context,self.container)

    def test_original_stopped_id_matches_partial_config_twice_not_full_creation_authority(self):
        proof=self.read();self.assertEqual(proof['container_config_state'],'matched');self.assertEqual(self.calls,2)
        self.assertNotIn('container_state',proof);self.assertNotIn('guard_state',proof)
        from hearth2.launch import LaunchCoordinator
        with self.assertRaises(RecordError):LaunchCoordinator(self.registry,None)._created(self.intent,self.container,proof)

    def test_pre_bind_intent_same_policy_and_original_id_can_be_inspected(self):
        self.assertEqual(self.read(self.intent)['container_id'],self.container)
        with self.assertRaises(RecordError):self.reader.inspect(self.binding,'e'*64)

    def test_image_labels_original_parent_and_user_must_match(self):
        for section,key,value in [('Config','User','0'),('HostConfig','CgroupParent',self.binding['parent_cgroup']),
                ('Config','Labels',{**self.state['Config']['Labels'],'hearth2.creation_epoch':'new'})]:
            original=self.state[section][key];self.state[section][key]=value
            with self.assertRaises(RecordError):self.read()
            self.state[section][key]=original
        self.state['Image']='sha256:'+'f'*64
        with self.assertRaises(RecordError):self.read()

    def test_resource_limits_cannot_be_missing_unlimited_or_changed(self):
        for key,value in [('Memory',0),('MemorySwap',-1),('NanoCpus',0),('PidsLimit',None),('PidsLimit',-1),('PidsLimit',False)]:
            original=self.state['HostConfig'][key];self.state['HostConfig'][key]=value
            with self.assertRaises(RecordError):self.read()
            self.state['HostConfig'][key]=original

    def test_running_previously_started_dead_or_restart_policy_refuses(self):
        for key,value in [('Status','exited'),('Running',True),('Pid',1),('StartedAt',self.time.isoformat()),('Dead',True)]:
            original=self.state['State'][key];self.state['State'][key]=value
            with self.assertRaises(RecordError):self.read()
            self.state['State'][key]=original
        self.state['HostConfig']['RestartPolicy']={'Name':'always','MaximumRetryCount':0}
        with self.assertRaises(RecordError):self.read()

    def test_security_namespace_capability_or_network_expansion_refuses(self):
        for key,value in [('Privileged',True),('ReadonlyRootfs',False),('CapAdd',['SYS_ADMIN']),('CapDrop',[]),
                ('SecurityOpt',[]),('PidMode','host'),('IpcMode','host'),('CgroupnsMode','host'),
                ('UsernsMode','host'),('NetworkMode','host'),('AutoRemove',True)]:
            original=self.state['HostConfig'][key];self.state['HostConfig'][key]=value
            with self.assertRaises(RecordError):self.read()
            self.state['HostConfig'][key]=original

    def test_extra_mount_device_port_or_host_mapping_counts_refuse(self):
        for key in self.module._COUNTS:
            self.state['Counts'][key]=1
            with self.subTest(key=key),self.assertRaises(RecordError):self.read()
            self.state['Counts'][key]=0

    def test_policy_schema_digest_ranges_and_scope_cannot_be_relaxed(self):
        for changes in [{'version':True},{'kind':'other'},{'image_id':'tag:latest'}, {'user':'0'},
                {'memory_bytes':0},{'nano_cpus':True},{'pids_limit':-1},{'network_mode':'host'},
                {'tools':['memory_search','memory_add']},{'unknown':True}]:
            with self.subTest(changes=changes),self.assertRaises(RecordError):
                self.module.NativeContainerPolicy.encode({**self.manifest,**changes})
        with self.assertRaises(RecordError):replace(self.policy,memory_bytes=1024**3)

    def test_private_policy_artifact_checksum_and_symlink_required(self):
        path=self.repo/(self.policy.sha256+'.json');path.chmod(0o600)
        with self.assertRaises(RecordError):self.read()
        path.write_bytes(b'{}\n');path.chmod(0o400)
        with self.assertRaises(RecordError):self.read()
        path.unlink();outside=Path(self.tmp.name)/'outside';outside.write_text(safe_payload(self.manifest)+'\n');outside.chmod(0o400)
        path.symlink_to(outside)
        with self.assertRaises(RecordError):self.read()

    def test_wrong_host_policy_and_deadline_refuse(self):
        self.host='2'*64
        with self.assertRaises(RecordError):self.read()
        self.host='1'*64
        with self.assertRaises(RecordError):self.read({**self.binding,'policy_sha256':'a'*64})
        self.time=timestamp(self.binding['deadline_at'])
        with self.assertRaises(RecordError):self.read()

    def test_changed_snapshot_context_or_overlong_collection_refuses(self):
        def change(container):
            result=copy.deepcopy(self.state);self.state['State']['Running']=True;return result
        self.port.inspect=change
        with self.assertRaises(RecordError):self.read()
        self.state['State']['Running']=False
        def mutate(container):self.binding['controller']='other';return copy.deepcopy(self.state)
        self.port.inspect=mutate
        with self.assertRaises(RecordError):self.read()

    def test_clock_rollback_or_overlong_monotonic_refuses(self):
        times=iter([self.time,self.time-timedelta(seconds=1)]);self.reader.clock=lambda:next(times)
        with self.assertRaises(RecordError):self.read()
        self.reader.clock=lambda:self.time;mono=iter([0,61]);self.reader.monotonic=lambda:next(mono)
        with self.assertRaises(RecordError):self.read()

    def test_unknown_projection_or_boolean_counts_do_not_coerce(self):
        key=next(iter(self.module._COUNTS));self.state['Counts'][key]=False
        with self.assertRaises(RecordError):self.read()
        self.state['Counts'][key]=0;self.state['Config']['Env']=['PRIVATE_NOT_READ']
        with self.assertRaises(RecordError):self.read()

    def test_fixed_docker_port_projects_only_selected_noncredential_fields(self):
        calls=[]
        class Runner:
            def run(_,args):calls.append(args);return json.dumps(self.state).encode()
        port=self.module.DockerStoppedContainerProperties(Runner());self.assertEqual(port.inspect(self.container),self.state)
        self.assertEqual(len(calls),1);args=calls[0]
        self.assertEqual(args[:4],['--host','unix:///var/run/docker.sock','container','inspect'])
        template=args[args.index('--format')+1]
        for forbidden in ['.Config.Env','.Config.Cmd','.Args','.Path','.State.Error','json .Mounts','json .HostConfig.Binds']:
            self.assertNotIn(forbidden,template)
        self.assertIn('len .Mounts',template)
        with self.assertRaises(RecordError):port.inspect('short')


if __name__=='__main__':unittest.main()
