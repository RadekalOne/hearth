"""Pure synthetic enrollment/map contracts; no native directories or credentials."""
from dataclasses import replace
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).parents[1]/'mcp/memory'))
from hearth2.credential_sources import SourceContext
from hearth2.store import RecordError


class DataDirectoryPolicyTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('hearth2.data_dir_policy'),'enrollment contract missing')
        from hearth2 import data_dir_policy as p, mcode_source_map as m
        self.p=p;self.m=m
        self.context=SourceContext('sha256:'+'a'*64,None,'b'*64,'c'*64)
        self.root=p.RootEnrollment('rootA','/synthetic/primary',7,11,12,13,1000,1000,
            (p.NamespaceEnrollment('prod','en','TYWZVOJ4uWHf-HV2JKkRMmL2D_Rlug5MpnfBKp2hLVQ'),),11,2)

    def policy(self,**changes):
        values=dict(context=self.context,roots=(self.root,),configured_sources=(('argv','d'*64),),
            authority_reference='SYNTHETIC-ENROLLMENT',helper_sha256='e'*64,parser_sha256='f'*64,
            discovery_to_composition_seconds=120,round_seconds=10,max_entries=256,
            max_bytes=1048576,max_candidates=64,logical_source_limit=256)
        values.update(changes)
        return self.p.DataDirectoryPolicy.create(**values)

    def test_root_slice_excludes_other_root_and_configuration(self):
        other=replace(self.root,root_id='rootB',path='/synthetic/legacy',inode=14)
        policy=self.policy(roots=(self.root,other))
        part=policy.root_slice('rootA',expected_sha256=policy.sha256,context=self.context)
        encoded=part.encode()
        self.assertNotIn(b'/synthetic/legacy',encoded)
        self.assertNotIn(b'rootB',encoded)
        self.assertNotIn(b'argv',encoded)
        self.assertEqual(part.root,self.root)
        self.assertEqual(part.policy_sha256,policy.sha256)

    def test_policy_rejects_wrong_original_context_or_independent_pin(self):
        policy=self.policy()
        for context in (replace(self.context,image_id='sha256:'+'1'*64),
                replace(self.context,container_id='2'*64),replace(self.context,assembly_sha256='3'*64),
                replace(self.context,policy_sha256='4'*64)):
            with self.assertRaises(RecordError):policy.root_slice('rootA',expected_sha256=policy.sha256,context=context)
        with self.assertRaises(RecordError):policy.root_slice('rootA',expected_sha256='0'*64,context=self.context)
        with self.assertRaises(RecordError):policy.root_slice('unknown',expected_sha256=policy.sha256,context=self.context)

    def test_policy_document_is_canonical_roundtrips_and_refuses_tampering(self):
        policy=self.policy()
        loaded=self.p.DataDirectoryPolicy.decode(policy.document,expected_sha256=policy.sha256)
        self.assertEqual(loaded,policy)
        self.assertEqual(hashlib.sha256(policy.document).hexdigest(),policy.sha256)
        with self.assertRaises(RecordError):self.p.DataDirectoryPolicy.decode(policy.document+b' ',expected_sha256=policy.sha256)
        with self.assertRaises(RecordError):replace(policy,max_bytes=12).root_slice('rootA',expected_sha256=policy.sha256,context=self.context)

    def test_eight_roots_allowed_ninth_duplicate_alias_and_nested_roots_refuse(self):
        roots=tuple(replace(self.root,root_id='r'+str(i),path='/fixture/r'+str(i),inode=20+i) for i in range(9))
        self.assertEqual(len(self.policy(roots=roots[:8]).roots),8)
        for value in (roots,(self.root,self.root),
                (self.root,replace(self.root,root_id='b',path='/synthetic/PRIMARY')),
                (self.root,replace(self.root,root_id='b',path='/synthetic/primary/nested'))):
            with self.assertRaises(RecordError):self.policy(roots=value)

    def test_canonical_paths_and_exact_nested_types_before_comparison(self):
        class Trap(str):
            def __eq__(self,other):raise AssertionError('caller comparison')
        for value in ('/','relative','/x/../y','/x//y','/x/','/has space','/x\\y','/café',Trap('/x')):
            with self.assertRaises(RecordError):self.policy(roots=(replace(self.root,path=value),))
        for value in (True,-1,'1000'):
            with self.assertRaises(RecordError):self.policy(roots=(replace(self.root,uid=value),))
        with self.assertRaises(RecordError):self.policy(roots=[self.root])

    def test_required_window_limits_closures_and_configured_sources_are_bound(self):
        for key,value in (('discovery_to_composition_seconds',None),('discovery_to_composition_seconds',121),
                ('round_seconds',11),('max_entries',257),('max_bytes',1048577),('max_candidates',65),
                ('logical_source_limit',True),('helper_sha256',''),('parser_sha256',''),('authority_reference',''),
                ('configured_sources',(('argv','d'*64),('argv','e'*64)))):
            with self.subTest(key=key),self.assertRaises(RecordError):self.policy(**{key:value})
        for key,value in (('round_seconds',9),('parser_sha256','1'*64),('configured_sources',(('argv','1'*64),))):
            self.assertNotEqual(self.policy().sha256,self.policy(**{key:value}).sha256)

    def test_absent_root_requires_explicit_slot_and_parent_identity(self):
        absent=replace(self.root,device=None,inode=None,ctime_ns=None,absent=True)
        policy=self.policy(roots=(absent,))
        self.assertTrue(policy.roots[0].absent)
        for root in (replace(absent,absent=False),replace(absent,parent_inode=0),replace(self.root,absent=True)):
            with self.assertRaises(RecordError):self.policy(roots=(root,))

    def test_namespace_selection_is_explicit_unique_and_not_defaulted(self):
        self.assertEqual(self.policy(roots=(replace(self.root,namespaces=()),)).roots[0].namespaces,())
        ns=self.root.namespaces[0]
        for values in ((ns,ns),(replace(ns,build_env='pre'),),(replace(ns,region='EN'),),(replace(ns,account='A'),)):
            with self.assertRaises(RecordError):self.policy(roots=(replace(self.root,namespaces=values),))

    def test_expansion_preserves_literal_paths_multiplicity_and_unmapped_obligations(self):
        part=self.policy().root_slice('rootA',expected_sha256=self.policy().sha256,context=self.context)
        leaves=self.m.MCodeSourceMap.expand(part)
        paths={x.kind:x.path for x in leaves}
        self.assertEqual(paths,{
            'pi-auth':('codex-auth.json',),'oauth-store':('auth','prod','en','mcode-public','auth.json'),
            'oauth-state':('auth','prod','en','mcode-public','auth-state.json'),
            'projection-namespaced':('cli-auth','prod','en','local-runtime.auth.json'),
            'projection-legacy':('cli-auth','prod','local-runtime.auth.json'),
            'projection-shared':('local-runtime.auth.json',),'lease-capability':('run','mcode-auth-lease-v1.cap'),
            'account-identity':('cli-auth','prod','en','account-identity.json'),
            'shared-selector':('cli-auth','shared-projection.json'),
            'scope-marker':('cli-auth','prod','en','cli-auth.scope.json'),
            'legacy-scope-marker':('cli-auth','prod','cli-auth.scope.json'),
            'region-selector':('preferences','mcode-region.json'),'legacy-encrypted':('auth','credentials.enc'),
            'mcode-config':('config.yaml',),'host-model-ref':None,'mcp-consumers':None,'environment':None})
        self.assertTrue(all(x.status=='unscanned' for x in leaves))
        self.assertTrue(all(x.acquisition_supported is False for x in leaves))

    def test_multi_namespace_does_not_multiply_shared_or_environment_roles(self):
        ns=self.root.namespaces[0]
        root=replace(self.root,namespaces=(ns,replace(ns,region='cn'),replace(ns,build_env='dev')))
        policy=self.policy(roots=(root,))
        leaves=self.m.MCodeSourceMap.expand(policy.root_slice('rootA',expected_sha256=policy.sha256,context=self.context))
        self.assertEqual(len(leaves),29) # 10 root/non-file + 2*2 environment + 5*3 namespace
        for kind in ('projection-shared','region-selector','environment'):
            self.assertEqual(sum(x.kind==kind for x in leaves),1)
        self.assertEqual(sum(x.kind=='projection-legacy' for x in leaves),2)
        self.assertEqual(sum(x.kind=='oauth-store' for x in leaves),3)
        self.assertEqual(len({x.source_id for x in leaves}),29)

    def test_expansion_refuses_underdeclared_logical_budget_without_truncation(self):
        policy=self.policy(logical_source_limit=17)
        with self.assertRaises(RecordError):self.m.MCodeSourceMap.expand(policy.root_slice('rootA',expected_sha256=policy.sha256,context=self.context))

    def test_account_is_checked_against_enrolled_value_not_minted(self):
        # Independent fixture SHA256('/synthetic/primary/auth' + NUL + 'mcode-public').
        part=self.policy().root_slice('rootA',expected_sha256=self.policy().sha256,context=self.context)
        self.assertTrue(self.m.MCodeSourceMap.account_matches(part,'prod','en'))
        wrong=replace(self.root,namespaces=(replace(self.root.namespaces[0],account='A'*43),))
        policy=self.policy(roots=(wrong,))
        self.assertFalse(self.m.MCodeSourceMap.account_matches(policy.root_slice('rootA',expected_sha256=policy.sha256,context=self.context),'prod','en'))
        self.assertFalse(self.m.MCodeSourceMap.account_matches(part,'dev','cn'))

    def test_exact_transients_not_generic_ignored_files_or_sockets(self):
        check=self.m.MCodeSourceMap.transient
        for path,kind in ((('auth','prod','en','mcode-public','auth.json.12.345.tmp'),'regular'),
                (('run','mcode-auth-lease-v1.cap.12.0123456789abcdef.tmp'),'regular'),
                (('.config-tmp-012345abcdef',),'regular'),
                (('auth','prod','en','mcode-public','auth.lock.lock'),'directory')):
            self.assertTrue(check(path,kind))
        for path,kind in ((('anything.tmp',),'regular'),(('config.yaml.backup',),'regular'),
                (('run','mcode-auth-lease-v1.sock'),'socket'),
                (('auth','prod','en','mcode-public','auth.lock.lock'),'symlink'),
                (('run','mcode-auth-lease-v1.cap.12.345.tmp'),'regular')):
            self.assertFalse(check(path,kind))

    def test_map_and_root_slice_forgery_refuse_redacted(self):
        policy=self.policy();part=policy.root_slice('rootA',expected_sha256=policy.sha256,context=self.context)
        for forged in (replace(part,source_map_sha256='0'*64),replace(part,root=replace(self.root,path='/elsewhere'))):
            with self.assertRaises(RecordError):self.m.MCodeSourceMap.expand(forged)
        for obj in (policy,part,self.root):
            self.assertNotIn('/synthetic',repr(obj))
            self.assertNotIn(policy.sha256,repr(obj))

    def test_missing_account_remains_unknown_and_empty_namespace_has_no_invented_env(self):
        unknown=replace(self.root,namespaces=(replace(self.root.namespaces[0],account=None),))
        policy=self.policy(roots=(unknown,))
        part=policy.root_slice('rootA',expected_sha256=policy.sha256,context=self.context)
        self.assertFalse(self.m.MCodeSourceMap.account_matches(part,'prod','en'))
        policy=self.policy(roots=(replace(self.root,namespaces=()),))
        leaves=self.m.MCodeSourceMap.expand(policy.root_slice('rootA',expected_sha256=policy.sha256,context=self.context))
        self.assertEqual(len(leaves),10)
        self.assertTrue(all(x.build_env is None for x in leaves))

    def test_decode_rejects_unknown_duplicate_and_old_policy_fields_redacted(self):
        raw=self.policy().document
        value=json.loads(raw)
        variants=[{**value,'version':2},{**value,'source_map_sha256':'0'*64},
            {**value,'extra':'PRIVATE-SENTINEL'},{**value,'roots':[]},
            {**value,'limits':{**value['limits'],'max_entries':True}}]
        documents=[json.dumps(x,sort_keys=True,separators=(',',':')).encode() for x in variants]
        documents.extend((b'{"version":1,"version":1}',b'['*5000+b']'*5000,b'PRIVATE-SENTINEL'))
        for document in documents:
            with self.assertRaises(RecordError) as error:
                self.p.DataDirectoryPolicy.decode(document,expected_sha256=hashlib.sha256(document).hexdigest())
            self.assertEqual(str(error.exception),'unsupported data directory enrollment')

    def test_source_map_never_recognizes_unverified_legacy_namespace_writer(self):
        # Only namespace account-identity writes were established. Environment
        # legacy branches have projection/scope roles, never account identity.
        self.assertFalse(self.m.MCodeSourceMap.transient(('cli-auth','prod','account-identity.json.12.345.tmp'),'regular'))
        self.assertTrue(self.m.MCodeSourceMap.transient(('cli-auth','prod','en','account-identity.json.12.345.tmp'),'regular'))


if __name__=='__main__':unittest.main()
