"""Private root policy/mapped regular files; no actual cgroups or daemon."""
from datetime import timedelta
import hashlib
import importlib
import json
from pathlib import Path
import unittest
from dataclasses import replace
import test_hearth2_claims as fixtures
from hearth2.store import Store,RecordError
from hearth2.dispatch import DispatchRegistry
from hearth2.creation import CreationRegistry
from hearth2.backup import export_record,restore_record
from hearth2.root_guard import CgroupFiles,RootKernelGuard
from hearth2.guard_evidence import GuardEvidenceStore


class LayoutDaemon:
    def __init__(self,binding,files,parent):
        self.binding,self.files,self.parent=binding,files,parent;self.present=True
    def inspect(self,container):
        return {'Id':container,'Config':{'Labels':{'hearth2.run':self.binding['run_id'],
            'hearth2.creation_epoch':self.binding['creation_epoch'],
            'hearth2.policy_sha256':self.binding['policy_sha256'],'hearth2.workload':self.binding['workload_id']}},
            'HostConfig':{'CgroupParent':self.parent},'State':{'Running':False,'Pid':0,'Status':'exited',
                'ExitCode':137,'StartedAt':self.binding['at'],'FinishedAt':self.binding['at']}}
    def remove(self,container):self.present=False
    def absent(self,container):return not self.present


class RootLayoutTests(unittest.TestCase):
    def setUp(self):
        fixtures.ClaimTests.setUp(self)
        self.assertIsNotNone(importlib.util.find_spec('hearth2.root_layout'),'immutable root layout policy missing')
        self.module=importlib.import_module('hearth2.root_layout')
        self.root=Path(self.tmp.name)/'private-cgroup';self.root.mkdir()
        self.repo=Path(self.tmp.name)/'private-policies';self.repo.mkdir(mode=0o700)
        self.manifest={'version':1,'host_id':'1'*64,'backend':'systemd-root-slice',
            'cgroup_root':str(self.root),'control_group_prefix':'/',
            'native_policy_sha256':'a'*64,'guard_sha256':'b'*64}
        self.policy=self.artifact(self.manifest)
        self.claim=self.store.claim(self.controller,self.task['id'],expected_revision=1,request_id='layout-one')
        self.registry=DispatchRegistry(self.store,self.controller)
        self.registration=self.registry.prepare(self.claim,policy_sha256=self.policy.sha256)
        self.creations=CreationRegistry(self.registry)
        self.intent=self.creations.begin(self.registration,self.claim,host_id='1'*64)
        self.binding=self.creations.bind(self.registration,self.claim,host_id='1'*64,container_id='b'*64)
        self.host='1'*64

    def artifact(self,manifest):
        raw=json.dumps(manifest,sort_keys=True,separators=(',',':')).encode()+b'\n'
        digest=hashlib.sha256(raw).hexdigest();path=self.repo/(digest+'.json')
        path.write_bytes(raw);path.chmod(0o400)
        return self.module.RootLayoutPolicy.load(self.repo,digest)

    def resolve(self):return self.policy.resolve(self.binding,host_identity=lambda:self.host)

    def files(self):
        mapping=self.resolve();group=self.root/mapping['relative_parent'];group.mkdir()
        for name,value in [('cgroup.freeze','0'),('cgroup.kill','0'),('cgroup.events','populated 0\nfrozen 1\n')]:
            (group/name).write_text(value)
        files=self.module.MappedCgroupFiles(self.policy,self.binding,host_identity=lambda:self.host)
        return files,group

    def test_policy_hash_pins_layout_original_host_and_native_guard_artifacts(self):
        expected=hashlib.sha256((json.dumps(self.manifest,sort_keys=True,separators=(',',':'))+'\n').encode()).hexdigest()
        self.assertEqual(self.policy.sha256,expected)
        self.assertEqual(self.policy.native_policy_sha256,'a'*64)
        self.assertEqual(self.policy.guard_sha256,'b'*64)
        self.assertEqual(self.binding['policy_sha256'],expected)

    def test_policy_constructor_cannot_bypass_content_digest(self):
        with self.assertRaises(RecordError):replace(self.policy,cgroup_root='/other')
        with self.assertRaises(RecordError):replace(self.policy,backend='automatic')

    def test_loader_rejects_changed_checksum_and_noncanonical_encoding(self):
        path=self.repo/(self.policy.sha256+'.json');path.chmod(0o600)
        path.write_bytes(b'{}\n');path.chmod(0o400)
        with self.assertRaises(RecordError):self.module.RootLayoutPolicy.load(self.repo,self.policy.sha256)
        raw=json.dumps(self.manifest,indent=2).encode();digest=hashlib.sha256(raw).hexdigest()
        path=self.repo/(digest+'.json');path.write_bytes(raw);path.chmod(0o400)
        with self.assertRaises(RecordError):self.module.RootLayoutPolicy.load(self.repo,digest)

    def test_systemd_mapping_keeps_logical_identity_and_uses_flat_no_dash_root_slice(self):
        mapping=self.resolve();logical=self.binding['parent_cgroup']
        expected='hearth2'+logical.removeprefix('hearth2-')+'.slice'
        self.assertEqual(mapping['logical_parent'],logical)
        self.assertEqual(mapping['daemon_parent'],expected)
        self.assertEqual(mapping['control_group'],'/'+expected)
        self.assertNotIn('-',expected);self.assertEqual(self.binding['parent_cgroup'],logical)

    def test_pre_create_intent_resolves_same_mapping_without_container_id(self):
        self.assertNotIn('container_id',self.intent)
        self.assertEqual(self.policy.resolve(self.intent,host_identity=lambda:self.host),self.resolve())

    def test_direct_backend_projection_is_explicit_and_does_not_reinterpret_old_policy(self):
        direct=self.artifact({**self.manifest,'backend':'direct','control_group_prefix':'/delegated'})
        with self.assertRaises(RecordError):direct.resolve(self.binding,host_identity=lambda:self.host)
        # Independent synthetic policy context, not authorization to rebind DB.
        context={**self.binding,'policy_sha256':direct.sha256}
        mapping=direct.resolve(context,host_identity=lambda:self.host)
        self.assertEqual(mapping['daemon_parent'],'/delegated/'+context['parent_cgroup'])
        self.assertEqual(mapping['control_group'],'/delegated/'+context['parent_cgroup'])

    def test_mapped_direct_daemon_parent_is_absolute_but_file_component_stays_relative(self):
        direct=self.artifact({**self.manifest,'backend':'direct','control_group_prefix':'/delegated'})
        context={**self.binding,'policy_sha256':direct.sha256}
        files=self.module.MappedCgroupFiles(direct,context,host_identity=lambda:self.host)
        group=self.root/context['parent_cgroup'];group.mkdir();(group/'cgroup.kill').write_text('0')
        self.assertEqual(files.daemon_parent(context['parent_cgroup']),'/delegated/'+context['parent_cgroup'])
        files.kill(context['parent_cgroup'])
        self.assertEqual((group/'cgroup.kill').read_text(),'1')

    def test_wrong_policy_or_new_host_cannot_choose_another_parent(self):
        with self.assertRaises(RecordError):self.policy.resolve({**self.binding,'policy_sha256':'c'*64},host_identity=lambda:self.host)
        self.host='2'*64
        with self.assertRaises(RecordError):self.resolve()

    def test_unknown_backend_nested_systemd_prefix_and_traversal_are_refused(self):
        for changes in [{'backend':'auto'},{'control_group_prefix':'/other.slice'},
                {'cgroup_root':'/sys/fs/cgroup/../other'},{'cgroup_root':'/'},
                {'control_group_prefix':'/../other'},{'version':True},{'token':'fake'}]:
            with self.subTest(changes=changes),self.assertRaises(RecordError):
                self.module.RootLayoutPolicy.encode({**self.manifest,**changes})

    def test_private_root_file_permissions_symlink_and_checksum_are_required(self):
        path=self.repo/(self.policy.sha256+'.json');path.chmod(0o600)
        with self.assertRaises(RecordError):self.module.RootLayoutPolicy.load(self.repo,self.policy.sha256)
        path.chmod(0o400);self.repo.chmod(0o755)
        with self.assertRaises(RecordError):self.module.RootLayoutPolicy.load(self.repo,self.policy.sha256)
        self.repo.chmod(0o700);path.unlink();outside=Path(self.tmp.name)/'outside';outside.write_bytes(b'{}')
        path.symlink_to(outside)
        with self.assertRaises(RecordError):self.module.RootLayoutPolicy.load(self.repo,self.policy.sha256)

    def test_mapped_files_open_only_actual_bound_parent_not_logical_or_other_group(self):
        files,group=self.files();logical=self.binding['parent_cgroup']
        files.freeze(logical);files.kill(logical)
        self.assertEqual((group/'cgroup.freeze').read_text(),'1')
        self.assertEqual((group/'cgroup.kill').read_text(),'1')
        self.assertEqual(files.state(logical),{'populated':0,'frozen':1})
        self.assertFalse((self.root/logical).exists())
        with self.assertRaises(RecordError):files.freeze('hearth2-'+'0'*64)

    def test_mapped_backend_rechecks_host_and_exact_binding_before_io(self):
        files,group=self.files();self.host='2'*64
        with self.assertRaises(RecordError):files.freeze(self.binding['parent_cgroup'])
        self.assertEqual((group/'cgroup.freeze').read_text(),'0')
        self.host='1'*64
        with self.assertRaises(RecordError):files.verify_binding({**self.binding,'container_id':'c'*64})

    def test_mapped_parent_symlink_still_cannot_escape_descriptor_confinement(self):
        files,group=self.files()
        for path in group.iterdir():path.unlink()
        group.rmdir();outside=Path(self.tmp.name)/'outside';outside.mkdir()
        (outside/'cgroup.freeze').write_text('0');group.symlink_to(outside,target_is_directory=True)
        with self.assertRaises(RecordError):files.freeze(self.binding['parent_cgroup'])
        self.assertEqual((outside/'cgroup.freeze').read_text(),'0')

    def guard(self,parent=None):
        files,group=self.files();mapping=self.resolve()
        daemon=LayoutDaemon(self.binding,files,mapping['daemon_parent'] if parent is None else parent)
        root=Path(self.tmp.name)/'evidence';root.mkdir(mode=0o700)
        evidence=GuardEvidenceStore(root,clock=lambda:self.time)
        return RootKernelGuard(files,daemon,host_identity=lambda:self.host,clock=lambda:self.time,evidence=evidence),daemon,group

    def test_kernel_guard_compares_daemon_parent_to_explicit_mapping(self):
        guard,daemon,group=self.guard();result=guard.enforce(self.binding)
        self.assertFalse(daemon.present)
        self.assertEqual(result['parent_cgroup'],self.binding['parent_cgroup'])
        self.assertEqual((group/'cgroup.kill').read_text(),'1')

    def test_wrong_daemon_parent_is_not_removed_even_if_logical_name_matches(self):
        guard,daemon,group=self.guard(parent=self.binding['parent_cgroup'])
        with self.assertRaises(RecordError):guard.enforce(self.binding)
        self.assertTrue(daemon.present);self.assertEqual((group/'cgroup.kill').read_text(),'1')

    def test_layout_observation_must_match_original_host_parent_path_and_be_fresh(self):
        mapping=self.resolve()
        proof={'host_id':self.host,'daemon_parent':mapping['daemon_parent'],'control_group':mapping['control_group'],
            'observed_at':self.time.isoformat(),'references':['root:actual-layout-inspection']}
        result=self.policy.verify_observation(self.binding,proof,host_identity=lambda:self.host,clock=lambda:self.time)
        self.assertEqual(result['layout_state'],'matched')
        for changes in [{'control_group':'/wrong'},{'daemon_parent':self.binding['parent_cgroup']},
                {'host_id':'2'*64},{'observed_at':(self.time-timedelta(seconds=61)).isoformat()}]:
            with self.subTest(changes=changes),self.assertRaises(RecordError):
                self.policy.verify_observation(self.binding,{**proof,**changes},host_identity=lambda:self.host,clock=lambda:self.time)

    def test_restore_preserves_original_mapping_and_never_adopts_new_host(self):
        original=self.resolve();bundle=Path(self.tmp.name)/'layout.json';target=Path(self.tmp.name)/'layout-restored.db'
        export_record(self.path,bundle);restore_record(bundle,target,controller_stopped=True)
        restored=Store(target,clock=lambda:self.time)
        binding=CreationRegistry(DispatchRegistry(restored,self.controller)).read(self.claim['run_id'])
        self.assertEqual(self.policy.resolve(binding,host_identity=lambda:self.host),original)
        with self.assertRaises(RecordError):self.policy.resolve(binding,host_identity=lambda:'2'*64)


if __name__=='__main__':unittest.main()
