"""Sealed guard ABI with private files and fake daemon; no installed runtime."""
import copy
from datetime import timedelta
import hashlib
import importlib
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch
import test_hearth2_claims as fixtures
from hearth2.store import RecordError,safe_payload,timestamp
from hearth2.dispatch import DispatchRegistry
from hearth2.creation import CreationRegistry
from hearth2.root_layout import RootLayoutPolicy


class GuardEntrypointTests(unittest.TestCase):
    def setUp(self):
        fixtures.ClaimTests.setUp(self)
        self.assertIsNotNone(importlib.util.find_spec('hearth2.guard_entrypoint'),'sealed guard entrypoint missing')
        self.module=importlib.import_module('hearth2.guard_entrypoint')
        self.repo=Path(self.tmp.name)/'policy';self.repo.mkdir(mode=0o700)
        self.groups=Path(self.tmp.name)/'groups';self.groups.mkdir()
        self.evidence=Path(self.tmp.name)/'evidence';self.evidence.mkdir(mode=0o700)
        self.sealdir=Path(self.tmp.name)/'seals';self.sealdir.mkdir(mode=0o700)
        manifest={'version':1,'host_id':'1'*64,'backend':'systemd-root-slice','cgroup_root':str(self.groups),
            'control_group_prefix':'/','native_policy_sha256':'a'*64,'guard_sha256':'b'*64}
        raw=RootLayoutPolicy.encode(manifest);digest=hashlib.sha256(raw).hexdigest()
        path=self.repo/(digest+'.json');path.write_bytes(raw);path.chmod(0o400)
        self.policy=RootLayoutPolicy.load(self.repo,digest)
        self.claim=self.store.claim(self.controller,self.task['id'],expected_revision=1,request_id='entry')
        registry=DispatchRegistry(self.store,self.controller)
        registration=registry.prepare(self.claim,policy_sha256=digest)
        self.binding=CreationRegistry(registry).bind(registration,self.claim,host_id='1'*64,container_id='c'*64)
        self.host='1'*64;self.uid=0
        self.seals=self.module.RootGuardBindings(self.sealdir,clock=lambda:self.time)
        self.seal=lambda:self.seals.seal(self.binding,self.policy,str(self.evidence),host_identity=lambda:self.host)
        parent=self.policy.resolve(self.binding,host_identity=lambda:self.host)['relative_parent']
        self.group=self.groups/parent;self.group.mkdir()
        for name,data in [('cgroup.freeze','0'),('cgroup.kill','0'),('cgroup.events','populated 0\nfrozen 1\n')]:
            (self.group/name).write_text(data)
        test=self
        class Daemon:
            def __init__(_):_.calls=[];_.present=True;_.failure=False
            def inspect(_,container):
                _.calls.append('inspect')
                if _.failure:raise RecordError('private daemon failure')
                return {'Id':container,'Config':{'Labels':{'hearth2.run':test.binding['run_id'],
                    'hearth2.creation_epoch':test.binding['creation_epoch'],'hearth2.policy_sha256':digest,
                    'hearth2.workload':test.binding['workload_id']}},'HostConfig':{'CgroupParent':parent},
                    'State':{'Status':'created','Running':False,'Pid':0,'ExitCode':0}}
            def remove(_,container):_.calls.append('remove');_.present=False
            def absent(_,container):_.calls.append('absent');return not _.present
        self.daemon=Daemon()
        self.runtime=self.module.RootGuardRuntime(self.seals,host_identity=lambda:self.host,clock=lambda:self.time,
            euid=lambda:self.uid,commands=self.daemon)

    def main(self,args=None,runtime=True):
        out=io.StringIO();err=io.StringIO()
        code=self.module.main(['--binding-json',safe_payload(self.binding)] if args is None else args,
            runtime=self.runtime if runtime else None,stdout=out,stderr=err)
        return code,out.getvalue(),err.getvalue()

    def test_durable_exact_seal_is_idempotent_and_readback_has_original_layout(self):
        first=self.seal();self.assertEqual(first,self.seal())
        record=self.seals.read(self.binding,host_identity=lambda:self.host)
        self.assertEqual(record['binding'],self.binding);self.assertEqual(record['layout']['cgroup_root'],str(self.groups))
        self.assertEqual(record['evidence_root'],str(self.evidence))
        self.assertEqual(len(list(self.sealdir.iterdir())),1)

    def test_same_guard_cannot_be_resealed_to_other_id_layout_or_evidence_root(self):
        self.seal()
        with self.assertRaises(RecordError):self.seals.seal({**self.binding,'container_id':'d'*64},self.policy,str(self.evidence),host_identity=lambda:self.host)
        other=Path(self.tmp.name)/'other';other.mkdir(mode=0o700)
        with self.assertRaises(RecordError):self.seals.seal(self.binding,self.policy,str(other),host_identity=lambda:self.host)

    def test_successful_entry_uses_sealed_layout_after_policy_file_disappears(self):
        self.seal()
        for p in self.repo.iterdir():p.unlink()
        self.repo.rmdir();self.time=timestamp(self.binding['deadline_at'])
        code,out,err=self.main()
        self.assertEqual(code,0);self.assertEqual(err,'');self.assertEqual(json.loads(out)['termination_state'],'observed')
        self.assertFalse(self.daemon.present);self.assertTrue(self.group.exists())
        self.assertEqual((self.group/'cgroup.freeze').read_text(),'1');self.assertEqual((self.group/'cgroup.kill').read_text(),'1')
        self.assertEqual(len(list(self.evidence.glob('*.json'))),2)

    def test_unsealed_cli_arguments_never_authorize_kernel_or_daemon_io(self):
        code,out,err=self.main();self.assertNotEqual(code,0);self.assertEqual(out,'')
        self.assertEqual(self.daemon.calls,[]);self.assertEqual((self.group/'cgroup.kill').read_text(),'0')

    def test_binding_argument_change_or_new_host_is_refused_before_io(self):
        self.seal()
        with self.assertRaises(RecordError):self.runtime.execute({**self.binding,'container_id':'d'*64})
        self.host='2'*64
        code,out,err=self.main();self.assertNotEqual(code,0);self.assertEqual(self.daemon.calls,[])
        self.assertEqual((self.group/'cgroup.kill').read_text(),'0')

    def test_nonroot_identity_cannot_read_seals_or_touch_kernel(self):
        self.seal();self.uid=1000
        with patch.object(self.seals,'read',side_effect=AssertionError('seal read forbidden')):
            code,out,err=self.main()
        self.assertNotEqual(code,0);self.assertEqual(out,'');self.assertEqual(self.daemon.calls,[])

    def test_default_cli_has_no_automatic_runtime_or_daemon_configuration(self):
        self.seal();code,out,err=self.main(runtime=False)
        self.assertNotEqual(code,0);self.assertEqual(out,'');self.assertEqual(self.daemon.calls,[])

    def test_canonical_bounded_abi_rejects_duplicates_extra_flags_and_credentials(self):
        valid=safe_payload(self.binding)
        for args in [[],['--binding-json',valid,'--other'],['--binding-json',json.dumps(self.binding,indent=2)],
                ['--binding-json','{"run_id":"x","run_id":"y"}'],['--binding-json','x'*8193],
                ['--binding-json',safe_payload({**self.binding,'extra':'bad'})]]:
            with self.subTest(args=args[:1]):
                code,out,err=self.main(args);self.assertNotEqual(code,0);self.assertEqual(out,'')
        self.assertEqual(self.daemon.calls,[])

    def test_expiry_execution_retries_kernel_kill_after_daemon_failure_and_retains_parent(self):
        self.seal();self.daemon.failure=True;self.time=timestamp(self.binding['deadline_at'])
        from hearth2.root_layout import MappedCgroupFiles
        calls=[]
        class Files(MappedCgroupFiles):
            def kill(_,parent):calls.append('kill');super().kill(parent)
        self.runtime.files_factory=Files
        code,out,err=self.main();self.assertNotEqual(code,0);self.assertEqual(out,'')
        self.assertEqual(calls,['kill','kill']);self.assertTrue(self.daemon.present);self.assertTrue(self.group.exists())
        self.assertEqual((self.group/'cgroup.freeze').read_text(),'1')

    def test_corrupt_or_symlink_seal_is_unknown_never_adopted(self):
        self.seal();path=next(self.sealdir.iterdir());path.chmod(0o600);path.write_text('{}\n');path.chmod(0o400)
        code,out,err=self.main();self.assertNotEqual(code,0);self.assertEqual(self.daemon.calls,[])
        path.unlink();other=Path(self.tmp.name)/'outside';other.write_text('{}\n');other.chmod(0o400);path.symlink_to(other)
        code,out,err=self.main();self.assertNotEqual(code,0);self.assertEqual((self.group/'cgroup.kill').read_text(),'0')

    def test_no_new_seal_after_deadline_and_no_retroactive_mapping_change(self):
        self.time=timestamp(self.binding['deadline_at'])
        with self.assertRaises(RecordError):self.seal()
        self.assertEqual(list(self.sealdir.iterdir()),[])

    def test_early_guard_invocation_cannot_stop_before_original_deadline(self):
        self.seal();code,out,err=self.main()
        self.assertNotEqual(code,0);self.assertEqual(self.daemon.calls,[])
        self.assertEqual((self.group/'cgroup.kill').read_text(),'0')

    def test_canonical_seal_with_changed_evidence_path_fails_checksum_before_io(self):
        self.seal();path=next(self.sealdir.iterdir());value=json.loads(path.read_text())
        value['evidence_root']=str(Path(self.tmp.name)/'changed');path.chmod(0o600)
        path.write_text(safe_payload(value)+'\n');path.chmod(0o400)
        with self.assertRaisesRegex(RecordError,'checksum'):
            self.seals.read(self.binding,host_identity=lambda:self.host)
        self.assertEqual(self.daemon.calls,[])

    def test_capacity_reserves_stage_and_final_slots_but_exact_retry_ignores_capacity(self):
        class Entries:
            def __enter__(_):return iter(range(4095))
            def __exit__(_,kind,error,trace):return False
        with patch.object(self.module.os,'scandir',return_value=Entries()):
            with self.assertRaisesRegex(RecordError,'capacity'):self.seal()
        self.assertEqual(list(self.sealdir.iterdir()),[])
        first=self.seal()
        with patch.object(self.module.os,'scandir',side_effect=AssertionError('retry must not rescan capacity')):
            self.assertEqual(first,self.seal())

    def test_unowned_staging_collision_is_not_deleted(self):
        path=self.sealdir/('.stage-'+'a'*32);path.write_bytes(b'private foreign staging');path.chmod(0o400)
        with patch.object(self.module.secrets,'token_hex',return_value='a'*32):
            with self.assertRaises(RecordError):self.seal()
        self.assertEqual(path.read_bytes(),b'private foreign staging')
        self.assertEqual(list(self.sealdir.iterdir()),[path])

    def test_directory_sync_failure_retains_final_seal_for_exact_retry(self):
        original=self.module.os.fsync
        import stat,os
        def fail_directory(fd):
            if stat.S_ISDIR(os.fstat(fd).st_mode):raise OSError('private sync fault')
            return original(fd)
        with patch.object(self.module.os,'fsync',side_effect=fail_directory):
            with self.assertRaises(RecordError):self.seal()
        self.assertEqual(len(list(self.sealdir.glob('*.json'))),1)
        self.seal();self.assertEqual(len(list(self.sealdir.iterdir())),1)


if __name__=='__main__':unittest.main()
