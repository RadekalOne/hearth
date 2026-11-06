"""Immutable conditional scope policy; all files are private fake fixtures."""
from dataclasses import FrozenInstanceError,asdict,replace
from datetime import timedelta
import hashlib
import importlib.util
import json
import os
import unittest
from unittest.mock import patch

import test_hearth2_data_dir_accounting as fixtures
from hearth2.credential_coverage import CoverageRequirements
from hearth2.store import RecordError


@unittest.skipUnless(os.name=='posix' and hasattr(os,'O_PATH'),'private POSIX fixtures')
class DirectoryScopeTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('hearth2.data_dir_scope'),
                             'immutable conditional root scope missing')
        from hearth2 import data_dir_scope as m
        self.m=m;self.f=fixtures.DirectoryAccountingTests();self.f.setUp()
        self.addCleanup(self.f.doCleanups)

    def view(self):return self.f.port().view

    def policy(self,view=None,requirements=None,manifest=None,**limits):
        return self.m.DirectoryScopePolicy.create(view or self.view(),requirements or self.f.requirements,
            manifest or self.f.manifest,max_entries=limits.get('max_entries',256),
            max_bytes=limits.get('max_bytes',900000),timeout_seconds=limits.get('timeout_seconds',5))

    def capture(self,policy,*,expected=None,view=None,requirements=None,manifest=None):
        return self.m.ScopedDirectoryCapture(policy,expected_sha256=expected or policy.sha256,
            clock=lambda:self.f.now,monotonic=lambda:0).capture(view or self.view(),
            requirements or self.f.requirements,manifest or self.f.manifest,begin=self.f.now)

    def test_policy_construction_does_not_open_or_discover_paths(self):
        view=self.view()
        with patch('os.open',side_effect=AssertionError('policy opened a path')):
            policy=self.policy(view=view)
        self.assertEqual(len(policy.sha256),64)
        with self.assertRaises(FrozenInstanceError):policy.max_bytes=1

    def test_pinned_scope_runs_real_private_acquisition_and_accounting(self):
        self.f.write('pi-auth',b'{"fake":{"type":"api_key","key":"FAKE-KEY"}}')
        policy=self.policy();r=self.capture(policy)
        self.assertEqual(r.state,'sources-accounted')
        self.assertEqual(dict(r.accounting.material_counts)['literal_fields'],1)
        self.assertEqual(r.accounting.unscanned_sources,13)
        self.assertEqual(len(r.accounting.unresolved_coverage_families),3)

    def test_new_batch_round_is_allowed_without_reenrolling_root(self):
        self.f.write('pi-auth',b'{}');policy=self.policy()
        scope=replace(self.f.scope,batch_id='NEXT-BATCH',round_id='NEXT-ROUND')
        view=replace(self.view(),scope=scope)
        req=CoverageRequirements.create(scope,self.f.requirements.sources,self.f.requirements.groups)
        self.assertEqual(self.policy(view=view,requirements=req).sha256,policy.sha256)
        self.assertEqual(self.capture(policy,view=view,requirements=req).accounting.parsed_sources,1)

    def test_expected_pin_is_required_and_not_replaced_by_self_hash(self):
        policy=self.policy();view=self.view()
        with patch('os.open',side_effect=AssertionError('untrusted policy opened files')):
            for port in [self.m.ScopedDirectoryCapture(),
                         self.m.ScopedDirectoryCapture(policy),
                         self.m.ScopedDirectoryCapture(policy,expected_sha256='f'*64)]:
                with self.assertRaises(RecordError):
                    port.capture(view,self.f.requirements,self.f.manifest,begin=self.f.now)

    def test_mutated_document_digest_and_rehashed_replacement_refuse_before_io(self):
        policy=self.policy();view=self.view()
        changed=replace(policy,document=policy.document+b' ')
        rehashed=replace(changed,sha256=hashlib.sha256(changed.document).hexdigest())
        with patch('os.open',side_effect=AssertionError('tampered policy opened files')):
            for bad in (changed,rehashed,replace(policy,sha256='f'*64)):
                with self.assertRaises(RecordError):self.capture(bad,expected=policy.sha256,view=view)

    def test_root_path_identity_owner_and_mount_cannot_change_under_pin(self):
        policy=self.policy();view=self.view()
        scope=replace(view.scope,root_mount_id=view.scope.root_mount_id+1)
        cases=[replace(view,root_path=view.root_path+'-elsewhere'),replace(view,inode=view.inode+1),
               replace(view,device=view.device+1),replace(view,ctime_ns=view.ctime_ns+1),
               replace(view,uid=view.uid+1),replace(view,gid=view.gid+1),replace(view,scope=scope)]
        with patch('os.open',side_effect=AssertionError('changed root opened files')):
            for bad in cases:
                with self.subTest(field=repr(bad)),self.assertRaises(RecordError):self.capture(policy,view=bad)

    def test_canonical_path_aliases_are_refused_even_at_policy_creation(self):
        view=self.view()
        for path in (view.root_path+'/../'+self.f.root.name,view.root_path+'/.',
                     view.root_path+'/',view.root_path.replace('/','//',1),'/',
                     view.root_path+'/a\\b',view.root_path+'/bad\nname'):
            with self.subTest(path=path),self.assertRaises(RecordError):self.policy(view=replace(view,root_path=path))

    def test_policy_rejects_mutable_and_bool_budget_fields(self):
        for name in ('max_entries','max_bytes','timeout_seconds'):
            for value in (True,0,-1,1.0,'5'):
                with self.subTest(name=name,value=value),self.assertRaises(RecordError):
                    self.policy(**{name:value})
        for limits in ({'max_entries':257},{'max_bytes':900001},{'timeout_seconds':6}):
            with self.assertRaises(RecordError):self.policy(**limits)

    def test_lower_policy_budget_cannot_be_widened_at_execution(self):
        self.f.write('pi-auth',b'{}');policy=self.policy(max_bytes=4)
        result=self.capture(policy)
        self.assertEqual((result.state,result.reason,result.accounting),('unscanned','budget-acquisition',None))
        view=self.view()
        with patch('os.open',side_effect=AssertionError('widened budget opened files')):
            with self.assertRaises(RecordError):self.capture(replace(policy,max_bytes=5),view=view)

    def test_selection_hypothesis_account_and_audit_closure_are_pinned(self):
        policy=self.policy();view=self.view();manifest=self.f.manifest
        selection=replace(self.f.f.sg,hypothesis=replace(self.f.f.hypothesis,resolver='MI'))
        account=replace(self.f.f.og,account='B'*43)
        for modified in (replace(manifest,selection_groups=(selection,)),replace(manifest,oauth_groups=(account,))):
            with patch('os.open',side_effect=AssertionError('changed parser scope opened files')):
                with self.assertRaises(RecordError):self.capture(policy,manifest=modified,view=view)

    def test_coverage_map_and_work_budget_are_pinned(self):
        policy=self.policy();view=self.view()
        sources=tuple(replace(s,path=None) if s.kind=='pi-auth' else s for s in self.f.requirements.sources)
        cases=[CoverageRequirements.create(self.f.scope,sources,self.f.requirements.groups),
               CoverageRequirements.create(self.f.scope,self.f.requirements.sources,self.f.requirements.groups,work_limit=63)]
        with patch('os.open',side_effect=AssertionError('changed map opened files')):
            for requirements in cases:
                with self.assertRaises(RecordError):self.capture(policy,requirements=requirements,view=view)

    def test_result_and_refusal_text_do_not_expose_policy_path_or_digest(self):
        self.f.write('pi-auth',b'{}');policy=self.policy();view=self.view()
        text=json.dumps(asdict(self.capture(policy)))+repr(policy)
        for forbidden in (view.root_path,policy.sha256,'FAKE-DATA-DIR','FAKE-SELECTION-REF'):
            self.assertNotIn(forbidden,text)
        with self.assertRaises(RecordError) as error:self.capture(policy,expected='f'*64)
        self.assertEqual(str(error.exception),'unsupported conditional directory scope')

    def test_stale_request_still_refuses_with_a_matching_policy(self):
        policy=self.policy()
        port=self.m.ScopedDirectoryCapture(policy,expected_sha256=policy.sha256,
            clock=lambda:self.f.now+timedelta(seconds=61),monotonic=lambda:0)
        view=self.view()
        with patch('os.open',side_effect=AssertionError('stale request opened files')):
            with self.assertRaises(RecordError):port.capture(view,self.f.requirements,self.f.manifest,begin=self.f.now)

    def test_policy_body_has_no_cross_root_slots_or_runtime_success_flags(self):
        value=json.loads(self.policy().document)
        self.assertNotIn('roots',value)
        for flag in ('complete','enrolled','authenticated','credentials_none','start'):
            self.assertNotIn(flag,value)

    def test_changed_parser_closure_requires_a_different_external_pin(self):
        policy=self.policy();view=self.view();f=self.f.f
        value=f.audit.manifest();value['parser_closure_sha256']='f'*64
        digest=hashlib.sha256(f.audit.encode(value)).hexdigest()
        audit=replace(f.audit,sha256=digest,parser_closure_sha256='f'*64)
        context=replace(f.context,policy_sha256=digest)
        scope=replace(self.f.scope,context=context)
        manifest=replace(self.f.manifest,context=context,audit=audit)
        requirements=CoverageRequirements.create(scope,self.f.requirements.sources,self.f.requirements.groups)
        view=replace(view,scope=scope)
        replacement=self.policy(view=view,requirements=requirements,manifest=manifest)
        self.assertNotEqual(replacement.sha256,policy.sha256)
        with patch('os.open',side_effect=AssertionError('changed closure opened files')):
            with self.assertRaises(RecordError):
                self.capture(replacement,expected=policy.sha256,view=view,requirements=requirements,manifest=manifest)

    def test_policy_does_not_normalize_declared_source_owner_to_helper_root(self):
        view=replace(self.view(),uid=1000,gid=1000)
        doc=json.loads(self.policy(view=view).document)
        self.assertEqual(doc['view'][-2:],[1000,1000])
        root_doc=json.loads(self.policy(view=replace(view,uid=0,gid=0)).document)
        self.assertEqual(root_doc['view'][-2:],[0,0])

    def test_string_subclasses_and_forged_nested_contracts_refuse_redacted(self):
        class Text(str):pass
        view=self.view()
        with self.assertRaises(RecordError):self.policy(view=replace(view,root_path=Text(view.root_path)))
        req=replace(self.f.requirements,sha256='f'*64)
        with self.assertRaises(RecordError):self.policy(requirements=req)
        policy=self.policy()
        with patch('os.open',side_effect=AssertionError('invalid nested contract opened files')):
            with self.assertRaises(RecordError):self.capture(policy,requirements=req,view=view)

    def test_content_not_policy_changes_across_later_rounds(self):
        self.f.write('pi-auth',b'{}');policy=self.policy()
        self.assertEqual(self.capture(policy).accounting.parsed_sources,1)
        self.f.root.joinpath('codex-auth.json').write_bytes(b'{bad')
        self.assertEqual(self.capture(policy).accounting.unsupported_sources,1)

    def test_nested_view_scope_is_typed_before_equality_can_run(self):
        class Trap:
            def __eq__(self,other):raise AssertionError('caller equality executed')
        with self.assertRaises(RecordError):self.policy(view=replace(self.view(),scope=Trap()))

if __name__=='__main__':unittest.main()
