"""Real filesystem metadata in private fixtures; never real credential content."""
from dataclasses import asdict, replace
from datetime import datetime, timezone, timedelta
import importlib.util
import json
import os
from pathlib import Path
import socket
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).parents[1]/'mcp/memory'))
from hearth2.credential_coverage import CoverageScope,CoverageSource,CoverageRequirements
from hearth2.credential_sources import SourceContext
from hearth2.store import RecordError


@unittest.skipUnless(os.name=='posix' and hasattr(os,'O_PATH'),'POSIX metadata fixture port')
class DirectoryMetadataTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('hearth2.data_dir_metadata'),'metadata port missing')
        from hearth2 import data_dir_metadata as m
        self.m=m;self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.root.chmod(0o700)
        fd=os.open(self.root,os.O_RDONLY|os.O_DIRECTORY)
        try:mount=m._mount_id(fd)
        finally:os.close(fd)
        self.now=datetime(2026,11,4,tzinfo=timezone.utc)
        self.scope=CoverageScope(SourceContext('sha256:'+'a'*64,None,'b'*64,'c'*64),'ROOT','BATCH','ROUND',mount)
        self.branch=('auth','prod','en','mcode-public')
        self.store=CoverageSource('STORE','oauth-store',self.branch+('auth.json',))
        self.state=CoverageSource('STATE','oauth-state',self.branch+('auth-state.json',))
        self.projection=CoverageSource('PROJECTION','projection-namespaced',('cli-auth','prod','en','local-runtime.auth.json'))
        self.requirements=CoverageRequirements.create(self.scope,(self.store,self.state),(('PAIR',('STORE','STATE')),))

    def write(self,path,data=b'FAKE-NOT-A-REAL-TOKEN'):
        path=self.root.joinpath(*path);path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes(data);return path

    def view(self,**changes):
        st=self.root.stat()
        return self.m.RootDirectoryView(**{**dict(scope=self.scope,root_path=str(self.root),device=st.st_dev,
            inode=st.st_ino,ctime_ns=st.st_ctime_ns,uid=st.st_uid,gid=st.st_gid),**changes})

    def port(self,view=None,**changes):
        return self.m.DirectoryMetadataCapture(view or self.view(),clock=lambda:self.now,monotonic=lambda:0,**changes)

    def capture(self,port=None,requirements=None):
        return (port or self.port()).capture(requirements or self.requirements,begin=self.now)

    def test_absent_namespace_is_measured_and_compacted(self):
        result=self.capture()
        self.assertEqual(result.state,'metadata-observed')
        self.assertEqual((result.summary.absent_sources,result.summary.accounting_work_units),(2,1))
        self.assertEqual(len(result.summary.unresolved_coverage_families),3)
        self.assertGreater(result.metadata_work,0)

    def test_existing_empty_namespace_is_also_proven_absent(self):
        self.root.joinpath(*self.branch).mkdir(parents=True)
        self.assertEqual(self.capture().summary.covered_absent_sources,2)

    def test_missing_store_and_present_state_are_preserved(self):
        self.write(self.state.path)
        result=self.capture()
        self.assertEqual((result.summary.absent_sources,result.summary.present_sources,result.summary.mixed_presence_groups),(1,1,1))

    def test_projection_in_other_branch_survives_auth_absence(self):
        self.write(self.projection.path)
        requirements=CoverageRequirements.create(self.scope,(self.store,self.state,self.projection),(('PAIR',('STORE','STATE')),))
        result=self.capture(requirements=requirements)
        self.assertEqual((result.summary.absent_sources,result.summary.present_sources),(2,1))

    def test_candidate_bodies_are_never_read_and_empty_file_is_present(self):
        self.write(self.store.path,b'');self.write(self.state.path)
        real_open=os.open;real_builtin_open=open;file_opens=[]
        def tracked_open(path,flags,*args,**kwargs):
            if path in ('auth.json','auth-state.json'):file_opens.append(flags)
            return real_open(path,flags,*args,**kwargs)
        def tracked_builtin(path,*args,**kwargs):
            if not str(path).startswith('/proc/self/fdinfo/'):raise AssertionError('candidate body read')
            return real_builtin_open(path,*args,**kwargs)
        with patch('os.open',side_effect=tracked_open),patch('builtins.open',side_effect=tracked_builtin),\
                patch('os.read',side_effect=AssertionError('content read')),patch('subprocess.run',side_effect=AssertionError('launch')):
            result=self.capture()
        self.assertEqual(result.summary.present_sources,2)
        self.assertTrue(file_opens)
        self.assertTrue(all(flags&os.O_PATH for flags in file_opens))

    def test_symlinked_root_and_wrong_original_inode_are_unscanned(self):
        other=self.root/'target';other.mkdir()
        link=self.root/'link';link.symlink_to(other,target_is_directory=True)
        for view in [self.view(inode=self.root.stat().st_ino+1),self.view(root_path=str(link))]:
            result=self.capture(self.port(view))
            self.assertEqual(result.state,'unscanned');self.assertIsNone(result.summary)

    def test_symlinked_parent_is_not_followed(self):
        outside=self.root/'outside';outside.mkdir();(outside/'FAKE').write_bytes(b'FAKE')
        (self.root/'auth').symlink_to(outside,target_is_directory=True)
        result=self.capture()
        self.assertEqual(result.summary.unscanned_sources,2)
        self.assertEqual(result.summary.absent_sources,0)

    def test_socket_sibling_blocks_absence_but_not_present_file(self):
        self.write(self.state.path)
        sock=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);self.addCleanup(sock.close)
        sock.bind(str(self.root.joinpath(*self.branch)/'lease.sock'))
        result=self.capture()
        self.assertEqual((result.summary.present_sources,result.summary.unscanned_sources,result.summary.absent_sources),(1,1,0))

    def test_hardlink_or_symlink_candidate_is_unsupported_not_opened(self):
        target=self.write(self.state.path)
        source=self.root.joinpath(*self.store.path)
        os.link(target,source)
        result=self.capture()
        self.assertEqual(result.summary.unsupported_sources,2)
        self.assertEqual(result.summary.absent_sources,0)

    def test_unmapped_sessions_directory_is_not_descended(self):
        sessions=self.root/'sessions';sessions.mkdir()
        for i in range(150):(sessions/str(i)).write_bytes(b'FAKE')
        real_scandir=os.scandir;visited=[]
        def tracked(fd):
            path=os.readlink('/proc/self/fd/'+str(fd));visited.append(path)
            if path==str(sessions):raise AssertionError('unmapped traversal')
            return real_scandir(fd)
        with patch('os.scandir',side_effect=tracked):result=self.capture()
        self.assertEqual(result.summary.absent_sources,2)
        self.assertNotIn(str(sessions),visited)

    def test_permission_failure_is_unknown_not_absent(self):
        self.write(self.state.path)
        real_scandir=os.scandir
        def denied(fd):
            if os.readlink('/proc/self/fd/'+str(fd)).endswith('/auth'):raise PermissionError('FAKE-SECRET')
            return real_scandir(fd)
        with patch('os.scandir',side_effect=denied):result=self.capture()
        self.assertEqual(result.summary.unscanned_sources,2)
        self.assertEqual(result.summary.absent_sources,0)

    def test_changed_file_or_directory_between_passes_invalidates_root(self):
        target=self.write(self.state.path)
        port=self.port();original=port._pass;calls=[]
        def changed(*args,**kwargs):
            value=original(*args,**kwargs)
            if not calls:target.write_bytes(b'FAKE-CHANGED')
            calls.append(True);return value
        with patch.object(port,'_pass',side_effect=changed):result=self.capture(port)
        self.assertEqual(result.state,'unscanned');self.assertEqual(result.reason,'changed')
        self.assertIsNone(result.summary)

    def test_acquisition_budget_and_accounting_budget_have_different_reasons(self):
        self.assertEqual(self.capture(self.port(max_entries=2)).reason,'budget-acquisition')
        self.write(self.state.path)
        requirements=CoverageRequirements.create(self.scope,(self.store,self.state),(('PAIR',('STORE','STATE')),),work_limit=3)
        result=self.capture(requirements=requirements)
        self.assertEqual(result.state,'unscanned');self.assertEqual(result.reason,'budget-accounting')

    def test_deadline_equality_and_clock_rollback_refuse_partial_success(self):
        for values in [(0,5),(2,1)]:
            times=iter(values);port=self.port();port.monotonic=lambda:next(times)
            result=self.capture(port)
            self.assertEqual(result.state,'unscanned');self.assertEqual(result.reason,'budget-acquisition')

    def test_nonfile_and_outside_mapped_parents_remain_unscanned(self):
        sources=(CoverageSource('ENV','environment',None),CoverageSource('DEEP','pi-auth',('sessions','fake.json')))
        requirements=CoverageRequirements.create(self.scope,sources,())
        result=self.capture(requirements=requirements)
        self.assertEqual(result.summary.unscanned_sources,2)

    def test_default_missing_view_and_foreign_scope_refuse_before_io(self):
        with patch('os.open',side_effect=AssertionError('I/O before binding')):
            with self.assertRaises(RecordError):self.m.DirectoryMetadataCapture(clock=lambda:self.now).capture(self.requirements,begin=self.now)
            view=replace(self.view(),scope=replace(self.scope,root_id='OTHER'))
            with self.assertRaises(RecordError):self.capture(self.port(view))

    def test_output_never_contains_paths_identities_or_file_contents(self):
        self.write(self.state.path)
        result=self.capture();text=json.dumps(asdict(result))+repr(result)+repr(self.view())
        for value in [str(self.root),'FAKE-NOT-A-REAL-TOKEN','STORE','STATE','ROUND',self.scope.context.image_id]:
            self.assertNotIn(value,text)
        for name in ['observe','complete','credential_entries','start']:
            self.assertFalse(hasattr(result,name));self.assertFalse(hasattr(self.port(),name))

    def test_nested_scope_is_validated_before_equality_callbacks(self):
        class Hostile:
            def __ne__(self,other):raise RuntimeError('FAKE-SECRET-CALLBACK')
        request=replace(self.requirements,scope=Hostile())
        with self.assertRaises(RecordError) as caught:self.capture(requirements=request)
        self.assertNotIn('FAKE-SECRET',str(caught.exception))

    def test_reopen_failure_closes_temporary_directory_descriptor(self):
        self.write(self.state.path)
        real_open=os.open;real_stat=os.fstat;failed=[];pending=set()
        def tracked_open(path,flags,*args,**kwargs):
            fd=real_open(path,flags,*args,**kwargs)
            if str(path).startswith('/proc/self/fd/'):pending.add(fd)
            return fd
        def fail_stat(fd):
            if fd in pending and not failed:
                failed.append(fd);raise OSError('FAKE-FAILURE')
            return real_stat(fd)
        before=len(os.listdir('/proc/self/fd'))
        with patch('os.open',side_effect=tracked_open),patch('os.fstat',side_effect=fail_stat):result=self.capture()
        self.assertEqual(result.state,'unscanned')
        self.assertEqual(len(os.listdir('/proc/self/fd')),before)

    def test_case_variant_and_nested_mount_cannot_be_absence(self):
        (self.root/'AUTH').mkdir()
        result=self.capture()
        self.assertEqual(result.summary.unscanned_sources,2)
        self.assertEqual(result.summary.absent_sources,0)
        self.write(self.state.path)
        original=self.m._mount_id
        def different(fd):
            if os.readlink('/proc/self/fd/'+str(fd)).endswith('/auth'):return self.scope.root_mount_id+1
            return original(fd)
        with patch.object(self.m,'_mount_id',side_effect=different):result=self.capture()
        self.assertEqual(result.summary.unscanned_sources,2)

    def test_owner_binding_and_bad_numeric_limits(self):
        self.assertEqual(self.capture(self.port(self.view(uid=self.root.stat().st_uid+1))).reason,'binding')
        for options in [dict(max_entries=True),dict(max_entries=257),dict(timeout_seconds=11)]:
            with self.assertRaises(RecordError):self.capture(self.port(**options))

    def test_reopened_directory_mount_is_independently_checked(self):
        import fcntl
        self.write(self.state.path)
        original=self.m._mount_id
        def different(fd):
            if (os.readlink('/proc/self/fd/'+str(fd)).endswith('/auth')
                    and not fcntl.fcntl(fd,fcntl.F_GETFL)&os.O_PATH):return self.scope.root_mount_id+1
            return original(fd)
        with patch.object(self.m,'_mount_id',side_effect=different):result=self.capture()
        self.assertEqual(result.state,'unscanned')

    def test_review_nested_absence_compaction_is_order_independent(self):
        shallow=CoverageSource('SHALLOW','oauth-store',('auth','prod','en','legacy-auth.json'))
        for sources in [(self.store,shallow),(shallow,self.store)]:
            with self.subTest(order=tuple(s.source_id for s in sources)):
                requirements=CoverageRequirements.create(self.scope,sources,())
                result=self.capture(requirements=requirements)
                self.assertEqual(result.state,'metadata-observed')
                self.assertEqual((result.summary.absent_sources,result.summary.accounting_work_units),(2,1))

    def test_review_node_members_are_strict_descendants(self):
        child=CoverageSource('CHILD','oauth-store',('auth','prod','en','legacy.json'))
        at_branch=CoverageSource('AT_BRANCH','oauth-store',('auth','prod','en'))
        requirements=CoverageRequirements.create(self.scope,(child,at_branch),())
        result=self.capture(requirements=requirements)
        self.assertEqual(result.state,'metadata-observed')
        self.assertEqual(result.summary.absent_sources,2)
        self.assertEqual(result.summary.unscanned_sources,0)
        self.assertEqual(result.summary.covered_absent_sources,1)


if __name__=='__main__':unittest.main()
