"""Supplied synthetic evidence only: no actual credential acquisition."""
from dataclasses import asdict, replace, FrozenInstanceError
from datetime import datetime, timedelta, timezone, tzinfo
import importlib.util
import json
from pathlib import Path
import stat
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).parents[1]/'mcp/memory'))
from hearth2.credential_sources import SourceContext
from hearth2.store import RecordError


class CredentialCoverageTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('hearth2.credential_coverage'),'coverage core missing')
        from hearth2 import credential_coverage as m
        self.m=m;self.now=datetime(2026,11,4,tzinfo=timezone.utc)
        self.scope=m.CoverageScope(SourceContext('sha256:'+'a'*64,None,'b'*64,'c'*64),
            'FAKE-ROOT','FAKE-BATCH','FAKE-ROUND',7)
        self.branch=('auth','prod','en','mcode-public')
        self.store=m.CoverageSource('FAKE-STORE','oauth-store',self.branch+('auth.json',))
        self.state=m.CoverageSource('FAKE-STATE','oauth-state',self.branch+('auth-state.json',))
        self.projection=m.CoverageSource('FAKE-PROJECTION','projection-namespaced',
            ('cli-auth','prod','en','local-runtime.auth.json'))
        self.sources=(self.store,self.state)
        self.requirements=self.require(self.sources)
        self.accounting=m.CoverageAccounting(clock=lambda:self.now)

    def require(self,sources,groups=None,**limits):
        groups=(('FAKE-PAIR',tuple(e.source_id for e in self.sources)),) if groups is None else groups
        return self.m.CoverageRequirements.create(self.scope,sources,groups,**limits)

    def snapshot(self,path=None,entries=(),**changes):
        values=dict(scope=self.scope,path=self.branch[:-1] if path is None else path,mount_id=7,
            device=1,inode=20,mode=stat.S_IFDIR|0o700,uid=1000,gid=1000,links=2,
            mtime_ns=100,ctime_ns=101,observed_at=self.now,entries=entries)
        return self.m.DirectorySnapshot(**{**values,**changes})

    def proof(self,path=None,entries=()):
        a=self.snapshot(path,entries)
        return self.m.AbsenceEvidence(a,a)

    def node(self,**changes):
        values=dict(scope=self.scope,branch=self.branch,observed_at=self.now,evidence=self.proof())
        return self.m.CoverageNode(**{**values,**changes})

    def obs(self,source,status='present',evidence=None,**changes):
        values=dict(scope=self.scope,source_id=source.source_id,status=status,
            observed_at=self.now,absence_evidence=evidence)
        return self.m.CoverageObservation(**{**values,**changes})

    def account(self,observations=(),nodes=(),requirements=None,**options):
        return self.accounting.account(requirements or self.requirements,observations,nodes,
            begin=options.get('begin',self.now))

    def test_absent_namespace_covers_two_leaves_for_one_unit(self):
        result=self.account(nodes=(self.node(),))
        self.assertEqual((result.required_sources,result.observed_sources,result.absent_sources),(2,2,2))
        self.assertEqual((result.physical_observations,result.coverage_nodes,result.covered_absent_sources),(1,1,2))
        self.assertEqual(result.accounting_work_units,1)
        self.assertEqual(result.source_statuses,((0,'oauth-store','absent'),(1,'oauth-state','absent')))
        self.assertEqual(len(result.unresolved_coverage_families),3)

    def test_missing_observation_is_unscanned_not_absent(self):
        result=self.account()
        self.assertEqual(result.unscanned_sources,2)
        self.assertEqual(result.absent_sources,0)
        self.assertEqual(result.accounting_work_units,3)

    def test_store_absent_state_present_preserves_mixed_pair(self):
        entry=self.m.DirectoryEntry('auth-state.json','regular',1)
        proof=self.proof(self.branch,(entry,))
        result=self.account((self.obs(self.store,'absent',proof),self.obs(self.state)))
        self.assertEqual((result.absent_sources,result.present_sources,result.mixed_presence_groups),(1,1,1))
        self.assertEqual(result.accounting_work_units,3)
        self.assertEqual(result.source_statuses[0][2],'absent')

    def test_auth_absence_cannot_hide_present_cli_projection(self):
        requirements=self.require(self.sources+(self.projection,))
        result=self.account((self.obs(self.projection),),(self.node(),),requirements)
        self.assertEqual((result.absent_sources,result.present_sources),(2,1))
        self.assertEqual(result.accounting_work_units,2)
        self.assertEqual(result.source_statuses[-1],(2,'projection-namespaced','present'))

    def test_node_overlapping_present_absent_or_unscanned_observation_refuses(self):
        for status in ['present','absent','unreadable','unscanned','unsupported']:
            proof=self.proof() if status=='absent' else None
            with self.subTest(status=status),self.assertRaises(RecordError):
                self.account((self.obs(self.store,status,proof),),(self.node(),))

    def test_duplicate_and_overlapping_nodes_refuse(self):
        for nodes in [(self.node(),self.node()),(self.node(branch=('auth','prod','en')),self.node())]:
            with self.assertRaises(RecordError):self.account(nodes=nodes)

    def test_node_with_no_covered_source_or_root_branch_refuses(self):
        for branch in [(),('run',),('auth','prod','cn','mcode-public')]:
            with self.assertRaises(RecordError):self.account(nodes=(self.node(branch=branch),))

    def test_existing_namespace_can_compact_only_proven_missing_leaves(self):
        node=self.node(evidence=self.proof(self.branch))
        self.assertEqual(self.account(nodes=(node,)).absent_sources,2)
        entry=self.m.DirectoryEntry('auth.json','regular',1)
        with self.assertRaises(RecordError):self.account(nodes=(replace(node,evidence=self.proof(self.branch,(entry,))),))

    def test_wrong_root_batch_round_context_or_mount_refuses(self):
        for field,value in [('root_id','OTHER'),('batch_id','OTHER'),('round_id','OTHER'),('root_mount_id',8),
                            ('context',replace(self.scope.context,assembly_sha256='f'*64))]:
            bad=replace(self.scope,**{field:value})
            with self.subTest(field=field),self.assertRaises(RecordError):
                self.account(nodes=(self.node(scope=bad),))
        with self.assertRaises(RecordError):
            self.account(nodes=(self.node(evidence=replace(self.proof(),second=self.snapshot(mount_id=8))),))

    def test_unstable_names_inode_ctime_and_mtime_refuse(self):
        proof=self.proof()
        for field,value in [('inode',21),('ctime_ns',102),('mtime_ns',102),
                            ('entries',(self.m.DirectoryEntry('new.tmp','regular',1),))]:
            with self.subTest(field=field),self.assertRaises(RecordError):
                self.account(nodes=(self.node(evidence=replace(proof,second=replace(proof.second,**{field:value}))),))

    def test_unsafe_sibling_and_multilink_refuse_absence(self):
        for kind,links in [('symlink',1),('socket',1),('fifo',1),('device',1),('unknown',1),('regular',2)]:
            entry=self.m.DirectoryEntry('other',kind,links)
            with self.subTest(kind=kind,links=links),self.assertRaises(RecordError):
                self.account(nodes=(self.node(evidence=self.proof(entries=(entry,))),))

    def test_case_variant_of_missing_name_cannot_be_absence(self):
        entry=self.m.DirectoryEntry('MCODE-PUBLIC','directory',2)
        with self.assertRaises(RecordError):self.account(nodes=(self.node(evidence=self.proof(entries=(entry,))),))

    def test_absence_requires_proof_and_no_extra_proof_on_present(self):
        for observation in [self.obs(self.store,'absent'),self.obs(self.store,'present',self.proof())]:
            with self.assertRaises(RecordError):self.account((observation,))

    def test_nonfile_sources_can_never_be_covered_or_asserted_absent(self):
        for kind in ['environment','host-model-ref','mcp-consumers']:
            source=self.m.CoverageSource('NONFILE',kind,None)
            requirements=self.require((source,),groups=())
            self.assertEqual(self.account(requirements=requirements).unscanned_sources,1)
            with self.assertRaises(RecordError):self.account((self.obs(source,'absent',self.proof()),),requirements=requirements)
            with self.assertRaises(RecordError):
                self.require((replace(source,path=self.branch+('fake',)),),groups=())

    def test_node_does_not_cover_root_level_material_misdeclared_under_auth(self):
        source=self.m.CoverageSource('CAP','lease-capability',self.branch+('fake.cap',))
        requirements=self.require((source,),groups=())
        with self.assertRaises(RecordError):self.account(nodes=(self.node(),),requirements=requirements)

    def test_same_casefold_duplicate_unsorted_or_unsafe_names_refuse(self):
        for entries in [(self.m.DirectoryEntry('a','regular'),self.m.DirectoryEntry('a','regular')),
                        (self.m.DirectoryEntry('b','regular'),self.m.DirectoryEntry('a','regular')),
                        (self.m.DirectoryEntry('a','regular'),self.m.DirectoryEntry('A','regular')),
                        (self.m.DirectoryEntry('../bad','regular'),)]:
            with self.assertRaises(RecordError):self.account(nodes=(self.node(evidence=self.proof(entries=entries)),))

    def test_work_budget_equality_refuses_but_compaction_fits(self):
        requirements=self.require(self.sources,work_limit=3)
        with self.assertRaises(RecordError):self.account(requirements=requirements)
        self.assertEqual(self.account(nodes=(self.node(),),requirements=requirements).accounting_work_units,1)

    def test_compaction_does_not_bypass_logical_source_limit(self):
        with self.assertRaises(RecordError):self.require(self.sources,source_limit=2)

    def test_freshness_and_evidence_order_are_checked(self):
        for time in [self.now-timedelta(seconds=61),self.now+timedelta(seconds=1),self.now.replace(tzinfo=None)]:
            with self.assertRaises(RecordError):self.account(nodes=(self.node(observed_at=time),))
        proof=self.proof()
        later=replace(proof.second,observed_at=self.now+timedelta(seconds=1))
        with self.assertRaises(RecordError):self.account(nodes=(self.node(evidence=replace(proof,second=later)),))

    def test_immutability_tampering_and_exact_nested_types(self):
        with self.assertRaises(FrozenInstanceError):self.scope.root_id='OTHER'
        with self.assertRaises(RecordError):self.account(observations=[])
        with self.assertRaises(RecordError):self.account(nodes=[self.node()])
        bad=replace(self.requirements,sha256='f'*64)
        with self.assertRaises(RecordError):self.account(requirements=bad)
        with self.assertRaises(RecordError):self.require(list(self.sources))
        class Alias(str):pass
        bad_scope=replace(self.scope,root_id=Alias('FAKE-ROOT'))
        with self.assertRaises(RecordError):self.m.CoverageRequirements.create(bad_scope,self.sources,())

    def test_custom_timezone_is_refused_without_callback(self):
        class Hostile(tzinfo):
            def utcoffset(self,dt):raise RuntimeError('FAKE-SECRET')
        with self.assertRaises(RecordError) as caught:
            self.account(begin=self.now.replace(tzinfo=Hostile()))
        self.assertNotIn('FAKE-SECRET',str(caught.exception))

    def test_unknown_status_duplicate_source_and_unknown_group_refuse(self):
        for observations in [(self.obs(self.store,'clean'),),(self.obs(self.store),self.obs(self.store)),
                             (replace(self.obs(self.store),source_id='UNKNOWN'),)]:
            with self.assertRaises(RecordError):self.account(observations)
        with self.assertRaises(RecordError):self.require(self.sources,(('g',('UNKNOWN',)),))

    def test_public_output_is_only_counts_enums_no_authority_or_metadata(self):
        result=self.account(nodes=(self.node(),))
        text=json.dumps(asdict(result))+repr(result)
        for value in ['FAKE-ROOT','FAKE-BATCH','FAKE-ROUND','FAKE-STORE','auth.json','mcode-public',self.scope.context.policy_sha256]:
            self.assertNotIn(value,text)
        for name in ['complete','observe','scan','credential_entries','start','credentials']:
            self.assertFalse(hasattr(result,name));self.assertFalse(hasattr(self.accounting,name))
        with patch('builtins.open',side_effect=AssertionError('no I/O')), \
             patch('subprocess.run',side_effect=AssertionError('no launch')):
            self.assertEqual(self.account(nodes=(self.node(),)).absent_sources,2)

    def test_smaller_declared_map_cannot_clear_any_physical_family(self):
        requirements=self.require((self.store,),groups=())
        result=self.account((self.obs(self.store,'absent',self.proof()),),requirements=requirements)
        self.assertEqual(result.absent_sources,1)
        self.assertEqual(result.unresolved_coverage_families,('image-rootfs','image-environment','image-native-consumers'))

    def test_result_cannot_outlive_window_or_wallclock_rollback(self):
        for finish in [self.now+timedelta(seconds=61),self.now-timedelta(microseconds=1)]:
            times=iter([self.now,finish]);self.accounting=self.m.CoverageAccounting(clock=lambda:next(times))
            with self.assertRaises(RecordError):self.account(nodes=(self.node(),))

    def test_conflicting_parent_witnesses_in_one_packet_refuse(self):
        a=self.obs(self.store,'absent',self.proof(self.branch))
        # Each individual pair is stable, but it cannot simultaneously describe
        # the same parent directory with a different inode or name list.
        for changes in [dict(inode=21),dict(entries=(self.m.DirectoryEntry('other','regular'),))]:
            snapshot=self.snapshot(self.branch,**changes)
            b=self.obs(self.state,'absent',self.m.AbsenceEvidence(snapshot,snapshot))
            with self.assertRaises(RecordError):self.account((a,b))

    def test_eight_absent_namespaces_fit_without_phantom_groups(self):
        sources=[];groups=[];nodes=[]
        for index,(env,region) in enumerate((e,r) for e in ('dev','test','staging','prod') for r in ('cn','en')):
            branch=('auth',env,region,'mcode-public');members=[]
            for role,name in [('oauth-store','auth.json'),('oauth-state','auth-state.json')]:
                source=self.m.CoverageSource('S'+str(len(sources)),role,branch+(name,))
                sources.append(source);members.append(source.source_id)
            groups.append(('G'+str(index),tuple(members)))
            snapshot=self.snapshot(branch[:-1],inode=100+index)
            nodes.append(self.node(branch=branch,evidence=self.m.AbsenceEvidence(snapshot,snapshot)))
        requirements=self.require(tuple(sources),tuple(groups),work_limit=16)
        with self.assertRaises(RecordError):self.account(requirements=requirements)
        result=self.account(nodes=tuple(nodes),requirements=requirements)
        self.assertEqual((result.required_sources,result.absent_sources,result.accounting_work_units),(16,16,8))

    def test_stopped_container_keeps_all_seven_physical_families_unresolved(self):
        scope=replace(self.scope,context=replace(self.scope.context,container_id='f'*64))
        requirements=self.m.CoverageRequirements.create(scope,self.sources,())
        self.assertEqual(len(self.account(requirements=requirements).unresolved_coverage_families),7)

    def test_review_missing_namespace_cannot_contain_present_state(self):
        for status in ['present','unsupported','unreadable']:
            with self.subTest(status=status),self.assertRaises(RecordError):
                self.account((self.obs(self.store,'absent',self.proof()),self.obs(self.state,status)))

    def test_review_empty_root_cannot_have_present_cli_branch(self):
        requirements=self.require(self.sources+(self.projection,))
        node=self.node(evidence=self.proof(()))
        with self.assertRaises(RecordError):
            self.account((self.obs(self.projection),),(node,),requirements)

    def test_review_missing_ancestor_cannot_have_existing_directory_witness(self):
        absent_store=self.obs(self.store,'absent',self.proof())
        snapshot=self.snapshot(self.branch,inode=21)
        absent_state=self.obs(self.state,'absent',self.m.AbsenceEvidence(snapshot,snapshot))
        with self.assertRaises(RecordError):self.account((absent_store,absent_state))
        # Same contradiction across a node and direct observation.
        with self.assertRaises(RecordError):
            self.account((absent_state,),(self.node(evidence=self.proof(())),))

    def test_review_reconciliation_metadata_work_is_bounded(self):
        sources=[];observations=[]
        for index in range(40):
            parent=self.branch+('p'+str(index),)
            source=self.m.CoverageSource('S'+str(index),'oauth-store',parent+('f',))
            sources.append(source)
            entries=tuple(self.m.DirectoryEntry(n,'regular') for n in ('a','b','c'))
            snapshot=self.snapshot(parent,entries,inode=100+index)
            observations.append(self.obs(source,'absent',self.m.AbsenceEvidence(snapshot,snapshot)))
        requirements=self.require(tuple(sources),groups=())
        with self.assertRaises(RecordError):self.account(tuple(observations),requirements=requirements)


if __name__=='__main__':unittest.main()
