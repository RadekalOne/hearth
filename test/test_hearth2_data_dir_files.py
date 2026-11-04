"""Bounded reads of fake credential-shaped files in private POSIX fixtures."""
from dataclasses import asdict
from datetime import datetime,timezone
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).parents[1]/'mcp/memory'))
from hearth2.credential_coverage import CoverageScope,CoverageSource,CoverageRequirements
from hearth2.credential_sources import SourceContext
from hearth2.data_dir_metadata import RootDirectoryView,_mount_id
from hearth2.store import RecordError


@unittest.skipUnless(os.name=='posix' and hasattr(os,'O_PATH'),'POSIX fixture reads')
class DirectoryFileTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('hearth2.data_dir_files'),'bounded file reader missing')
        from hearth2 import data_dir_files
        self.m=data_dir_files
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.root.chmod(0o700)
        self.now=datetime(2026,11,4,tzinfo=timezone.utc)
        fd=os.open(self.root,os.O_RDONLY|os.O_DIRECTORY)
        try:mount=_mount_id(fd)
        finally:os.close(fd)
        self.scope=CoverageScope(SourceContext('sha256:'+'a'*64,None,'b'*64,'c'*64),'ROOT','BATCH','ROUND',mount)
        self.store=CoverageSource('STORE','oauth-store',('auth','prod','en','mcode-public','auth.json'))
        self.state=CoverageSource('STATE','oauth-state',self.store.path[:-1]+('auth-state.json',))
        self.requirements=CoverageRequirements.create(self.scope,(self.store,self.state),(('PAIR',('STORE','STATE')),))

    def write(self,source,data=b'FAKE-ONLY-SECRET'):
        p=self.root.joinpath(*source.path);p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
        return p

    def port(self,**options):
        st=self.root.stat()
        view=RootDirectoryView(self.scope,str(self.root),st.st_dev,st.st_ino,st.st_ctime_ns,st.st_uid,st.st_gid)
        return self.m.DirectoryFileCapture(view,clock=lambda:self.now,monotonic=lambda:0,**options)

    def capture(self,port=None):return (port or self.port()).capture(self.requirements,begin=self.now)

    def test_missing_store_preserves_present_state(self):
        self.write(self.state)
        r=self.capture()
        self.assertEqual(r.state,'files-observed')
        self.assertEqual((r.summary.absent_sources,r.summary.present_sources),(1,1))
        self.assertEqual(r.bytes_read,32)
        self.assertEqual(r.file_outcomes,((0,'absent',None),(1,'present',None)))

    def test_empty_existing_file_is_present_and_read_twice(self):
        self.write(self.store,b'');r=self.capture()
        self.assertEqual(r.summary.present_sources,1)
        self.assertEqual(r.bytes_read,0);self.assertEqual(r.read_attempts,2)

    def test_exact_size_boundaries_are_not_truncated_success(self):
        for size,status,reason in [(65535,'present',None),(65536,'unreadable','oversize'),(65537,'unreadable','oversize'),(200000,'unreadable','oversize')]:
            with self.subTest(size=size):
                self.write(self.store,b'x'*size);r=self.capture()
                self.assertEqual(r.file_outcomes[0],(0,status,reason))
                self.assertLessEqual(r.bytes_read,2*65537)

    def test_only_mapped_candidate_bodies_are_read(self):
        self.write(self.state)
        other=self.root/'sessions';other.mkdir();(other/'private').write_bytes(b'UNRELATED-SECRET')
        real=os.read
        def read(fd,n):
            name=os.readlink('/proc/self/fd/'+str(fd))
            self.assertTrue(name.endswith('/auth-state.json'),name)
            return real(fd,n)
        with patch('os.read',side_effect=read):r=self.capture()
        self.assertEqual(r.summary.present_sources,1)

    def test_permission_denial_is_unreadable_never_absent(self):
        self.write(self.store)
        with patch('os.read',side_effect=PermissionError('FAKE-ONLY-SECRET')):r=self.capture()
        self.assertEqual(r.file_outcomes[0],(0,'unreadable','permission'))
        self.assertEqual(r.summary.absent_sources,1)

    def test_io_error_is_unreadable_and_does_not_erase_other_source(self):
        self.write(self.store);self.write(self.state)
        real=os.read
        def read(fd,n):
            if os.readlink('/proc/self/fd/'+str(fd)).endswith('/auth.json'):raise OSError('FAKE-ONLY-SECRET')
            return real(fd,n)
        with patch('os.read',side_effect=read):r=self.capture()
        self.assertEqual((r.summary.unreadable_sources,r.summary.present_sources),(1,1))
        self.assertEqual(r.file_outcomes[0],(0,'unreadable','io'))

    def test_symlink_fifo_and_hardlink_are_never_read(self):
        for kind in ('symlink','fifo','hardlink'):
            with self.subTest(kind=kind):
                p=self.write(self.store);p.unlink()
                if kind=='symlink':p.symlink_to('/does-not-exist')
                elif kind=='fifo':os.mkfifo(p)
                else:
                    target=p.parent/'other';target.write_bytes(b'FAKE');os.link(target,p)
                with patch('os.read',side_effect=AssertionError('unsafe body open')):r=self.capture()
                self.assertEqual(r.summary.unsupported_sources,1)
                p.unlink()
                if kind=='hardlink':target.unlink()

    def test_content_change_with_same_metadata_is_detected(self):
        self.write(self.store,b'FAKE');real=os.read;nonempty=[]
        def read(fd,n):
            raw=real(fd,n)
            if raw:
                nonempty.append(raw)
                if len(nonempty)>1:return b'EVIL'
            return raw
        with patch('os.read',side_effect=read):r=self.capture()
        self.assertEqual((r.state,r.reason),('unscanned','changed'));self.assertIsNone(r.summary)

    def test_file_mutation_during_read_invalidates_root(self):
        p=self.write(self.store,b'FAKE');real=os.read;done=[]
        def read(fd,n):
            raw=real(fd,n)
            if not done:done.append(True);p.write_bytes(b'EVIL')
            return raw
        with patch('os.read',side_effect=read):r=self.capture()
        self.assertEqual(r.state,'unscanned');self.assertIsNone(r.summary)

    def test_replacement_at_same_name_is_not_read_as_original(self):
        p=self.write(self.store);real=os.open;done=[]
        def opened(path,flags,*a,**kw):
            if path=='auth.json':
                done.append(True)
                if len(done)==2:p.unlink();p.write_bytes(b'REPLACED')
            return real(path,flags,*a,**kw)
        with patch('os.open',side_effect=opened):r=self.capture()
        self.assertEqual(r.state,'unscanned');self.assertIsNone(r.summary)

    def test_byte_budget_equality_invalidates_whole_root(self):
        self.write(self.store,b'AB')
        r=self.capture(self.port(max_bytes=4))
        self.assertEqual((r.state,r.reason),('unscanned','budget-acquisition'));self.assertIsNone(r.summary)
        self.assertEqual(self.capture(self.port(max_bytes=5)).summary.present_sources,1)

    def test_reads_consume_shared_work_budget(self):
        self.write(self.store,b'A')
        r=self.capture(self.port(max_entries=25))
        self.assertEqual((r.state,r.reason),('unscanned','budget-acquisition'))

    def test_invalid_byte_limits_refuse_before_any_directory_open(self):
        for limit in [True,0,1048577,1.5]:
            port=self.port(max_bytes=limit)
            with patch('os.open',side_effect=AssertionError('opened before validation')):
                with self.assertRaises(RecordError):self.capture(port)

    def test_default_unconfigured_refuses(self):
        with self.assertRaises(RecordError):self.m.DirectoryFileCapture(clock=lambda:self.now).capture(self.requirements,begin=self.now)

    def test_read_failure_closes_every_descriptor(self):
        self.write(self.store);before=len(os.listdir('/proc/self/fd'))
        with patch('os.read',side_effect=OSError('FAKE')):self.capture()
        self.assertEqual(len(os.listdir('/proc/self/fd')),before)

    def test_later_source_cannot_change_earlier_source_in_final_pass(self):
        p=self.write(self.store,b'FAKE');self.write(self.state,b'STATE')
        real=os.read;states=[]
        def read(fd,n):
            raw=real(fd,n)
            if raw and os.readlink('/proc/self/fd/'+str(fd)).endswith('/auth-state.json'):
                states.append(True)
                if len(states)==2:
                    before=p.stat();p.write_bytes(b'EVIL')
                    os.utime(p,ns=(before.st_atime_ns,before.st_mtime_ns+1000000000))
            return raw
        with patch('os.read',side_effect=read):r=self.capture()
        self.assertEqual((r.state,r.reason),('unscanned','changed'))
        self.assertIsNone(r.summary)

    def test_read_descriptor_mount_is_checked_before_body_read(self):
        import fcntl
        self.write(self.store)
        original=self.m._mount_id
        def mount(fd):
            if (os.readlink('/proc/self/fd/'+str(fd)).endswith('/auth.json')
                    and not fcntl.fcntl(fd,fcntl.F_GETFL)&os.O_PATH):return self.scope.root_mount_id+1
            return original(fd)
        with patch.object(self.m,'_mount_id',side_effect=mount),patch('os.read',side_effect=AssertionError('unverified mount read')):
            r=self.capture()
        self.assertEqual(r.state,'unscanned')

    def test_short_reads_are_combined_without_truncation(self):
        self.write(self.store,b'FAKE');real=os.read
        with patch('os.read',side_effect=lambda fd,n:real(fd,min(n,1))):r=self.capture()
        self.assertEqual(r.bytes_read,8)
        self.assertEqual(r.file_outcomes[0],(0,'present',None))
        self.assertEqual(r.read_attempts,10)

    def test_reopen_fstat_failure_is_unreadable_and_does_not_leak(self):
        import fcntl
        self.write(self.store);real=os.fstat
        def value(fd):
            if (os.readlink('/proc/self/fd/'+str(fd)).endswith('/auth.json')
                    and not fcntl.fcntl(fd,fcntl.F_GETFL)&os.O_PATH):raise OSError('FAKE-ONLY-SECRET')
            return real(fd)
        before=len(os.listdir('/proc/self/fd'))
        with patch('os.fstat',side_effect=value):r=self.capture()
        self.assertEqual(r.file_outcomes[0],(0,'unreadable','io'))
        self.assertEqual(len(os.listdir('/proc/self/fd')),before)

    def test_public_results_and_errors_redact_file_material(self):
        self.write(self.store);r=self.capture();text=repr(r)+json.dumps(asdict(r))
        for secret in ['FAKE-ONLY-SECRET',str(self.root),'auth.json','STORE','ROUND',self.scope.context.image_id]:self.assertNotIn(secret,text)
        self.assertEqual(len(r.summary.unresolved_coverage_families),3)
        for name in ['observe','complete','credential_entries','start','raw','sha256']:
            self.assertFalse(hasattr(r,name))

    def test_unsafe_sibling_does_not_become_absence_in_file_outcomes(self):
        self.write(self.state)
        (self.root.joinpath(*self.state.path[:-1])/'unsafe').symlink_to('/missing')
        r=self.capture()
        self.assertEqual(r.summary.absent_sources,0)
        self.assertEqual(r.file_outcomes,((0,'unscanned',None),(1,'present',None)))


if __name__=='__main__':unittest.main()
