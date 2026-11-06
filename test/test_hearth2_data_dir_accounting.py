"""Private synthetic files only; exercise real acquisition and pinned parsers."""
from dataclasses import asdict, replace
import importlib.util
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).parents[1]/'mcp/memory'))
import test_hearth2_credential_sources as fixtures
from hearth2.credential_coverage import CoverageScope,CoverageSource,CoverageRequirements
from hearth2.data_dir_metadata import RootDirectoryView,_mount_id
from hearth2.store import RecordError


@unittest.skipUnless(os.name=='posix' and hasattr(os,'O_PATH'),'POSIX private fixtures')
class DirectoryAccountingTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('hearth2.data_dir_accounting'),
                             'private acquisition/accounting adapter missing')
        from hearth2 import data_dir_accounting as m
        import tempfile
        self.m=m
        fixture=fixtures.CredentialSourceTests();fixture.setUp()
        self.f=fixture;self.now=fixture.now;self.manifest=fixture.manifest
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.root.chmod(0o700)
        fd=os.open(self.root,os.O_RDONLY|os.O_DIRECTORY)
        try:mount=_mount_id(fd)
        finally:os.close(fd)
        self.scope=CoverageScope(fixture.context,'FAKE-DATA-DIR','BATCH','ROUND',mount)
        self.paths={'pi-auth':('codex-auth.json',),'mcode-config':('config.yaml',),
            'oauth-store':('auth','prod','en','mcode-public','auth.json'),
            'oauth-state':('auth','prod','en','mcode-public','auth-state.json')}
        self.requirements=self.requirements_for(self.manifest)

    def requirements_for(self,manifest):
        sources=[]
        for e in manifest.entries:
            path=self.paths.get(e.kind)
            if e.kind in ('oauth-store','oauth-state'):
                group=next(g for g in manifest.oauth_groups if g.group_id==e.group_id)
                path=('auth',group.build_env,group.region,'mcode-public',path[-1])
            sources.append(CoverageSource(e.source_id,e.kind,path))
        groups=tuple((g.group_id,tuple(e.source_id for e in manifest.entries if e.group_id==g.group_id))
                     for g in manifest.oauth_groups+manifest.selection_groups)
        return CoverageRequirements.create(self.scope,tuple(sources),groups)

    def write(self,kind,raw):
        p=self.root.joinpath(*self.paths[kind]);p.parent.mkdir(parents=True,exist_ok=True)
        p.write_bytes(raw);return p

    def port(self,**options):
        st=self.root.stat()
        view=RootDirectoryView(self.scope,str(self.root),st.st_dev,st.st_ino,st.st_ctime_ns,st.st_uid,st.st_gid)
        return self.m.DirectorySourceCapture(view,clock=lambda:self.now,monotonic=lambda:0,**options)

    def capture(self,port=None,requirements=None,manifest=None):
        return (port or self.port()).capture(requirements or self.requirements,
            manifest or self.manifest,begin=self.now)

    def test_real_pi_file_material_is_counted_without_resolving_commands(self):
        self.write('pi-auth',b'{"fake-provider":{"type":"api_key","key":"!DO-NOT-EXECUTE"}}')
        r=self.capture()
        self.assertEqual(r.state,'sources-accounted')
        self.assertEqual(dict(r.accounting.material_counts)['command_fields'],1)
        self.assertEqual(r.accounting.parsed_sources,1)
        self.assertEqual(r.accounting.absent_sources,3)
        self.assertEqual(r.accounting.unscanned_sources,13)
        self.assertEqual(len(r.accounting.unresolved_coverage_families),3)

    def test_oauth_pair_uses_acquired_bytes_in_its_original_namespace(self):
        for kind,raw in self.f.pair().items():self.write(kind,raw)
        r=self.capture();counts=dict(r.accounting.material_counts)
        self.assertEqual((counts['access_tokens'],counts['refresh_tokens']),(1,1))
        self.assertEqual(r.accounting.parsed_sources,2)

    def test_wrong_namespace_inside_file_is_unsupported_not_repaired(self):
        pair=self.f.pair();pair['oauth-store']=pair['oauth-store'].replace(b'.prod.en',b'.prod.cn')
        for kind,raw in pair.items():self.write(kind,raw)
        r=self.capture()
        self.assertEqual(r.accounting.parsed_sources,0)
        self.assertEqual(r.accounting.unsupported_sources,2)

    def test_missing_store_present_state_is_not_absent_or_parsed(self):
        self.write('oauth-state',self.f.pair()['oauth-state'])
        r=self.capture()
        self.assertEqual((r.accounting.absent_sources,r.accounting.unsupported_sources),(3,1))
        self.assertEqual(r.coverage.mixed_presence_groups,1)

    def test_config_keys_survive_missing_runtime_model_ref(self):
        self.write('mcode-config',b'provider:\n  custom:\n    options:\n      apiKey: FAKE-PRIVATE-KEY\n')
        r=self.capture()
        self.assertEqual(dict(r.accounting.material_counts)['configured_key_fields'],1)
        self.assertEqual(r.accounting.unsupported_sources,1)
        self.assertEqual(r.accounting.unscanned_sources,13)

    def test_empty_and_malformed_files_remain_present_unsupported(self):
        for raw in (b'',b'{bad'):
            with self.subTest(raw=raw):
                self.write('pi-auth',raw);r=self.capture()
                self.assertEqual(r.coverage.present_sources,1)
                self.assertEqual(r.accounting.unsupported_sources,1)
                self.assertEqual(r.accounting.absent_sources,3)

    def test_oversize_and_permission_failure_keep_other_material(self):
        self.write('pi-auth',b'{"fake":{"type":"api_key","key":"FAKE-PRIVATE-KEY"}}')
        self.write('mcode-config',b'x'*65536)
        r=self.capture()
        self.assertEqual((r.accounting.parsed_sources,r.accounting.unreadable_sources),(1,1))
        self.assertEqual(r.file_outcomes[13],(13,'unreadable','oversize'))
        real=os.read
        def read(fd,n):
            if os.readlink('/proc/self/fd/'+str(fd)).endswith('/config.yaml'):
                raise PermissionError('FAKE-PRIVATE-KEY')
            return real(fd,n)
        with patch('os.read',side_effect=read):r=self.capture()
        self.assertEqual((r.accounting.parsed_sources,r.accounting.unreadable_sources),(1,1))

    def test_changed_second_pass_discards_all_accounting(self):
        self.write('pi-auth',b'{}');real=os.read;nonempty=0
        def read(fd,n):
            nonlocal nonempty
            raw=real(fd,n)
            if raw:
                nonempty+=1
                if nonempty>1:return b'[]'
            return raw
        with patch('os.read',side_effect=read):r=self.capture()
        self.assertEqual((r.state,r.reason,r.accounting),('unscanned','changed',None))

    def test_context_kind_group_root_and_namespace_mismatches_refuse_before_reads(self):
        bad_group=replace(self.f.og,data_directory_id='OTHER-ROOT')
        cases=[replace(self.manifest,context=replace(self.f.context,assembly_sha256='f'*64)),
               replace(self.manifest,oauth_groups=(bad_group,)),
               replace(self.manifest,oauth_groups=(replace(self.f.og,region='cn'),)),
               replace(self.manifest,entries=tuple(replace(e,kind='environment') if e.kind=='pi-auth' else e
                                                  for e in self.manifest.entries))]
        for manifest in cases:
            with self.subTest(manifest=repr(manifest)),patch('os.read',side_effect=AssertionError('read before binding')):
                with self.assertRaises(RecordError):self.capture(manifest=manifest)

    def test_unmapped_consumers_cannot_be_read_as_arbitrary_files(self):
        sources=tuple(replace(s,path=('pretend-runtime.json',)) if s.kind=='lease-capability' else s
                      for s in self.requirements.sources)
        bad=CoverageRequirements.create(self.scope,sources,self.requirements.groups)
        with self.assertRaises(RecordError):self.capture(requirements=bad)

    def test_accounting_budget_is_validated_before_io_and_acquisition_budget_discards_root(self):
        audit=replace(self.f.audit)
        object.__setattr__(audit,'limits',tuple((k,1 if k=='bytes' else v) for k,v in self.f.audit.limits))
        with self.assertRaises(RecordError):self.capture(manifest=replace(self.manifest,audit=audit))
        self.write('pi-auth',b'{}')
        r=self.capture(port=self.port(max_bytes=4))
        self.assertEqual((r.state,r.reason,r.accounting),('unscanned','budget-acquisition',None))

    def test_public_result_and_errors_do_not_expose_private_material_or_hashes(self):
        raw=b'{"fake":{"type":"api_key","key":"FAKE-PRIVATE-KEY"}}';self.write('pi-auth',raw)
        r=self.capture();out=json.dumps(asdict(r))+repr(r)
        import hashlib
        for forbidden in ('FAKE-PRIVATE-KEY','codex-auth.json',str(self.root),hashlib.sha256(raw).hexdigest(),
                          'FAKE-DATA-DIR','FAKE-ACQUISITION'):
            self.assertNotIn(forbidden,out)

    def test_unsafe_sibling_blocks_absence_without_erasing_stable_present_material(self):
        self.write('pi-auth',b'{}');os.mkfifo(self.root/'socket-shaped')
        r=self.capture()
        self.assertEqual(r.accounting.parsed_sources,1)
        self.assertEqual(r.accounting.absent_sources,0)
        self.assertEqual(r.accounting.unscanned_sources,16)

    def test_later_root_never_reuses_first_root_material(self):
        self.write('pi-auth',b'{"fake":{"type":"api_key","key":"FAKE-PRIVATE-KEY"}}')
        first=self.capture();self.root.joinpath('codex-auth.json').unlink()
        second=self.capture()
        self.assertEqual(dict(first.accounting.material_counts)['literal_fields'],1)
        self.assertEqual(dict(second.accounting.material_counts)['literal_fields'],0)
        self.assertEqual(second.accounting.absent_sources,4)

    def test_two_namespace_groups_do_not_borrow_each_others_state(self):
        from hearth2.credential_sources import SourceRequirement
        other=replace(self.f.og,group_id='other',region='cn')
        extra=(SourceRequirement('other-store','oauth-store','image-native-consumers','other'),
               SourceRequirement('other-state','oauth-state','image-native-consumers','other'))
        manifest=replace(self.manifest,entries=self.manifest.entries+extra,
                         oauth_groups=(self.f.og,other))
        requirements=self.requirements_for(manifest)
        pair=self.f.pair()
        self.write('oauth-store',pair['oauth-store'])
        cn=self.root/'auth/prod/cn/mcode-public';cn.mkdir(parents=True)
        (cn/'auth-state.json').write_bytes(pair['oauth-state'].replace(b'"en"',b'"cn"'))
        r=self.capture(requirements=requirements,manifest=manifest)
        self.assertEqual(r.accounting.parsed_sources,0)
        self.assertEqual(r.accounting.unsupported_sources,2)
        self.assertEqual(r.accounting.absent_sources,4)

    def test_context_container_id_is_not_dropped_in_accounting(self):
        context=replace(self.f.context,container_id='f'*64)
        self.scope=replace(self.scope,context=context)
        self.manifest=replace(self.manifest,context=context)
        self.requirements=self.requirements_for(self.manifest)
        r=self.capture()
        self.assertEqual(len(r.accounting.unresolved_coverage_families),7)
        self.assertEqual(len(r.coverage.unresolved_coverage_families),7)

    def test_smaller_audit_read_budget_wins_over_capture_default(self):
        import hashlib
        value=self.f.audit.manifest();value['limits']['bytes']=4
        digest=hashlib.sha256(self.f.audit.encode(value)).hexdigest()
        audit=replace(self.f.audit,sha256=digest,limits=tuple(sorted(value['limits'].items())))
        context=replace(self.f.context,policy_sha256=digest)
        self.scope=replace(self.scope,context=context)
        self.manifest=replace(self.manifest,context=context,audit=audit)
        self.requirements=self.requirements_for(self.manifest)
        self.write('pi-auth',b'{}')
        r=self.capture()
        self.assertEqual((r.state,r.reason,r.accounting),('unscanned','budget-acquisition',None))

    def test_source_kind_mismatch_and_missing_catalog_refuse_before_root_open(self):
        variants=[replace(self.manifest,entries=self.manifest.entries[:-1])]
        sources=tuple(replace(s,kind='legacy-encrypted') if s.kind=='pi-auth' else s
                      for s in self.requirements.sources)
        wrong=CoverageRequirements.create(self.scope,sources,self.requirements.groups)
        with patch('os.open',side_effect=AssertionError('opened before validation')):
            for manifest in variants:
                with self.assertRaises(RecordError):self.capture(manifest=manifest)
            with self.assertRaises(RecordError):self.capture(requirements=wrong)

    def test_default_runtime_refuses_without_acquiring_any_path(self):
        with patch('os.open',side_effect=AssertionError('default runtime acquired files')):
            with self.assertRaises(RecordError):
                self.m.DirectorySourceCapture().capture(self.requirements,self.manifest,begin=self.now)

if __name__=='__main__':unittest.main()
