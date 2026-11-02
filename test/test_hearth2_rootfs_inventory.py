"""Whole-view inventory fixtures; no real root/mount or credential acceptance."""
from dataclasses import replace
from contextlib import contextmanager
import hashlib
import importlib.util
import json
import os
from datetime import timedelta
from pathlib import Path
import unittest

import test_hearth2_rootfs_source as fixtures
from hearth2.credential_policy import CredentialAuditRequirements
from hearth2.store import RecordError, safe_payload


class RootfsInventoryTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('hearth2.rootfs_inventory'),'whole rootfs inventory missing')
        fixtures.RootfsSourceTests.setUp(self)
        from hearth2 import rootfs_inventory
        self.inventory_module=rootfs_inventory
        self.policy_value={'version':1,'kind':'hearth2-credential-audit-requirements-v1',
            'image_id':self.image,'native_profile_sha256':'b'*64,'rootfs_audit_manifest_sha256':'c'*64,
            'consumer_audit_manifest_sha256':'d'*64,'parser_closure_sha256':'e'*64,
            'audit_authority_reference':'private:auditor','limits':{'sources':4096,'bytes':67108864,'consumers':32,'seconds':5}}
        self.requirements=self.policy()
        self.enrollment=rootfs_inventory.RootfsInventoryEnrollment(self.anchor,self.requirements.sha256,'private:whole-view-authority')
        env={'__name__':'private_fixture'};exec(rootfs_inventory.PROGRAM,env);env['os']=self.env['os'];self.inventory_env=env
        test=self
        class Command:
            def run(_,args):
                test.calls.append(args);result=env['inventory'](json.loads(args[-1]))
                return json.dumps({**result,**test.changes}).encode()
        self.command=Command()
        self.scanner=self.scanner_for(self.enrollment)

    def policy(self,**limits):
        value={**self.policy_value,'limits':{**self.policy_value['limits'],**limits}}
        digest=hashlib.sha256(CredentialAuditRequirements.encode(value)).hexdigest()
        return CredentialAuditRequirements(digest,value['image_id'],value['native_profile_sha256'],
            value['rootfs_audit_manifest_sha256'],value['consumer_audit_manifest_sha256'],value['parser_closure_sha256'],
            value['audit_authority_reference'],tuple(sorted(value['limits'].items())))

    def scanner_for(self,enrollment):
        return self.inventory_module.RootfsInventorySource((enrollment,),self.command,
            host_identity=lambda:self.host,clock=lambda:self.now)

    def scan(self):return self.scanner.scan(self.image,None,self.requirements)

    def add_file(self,name,content=b'private fixture',mode=0o444):
        parent=self.file.parent;parent.chmod(0o755);path=parent/name
        path.write_bytes(content);path.chmod(mode);parent.chmod(0o555);return path

    def test_scans_every_entry_twice_and_returns_only_summary_digests(self):
        value=self.scan()
        self.assertEqual((value['entries'],value['files'],value['directories']), (3,1,2))
        self.assertEqual(value['bytes'],self.file.stat().st_size)
        self.assertEqual(value['work_sources'],6);self.assertEqual(value['work_bytes'],2*self.file.stat().st_size)
        self.assertEqual(self.calls[0][:3],['-I','-S','-c'])
        self.assertEqual(len(value['tree_sha256']),64)
        self.assertEqual(value['image_id'],self.image);self.assertIsNone(value['container_id'])
        self.assertNotIn('PRIVATE BOOTSTRAP',str(value));self.assertNotIn('/opt/bootstrap',str(value))

    def test_hidden_unlisted_file_changes_inventory_and_is_not_a_clean_credential_receipt(self):
        before=self.scan();self.add_file('.credential-store.json',b'{"token":"PRIVATE_FAKE_SECRET"}')
        after=self.scan()
        self.assertEqual(after['files'],2);self.assertNotEqual(before['tree_sha256'],after['tree_sha256'])
        self.assertNotIn('PRIVATE_FAKE_SECRET',str(after))
        for key in ['complete','credential_entries','unknown_consumers','scope','states']:
            self.assertNotIn(key,after)
        self.assertFalse(hasattr(self.scanner,'observe'))

    def test_selected_file_enrollment_does_not_authorize_whole_view(self):
        with self.assertRaises(RecordError):self.inventory_module.RootfsInventorySource((self.anchor,),self.command,host_identity=lambda:self.host,clock=lambda:self.now)
        scanner=self.inventory_module.RootfsInventorySource(host_identity=lambda:self.host,clock=lambda:self.now)
        with self.assertRaises(RecordError):scanner.scan(self.image,None,self.requirements)
        self.assertEqual(self.calls,[])

    def test_exact_view_policy_image_and_container_are_required(self):
        with self.assertRaises(RecordError):self.scanner.scan(self.image,self.cid,self.requirements)
        with self.assertRaises(RecordError):self.scanner.scan('sha256:'+'f'*64,None,self.requirements)
        with self.assertRaises(RecordError):self.scanner.scan(self.image,None,self.policy(seconds=4))
        self.assertEqual(self.calls,[])
        enrollment=replace(self.enrollment,view=replace(self.anchor,container_id=self.cid))
        self.assertEqual(self.scanner_for(enrollment).scan(self.image,self.cid,self.requirements)['container_id'],self.cid)

    def test_exact_and_exceeded_work_budgets_fail_without_partial_result(self):
        for limits in [dict(sources=6),dict(sources=5),dict(bytes=2*self.file.stat().st_size),dict(bytes=1)]:
            policy=self.policy(**limits);enrollment=replace(self.enrollment,inventory_policy_sha256=policy.sha256)
            with self.assertRaises((RecordError,ValueError)):
                self.scanner_for(enrollment).scan(self.image,None,policy)

    def test_symlinks_hardlinks_fifo_and_unreadable_directory_are_not_skipped(self):
        parent=self.file.parent
        for kind in ['symlink','hardlink','fifo']:
            parent.chmod(0o755);path=parent/'unsupported'
            if kind=='symlink':path.symlink_to('bootstrap')
            elif kind=='hardlink':os.link(self.file,path)
            else:os.mkfifo(path)
            parent.chmod(0o555)
            with self.assertRaises((RecordError,ValueError,OSError)):self.scan()
            parent.chmod(0o755);path.unlink();parent.chmod(0o555)
        proxy=self.inventory_env['os']
        class Deny:
            def __getattr__(_,key):return getattr(proxy,key)
            def scandir(_,fd):raise PermissionError('private fixture denied')
        self.inventory_env['os']=Deny()
        with self.assertRaises((RecordError,ValueError,OSError)):self.scan()

    def test_mount_crossing_nonroot_and_writable_view_fail(self):
        self.uid=1000
        with self.assertRaises((RecordError,ValueError)):self.scan()
        self.uid=0;self.readonly=False
        with self.assertRaises((RecordError,ValueError)):self.scan()
        self.readonly=True;mount=self.inventory_env['mount_id']
        self.inventory_env['mount_id']=lambda fd:mount(fd)+(1 if os.readlink('/proc/self/fd/'+str(fd)).endswith('bootstrap') else 0)
        with self.assertRaises((RecordError,ValueError)):self.scan()

    def test_mutation_during_scan_and_between_passes_fails(self):
        proxy=self.inventory_env['os'];test=self;changed=False
        class Change:
            def __getattr__(_,key):return getattr(proxy,key)
            def read(_,fd,count):
                nonlocal changed
                data=os.read(fd,count)
                if not changed:
                    changed=True;test.add_file('arrived',b'new')
                return data
        self.inventory_env['os']=Change()
        with self.assertRaises((RecordError,ValueError)):self.scan()

    def test_stable_order_empty_files_and_unsupported_names(self):
        self.add_file('z-last',b'');self.add_file('a-first',b'a')
        before=self.scan();proxy=self.inventory_env['os']
        class Reverse:
            def __getattr__(_,key):return getattr(proxy,key)
            @contextmanager
            def scandir(_,fd):
                with os.scandir(fd) as entries: values=list(entries)
                yield iter(reversed(values))
        self.inventory_env['os']=Reverse()
        self.assertEqual(self.scan()['tree_sha256'],before['tree_sha256'])
        for name in ['bad\nname','back\\slash','bad\x7fname','caf\u00e9']:
            path=self.add_file(name,b'x')
            with self.assertRaises((RecordError,ValueError)):self.scan()
            path.parent.chmod(0o755);path.unlink();path.parent.chmod(0o555)

    def test_typed_summary_binding_and_work_equations_are_checked(self):
        for changes in [dict(entries=True),dict(work_sources=1),dict(work_bytes=1),dict(bytes=-1),
                        dict(files=-1),dict(tree_sha256='bad'),dict(root_inode=self.anchor.root_inode+1),
                        dict(complete=True),dict(uid=1000)]:
            self.changes=changes
            with self.assertRaises(RecordError):self.scan()

    def test_impossible_byte_totals_for_file_count_are_refused(self):
        self.changes={'files':0,'entries':2,'work_sources':4}
        with self.assertRaises(RecordError):self.scan()

    def test_change_only_between_full_passes_is_refused(self):
        proxy=self.inventory_env['os'];test=self;root_lists=0
        class Between:
            def __getattr__(_,key):return getattr(proxy,key)
            @contextmanager
            def scandir(_,fd):
                nonlocal root_lists
                is_root=os.fstat(fd).st_ino==test.anchor.root_inode
                if is_root:root_lists+=1
                with os.scandir(fd) as entries:yield entries
                if is_root and root_lists==2:test.add_file('between-passes',b'new')
        self.inventory_env['os']=Between()
        with self.assertRaises((RecordError,ValueError)):self.scan()

    def test_wall_monotonic_and_host_drift_refuse_measurements(self):
        command=self.command;test=self
        class Late:
            def run(_,args):
                result=command.run(args);test.now+=timedelta(seconds=5);return result
        scanner=self.inventory_module.RootfsInventorySource((self.enrollment,),Late(),host_identity=lambda:self.host,clock=lambda:self.now)
        with self.assertRaises(RecordError):scanner.scan(self.image,None,self.requirements)
        for values in [(10,9),(10,15)]:
            times=iter(values)
            scanner=self.inventory_module.RootfsInventorySource((self.enrollment,),self.command,
                host_identity=lambda:self.host,clock=lambda:self.now,monotonic=lambda:next(times))
            with self.assertRaises(RecordError):scanner.scan(self.image,None,self.requirements)
        class Moved:
            def run(_,args):
                result=command.run(args);test.host='2'*64;return result
        scanner=self.inventory_module.RootfsInventorySource((self.enrollment,),Moved(),host_identity=lambda:self.host,clock=lambda:self.now)
        with self.assertRaises(RecordError):scanner.scan(self.image,None,self.requirements)

    def test_deeply_immutable_enrollment_and_no_duplicate_targets(self):
        with self.assertRaises(RecordError):replace(self.enrollment,inventory_policy_sha256='unknown')
        with self.assertRaises(RecordError):replace(self.enrollment,authority_reference=' ')
        with self.assertRaises(RecordError):self.inventory_module.RootfsInventorySource((self.enrollment,self.enrollment),self.command,host_identity=lambda:self.host,clock=lambda:self.now)


if __name__=='__main__':unittest.main()
