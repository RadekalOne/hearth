"""Private filesystem fixtures with explicit fake root/readonly-mount facts."""
from dataclasses import replace
from datetime import datetime, timezone, timedelta
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from hearth2.store import RecordError


class RootfsSourceTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('hearth2.rootfs_source'), 'rootfs source missing')
        from hearth2 import rootfs_source
        self.module = rootfs_source
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)/'view'; self.root.mkdir()
        (self.root/'opt').mkdir(); self.file = self.root/'opt/bootstrap'
        self.file.write_bytes(b'PRIVATE BOOTSTRAP NOT EXECUTED'); self.file.chmod(0o555)
        (self.root/'opt').chmod(0o555); self.root.chmod(0o555)
        self.addCleanup(lambda: ((self.root/'opt').chmod(0o700), self.root.chmod(0o700)))
        self.now = datetime(2026,11,1,23,10,tzinfo=timezone.utc)
        self.host = '1'*64; self.image = 'sha256:'+'a'*64; self.cid = 'b'*64
        self.calls = []; self.changes = {}; self.uid = 0; self.readonly = True; self.crossmount = False
        env = {'__name__':'private_fixture'}; exec(self.module.PROGRAM, env)
        test = self
        class FakeRootOS:
            def __getattr__(_, key): return getattr(os, key)
            def getuid(_): return test.uid
            def geteuid(_): return test.uid
            def fstatvfs(_, fd): return SimpleNamespace(f_flag=os.ST_RDONLY if test.readonly else 0)
            def fstat(_, fd):
                value = os.fstat(fd)
                return SimpleNamespace(**{k:(0 if k in {'st_uid','st_gid'} else getattr(value,k)) for k in dir(value) if k.startswith('st_')})
            def stat(_, path, **kwargs):
                value = os.stat(path, **kwargs)
                return SimpleNamespace(**{k:(0 if k in {'st_uid','st_gid'} else getattr(value,k)) for k in dir(value) if k.startswith('st_')})
        env['os'] = FakeRootOS(); self.env = env
        descriptor = os.open(self.root, os.O_RDONLY|os.O_DIRECTORY)
        try:
            root_stat = os.fstat(descriptor); mount = env['mount_id'](descriptor)
        finally: os.close(descriptor)
        namespaces = tuple((name, os.stat('/proc/self/ns/'+name).st_ino) for name in ['user','pid','mnt','cgroup'])
        boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
        self.anchor = self.module.RootfsViewEnrollment(self.host, boot, namespaces, self.image, None,
            str(self.root), root_stat.st_dev, root_stat.st_ino, root_stat.st_ctime_ns, mount,
            ('/opt/bootstrap',), 'private:independent-fixture-enrollment')
        class Command:
            def run(_, args):
                test.calls.append(args)
                enrollment = json.loads(args[-2]); path = args[-1]
                result = env['measure'](enrollment, path)
                return json.dumps({**result, **test.changes}).encode()
        self.command = Command()
        self.source = self.module.RootfsFileMeasurements((self.anchor,), self.command,
            host_identity=lambda:self.host, clock=lambda:self.now)

    def read(self, cid=None, path='/opt/bootstrap'): return self.source.observe(self.image, cid, path)

    def test_measures_actual_private_bytes_through_nofollow_descriptors(self):
        fact = self.read()
        self.assertEqual(fact['sha256'], hashlib.sha256(self.file.read_bytes()).hexdigest())
        self.assertEqual((fact['mode'],fact['uid'],fact['size']), (0o555,0,self.file.stat().st_size))
        self.assertEqual((fact['image_id'],fact['container_id'],fact['path']), (self.image,None,'/opt/bootstrap'))
        self.assertNotIn('PRIVATE BOOTSTRAP', str(fact))
        self.assertEqual(self.calls[0][:3], ['-I','-S','-c'])
        self.assertEqual(self.calls[0][3], self.module.PROGRAM)

    def test_missing_enrollment_and_wrong_image_cid_or_unapproved_path_fail_before_command(self):
        for image,cid,path in [(self.image,self.cid,'/opt/bootstrap'),('sha256:'+'c'*64,None,'/opt/bootstrap'),
                               (self.image,None,'/etc/secret'),(self.image,None,'/opt/../bootstrap')]:
            with self.assertRaises(RecordError): self.source.observe(image,cid,path)
        self.assertEqual(self.calls, [])
        empty = self.module.RootfsFileMeasurements(host_identity=lambda:self.host,clock=lambda:self.now)
        with self.assertRaises(RecordError): empty.observe(self.image,None,'/opt/bootstrap')

    def test_container_view_must_be_separately_enrolled(self):
        anchor = replace(self.anchor, container_id=self.cid)
        self.source = self.module.RootfsFileMeasurements((self.anchor,anchor),self.command,host_identity=lambda:self.host,clock=lambda:self.now)
        self.assertEqual(self.read(self.cid)['container_id'], self.cid)

    def test_wrong_host_boot_namespace_inode_or_mount_never_passes(self):
        original = self.anchor
        for changes in [dict(boot_id='11111111-1111-4111-8111-111111111111'),
                        dict(root_inode=original.root_inode+1), dict(root_ctime_ns=original.root_ctime_ns+1),
                        dict(root_mount_id=original.root_mount_id+1),
                        dict(namespaces=tuple((n,v+1) for n,v in original.namespaces))]:
            anchor = replace(original, **changes)
            source = self.module.RootfsFileMeasurements((anchor,),self.command,host_identity=lambda:self.host,clock=lambda:self.now)
            with self.assertRaises((RecordError,ValueError)): source.observe(self.image,None,'/opt/bootstrap')
        self.host = '2'*64
        with self.assertRaises(RecordError): self.read()

    def test_nonroot_or_readwrite_mount_is_refused(self):
        self.uid = 1000
        with self.assertRaises((RecordError,ValueError)): self.read()
        self.uid = 0; self.readonly = False
        with self.assertRaises((RecordError,ValueError)): self.read()

    def test_file_and_ancestor_symlinks_fifo_and_hardlinks_are_refused(self):
        parent=self.file.parent; parent.chmod(0o755)
        self.file.unlink(); self.file.symlink_to('/outside');parent.chmod(0o555)
        with self.assertRaises((RecordError,ValueError,OSError)): self.read()
        parent.chmod(0o755);self.file.unlink(); os.mkfifo(self.file);parent.chmod(0o555)
        with self.assertRaises((RecordError,ValueError,OSError)): self.read()
        parent.chmod(0o755);self.file.unlink(); self.file.write_bytes(b'x'); self.file.chmod(0o555)
        os.link(self.file,self.root/'opt/hardlink');parent.chmod(0o555)
        with self.assertRaises((RecordError,ValueError,OSError)): self.read()

    def test_digest_metadata_and_helper_receipt_are_validated(self):
        for changes in [dict(sha256='bad'),dict(uid=1000),dict(mode=0o777),dict(size=0),
                        dict(root_inode=self.anchor.root_inode+1),dict(path='/wrong'),dict(extra=True)]:
            self.changes = changes
            with self.assertRaises(RecordError): self.read()

    def test_unsupported_enrollment_types_and_duplicate_targets_refuse(self):
        for changes in [dict(paths=['/opt/bootstrap']),dict(root_mount_id=True),dict(root_path='/tmp/../root'),
                        dict(namespaces=list(self.anchor.namespaces)),dict(paths=('/opt/../bootstrap',))]:
            with self.assertRaises(RecordError): replace(self.anchor, **changes)
        with self.assertRaises(RecordError): self.module.RootfsFileMeasurements((self.anchor,self.anchor),self.command,host_identity=lambda:self.host,clock=lambda:self.now)

    def test_clock_or_host_change_during_command_is_refused(self):
        command = self.command
        test = self
        class Drift:
            def run(_,args):
                result = command.run(args); test.host = '2'*64; return result
        source = self.module.RootfsFileMeasurements((self.anchor,),Drift(),host_identity=lambda:self.host,clock=lambda:self.now)
        with self.assertRaises(RecordError): source.observe(self.image,None,'/opt/bootstrap')

    def test_final_target_is_opened_with_opath_before_any_read_open(self):
        operations=[];proxy=self.env['os']
        class Spy:
            def __getattr__(_,key): return getattr(proxy,key)
            def open(_,path,flags,*args,**kwargs):
                operations.append((path,flags));return os.open(path,flags,*args,**kwargs)
        self.env['os']=Spy();self.read()
        target=[flags for path,flags in operations if path=='bootstrap']
        self.assertEqual(len(target),1)
        self.assertTrue(target[0]&os.O_PATH,'must validate inode type without activating a device')

    def test_nested_mount_and_ancestor_symlink_are_refused(self):
        mount=self.env['mount_id']
        self.env['mount_id']=lambda fd: mount(fd)+(1 if os.readlink('/proc/self/fd/'+str(fd)).endswith('bootstrap') else 0)
        with self.assertRaises(ValueError):self.read()
        self.env['mount_id']=mount
        self.root.chmod(0o755);(self.root/'alias').symlink_to('opt');self.root.chmod(0o555)
        anchor=replace(self.anchor,root_ctime_ns=self.root.stat().st_ctime_ns,paths=('/alias/bootstrap',))
        source=self.module.RootfsFileMeasurements((anchor,),self.command,host_identity=lambda:self.host,clock=lambda:self.now)
        with self.assertRaises((RecordError,ValueError,OSError)):source.observe(self.image,None,'/alias/bootstrap')

    def test_file_mutation_during_read_is_not_accepted(self):
        proxy=self.env['os'];test=self;mutated=False
        class Change:
            def __getattr__(_,key):return getattr(proxy,key)
            def read(_,fd,count):
                nonlocal mutated
                block=os.read(fd,count)
                if not mutated:
                    mutated=True;test.file.chmod(0o755);test.file.write_bytes(b'changed');test.file.chmod(0o555)
                return block
        self.env['os']=Change()
        with self.assertRaises((RecordError,ValueError)):self.read()

    def test_size_limit_and_invalid_file_mode_are_checked_before_read(self):
        self.file.chmod(0o755);self.file.write_bytes(b'x'*(8*1024*1024));self.file.chmod(0o555)
        self.assertEqual(self.read()['size'],8*1024*1024)
        self.file.chmod(0o755);self.file.write_bytes(b'x'*(8*1024*1024+1));self.file.chmod(0o555)
        with self.assertRaises(ValueError):self.read()
        self.file.chmod(0o755)
        with self.assertRaises(ValueError):self.read()


if __name__ == '__main__': unittest.main()
