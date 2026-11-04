"""Synthetic accounting only; never acquire a user's credentials or runtime."""
from dataclasses import asdict, replace, FrozenInstanceError
from datetime import datetime, timedelta, timezone, tzinfo
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).parents[1]/'mcp/memory'))
from hearth2.credential_policy import CredentialAuditRequirements
from hearth2.mcode_config import SelectionHypothesis
from hearth2.store import RecordError


def raw(value):return json.dumps(value).encode()


class CredentialSourceTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('hearth2.credential_sources'),'source accounting missing')
        from hearth2 import credential_sources as m
        self.m=m;self.now=datetime(2026,11,4,tzinfo=timezone.utc)
        value=dict(version=1,kind='hearth2-credential-audit-requirements-v1',image_id='sha256:'+'a'*64,
            native_profile_sha256='b'*64,rootfs_audit_manifest_sha256='c'*64,
            consumer_audit_manifest_sha256='d'*64,parser_closure_sha256='e'*64,
            audit_authority_reference='FAKE-AUDITOR',limits=dict(sources=200,bytes=900000,consumers=32,seconds=5))
        digest=hashlib.sha256(CredentialAuditRequirements.encode(value)).hexdigest()
        self.audit=CredentialAuditRequirements(digest,value['image_id'],*(value[k] for k in
            ('native_profile_sha256','rootfs_audit_manifest_sha256','consumer_audit_manifest_sha256','parser_closure_sha256')),
            value['audit_authority_reference'],tuple(sorted(value['limits'].items())))
        self.context=m.SourceContext(self.audit.image_id,None,'b'*64,digest)
        self.hypothesis=SelectionHypothesis('OD','en',('MiniMax-M3',),'MiniMax-M3',('MiniMax-M3',),
            True,True,'runtime-default',False,False,False,'FAKE-SELECTION-REF')
        self.og=m.OAuthSourceGroup('oauth','FAKE-DATA-DIR','prod','en','A'*43)
        self.sg=m.SelectionSourceGroup('config',self.hypothesis)
        entries=[]
        for i,kind in enumerate(m.SOURCE_KINDS):
            group='oauth' if kind.startswith(('oauth-','projection-')) else 'config' if kind in ('mcode-config','host-model-ref') else None
            primary='oauth' if kind.startswith('projection-') else None
            family='image-environment' if kind=='environment' else 'image-native-consumers'
            entries.append(m.SourceRequirement('src'+str(i),kind,family,group,primary))
        self.manifest=m.SourceManifest(self.context,self.audit,tuple(entries),(self.og,),(self.sg,))
        self.observations=tuple(self.obs(e) for e in entries)
        self.accounting=m.CredentialSourceAccounting(clock=lambda:self.now,monotonic=lambda:0)

    def obs(self,entry,status='absent',data=None,**changes):
        return self.m.SourceObservation(self.context,entry.source_id,entry.kind,status,self.now,'FAKE-ACQUISITION',data,**changes)

    def sources(self,**data):
        return tuple(self.obs(e,'present',data[e.kind]) if e.kind in data else self.obs(e)
                     for e in self.manifest.entries)

    def run_account(self,observations=None,manifest=None,**options):
        return self.accounting.account(manifest or self.manifest,
            self.observations if observations is None else observations,begin=options.get('begin',self.now))

    def counts(self,result):return dict(result.material_counts)

    def pair(self,**record_changes):
        record=dict(schemaVersion=1,accessToken='FAKE-ACCESS',refreshToken='FAKE-REFRESH',tokenType='Bearer',
            clientId='mcode-public',audience='agent-backend',scopes=['agent.default'],expiresAtMs=1,generation=3,
            accountId='FAKE-IDENTITY')
        record.update(record_changes)
        auth=dict(schemaVersion=1,records={'com.minimax.mcode.oauth.prod.en\0'+'A'*43:record})
        state=dict(schemaVersion=2,status='authenticated',storeKind='file',clientId='mcode-public',
            audience='agent-backend',scopes=['agent.default'],expiresAtMs=1,generation=3,buildEnv='prod',region='en')
        return {'oauth-store':raw(auth),'oauth-state':raw(state)}

    def projection(self,token='FAKE-ACCESS'):
        return raw(dict(version=1,updatedAtMs=1,auth=dict(accessToken=token,userEmail='FAKE-EMAIL')))

    def test_missing_is_unscanned_and_all_physical_families_unresolved(self):
        result=self.run_account(())
        self.assertEqual(result.required_sources,len(self.manifest.entries))
        self.assertEqual(result.observed_sources,0)
        self.assertEqual(result.unscanned_sources,result.required_sources)
        self.assertEqual(result.unresolved_coverage_families,('image-rootfs','image-environment','image-native-consumers'))
        self.assertEqual(sum(v for _,v in result.unaccounted_by_family),result.required_sources)
        for name in ('observe','complete','credential_entries','start','credentials'):
            self.assertFalse(hasattr(self.accounting,name));self.assertFalse(hasattr(result,name))

    def test_explicit_absence_is_only_an_acquisition_assertion(self):
        result=self.run_account()
        self.assertEqual(result.absent_sources,result.required_sources)
        self.assertEqual(result.unscanned_sources,0)
        self.assertEqual(len(result.unresolved_coverage_families),3)

    def test_container_adds_all_families_and_context_remains_original(self):
        ctx=replace(self.context,container_id='f'*64)
        manifest=replace(self.manifest,context=ctx)
        result=self.run_account(tuple(replace(o,context=ctx) for o in self.observations),manifest)
        self.assertEqual(len(result.unresolved_coverage_families),7)
        self.assertIn(('container-mount-sources',0),result.unaccounted_by_family)
        with self.assertRaises(RecordError):self.run_account(manifest=manifest)

    def test_context_mismatch_refuses_even_for_absent_sources(self):
        for key,value in [('image_id','sha256:'+'f'*64),('container_id','f'*64),('assembly_sha256','f'*64),('policy_sha256','f'*64)]:
            with self.subTest(key=key),self.assertRaises(RecordError):
                self.run_account((replace(self.observations[0],context=replace(self.context,**{key:value})),))

    def test_policy_binding_and_shortened_catalog_refuse(self):
        for ctx in [replace(self.context,image_id='sha256:'+'f'*64),replace(self.context,assembly_sha256='f'*64),
                    replace(self.context,policy_sha256='f'*64)]:
            with self.assertRaises(RecordError):self.run_account(manifest=replace(self.manifest,context=ctx))
        with self.assertRaises(RecordError):self.run_account(manifest=replace(self.manifest,entries=self.manifest.entries[:-1]))

    def test_duplicate_unknown_and_wrong_kind_observations_refuse(self):
        first=self.observations[0]
        for observations in [(first,first),(replace(first,source_id='unlisted'),),(replace(first,kind='environment'),)]:
            with self.assertRaises(RecordError):self.run_account(observations)

    def test_duplicate_ids_roles_unknown_families_and_groups_refuse(self):
        e=self.manifest.entries[0]
        cases=[replace(self.manifest,entries=self.manifest.entries+(e,)),
            replace(self.manifest,entries=tuple(replace(x,family='unknown') if x is e else x for x in self.manifest.entries)),
            replace(self.manifest,oauth_groups=(self.og,self.og)),
            replace(self.manifest,oauth_groups=()),
            replace(self.manifest,entries=self.manifest.entries+(replace(next(x for x in self.manifest.entries if x.kind=='oauth-store'),source_id='other'),))]
        for manifest in cases:
            with self.assertRaises(RecordError):self.run_account(manifest=manifest)

    def test_stale_future_predates_begin_and_naive_timestamps_refuse(self):
        for time in [self.now-timedelta(seconds=61),self.now+timedelta(microseconds=1),self.now-timedelta(microseconds=1),self.now.replace(tzinfo=None)]:
            with self.assertRaises(RecordError):self.run_account((replace(self.observations[0],observed_at=time),))
        with self.assertRaises(RecordError):self.run_account(begin=self.now.replace(tzinfo=None))

    def test_nonpresent_payloads_and_missing_evidence_refuse(self):
        for observation in [replace(self.observations[0],raw=b'FAKE-SECRET'),replace(self.observations[0],reference=''),
                            replace(self.observations[0],status='complete'),replace(self.observations[0],raw=bytearray())]:
            with self.assertRaises(RecordError):self.run_account((observation,))

    def test_unreadable_unscanned_and_unsupported_are_distinct(self):
        entries=self.manifest.entries
        result=self.run_account((self.obs(entries[0],'unreadable'),self.obs(entries[1],'unscanned'),
            self.obs(next(e for e in entries if e.kind=='lease-capability'),'present',b'FAKE-CAPABILITY')))
        self.assertEqual(result.unreadable_sources,1)
        self.assertEqual(result.unsupported_sources,1)
        self.assertEqual(result.unscanned_sources,len(entries)-2)

    def test_malformed_supported_source_is_unknown_never_absent(self):
        result=self.run_account(self.sources(**{'pi-auth':b'not-json FAKE-SECRET'}))
        self.assertEqual(result.unsupported_sources,1)
        self.assertEqual(result.absent_sources,result.required_sources-1)

    def test_output_repr_and_errors_never_echo_input_metadata_or_material(self):
        values=self.sources(**{'environment':raw({'FAKE_ENV':'FAKE-SECRET'})})
        values=tuple(replace(o,reference='https://FAKE-SECRET.example/path') for o in values)
        result=self.run_account(values)
        for value in [repr(result),json.dumps(asdict(result)),repr(self.manifest),repr(values)]:
            for forbidden in ['FAKE-SECRET','FAKE-ACQUISITION','FAKE-DATA-DIR','FAKE-SELECTION-REF','src0','https://']:
                self.assertNotIn(forbidden,value)
        with self.assertRaises(RecordError) as caught:self.run_account((replace(values[0],source_id='FAKE-SECRET'),))
        self.assertNotIn('FAKE-SECRET',str(caught.exception))

    def test_contracts_are_frozen_and_require_deep_immutable_exact_inputs(self):
        with self.assertRaises(FrozenInstanceError):self.manifest.context=None
        with self.assertRaises(RecordError):self.run_account(list(self.observations))
        with self.assertRaises(RecordError):self.run_account(manifest=replace(self.manifest,entries=list(self.manifest.entries)))
        result=self.run_account()
        with self.assertRaises(FrozenInstanceError):result.required_sources=0

    def test_source_and_byte_limits_refuse_at_limit_not_truncate(self):
        # Derive a new correctly digested policy with the exact exercised limit.
        for field,limit in [('sources',len(self.manifest.entries)),('bytes',2)]:
            value=self.audit.manifest();value['limits'][field]=limit
            digest=hashlib.sha256(CredentialAuditRequirements.encode(value)).hexdigest()
            audit=replace(self.audit,sha256=digest,limits=tuple(sorted(value['limits'].items())))
            ctx=replace(self.context,policy_sha256=digest)
            manifest=replace(self.manifest,audit=audit,context=ctx)
            obs=tuple(replace(o,context=ctx) for o in self.sources(**{'environment':b'{}'}))
            with self.assertRaises(RecordError):self.run_account(obs,manifest)
        with self.assertRaises(RecordError):self.run_account(self.sources(**{'environment':b' ' * 65537}))

    def test_elapsed_deadline_reaching_limit_refuses(self):
        times=iter([0,5]);self.accounting=self.m.CredentialSourceAccounting(clock=lambda:self.now,monotonic=lambda:next(times))
        with self.assertRaises(RecordError):self.run_account()

    def test_pi_material_and_unknown_semantics_both_survive(self):
        value={'x':{'type':'oauth','access':'FAKE-ACCESS','refresh':'FAKE-REFRESH','expires':1,'extra':'unknown'},
            'y':{'type':'api_key','key':'!FAKE-COMMAND'}}
        result=self.run_account(self.sources(**{'pi-auth':raw(value)}));counts=self.counts(result)
        self.assertEqual(counts['access_tokens'],1);self.assertEqual(counts['refresh_tokens'],1)
        self.assertEqual(counts['command_fields'],1);self.assertEqual(counts['unknown_records'],1)
        self.assertEqual(result.unsupported_sources,1)

    def test_explicit_environment_counts_literals_without_expansion(self):
        result=self.run_account(self.sources(**{'environment':raw({'A':'FAKE-TOKEN','B':'','C':'!not-executed'})}))
        self.assertEqual(self.counts(result)['literal_fields'],2)
        self.assertEqual(self.counts(result)['empty_fields'],1)

    def test_oauth_pair_counts_once_and_expired_material_is_retained(self):
        result=self.run_account(self.sources(**self.pair()))
        self.assertEqual(self.counts(result)['access_tokens'],1)
        self.assertEqual(self.counts(result)['refresh_tokens'],1)
        self.assertEqual(result.parsed_sources,2)

    def test_missing_oauth_partner_and_unknown_generation_remain_unresolved(self):
        data=self.pair();del data['oauth-state']
        result=self.run_account(self.sources(**data))
        self.assertEqual(result.unsupported_sources,1)
        data=self.pair(generation=4)
        self.assertEqual(self.run_account(self.sources(**data)).unsupported_sources,2)

    def test_projection_scope_comparison_and_primary_alerts(self):
        data=self.pair(scopes=['extra']);data['projection-namespaced']=self.projection('FAKE-DIFFERENT')
        result=self.run_account(self.sources(**data));counts=self.counts(result)
        self.assertEqual(counts['access_tokens'],2)
        self.assertEqual(counts['projection_mismatches'],1)
        self.assertGreater(counts['scope_alerts'],0)
        self.assertEqual(counts['primary_metadata_unknown'],0)

    def test_standalone_projection_keeps_primary_metadata_unknown(self):
        result=self.run_account(self.sources(**{'projection-shared':self.projection()}))
        self.assertEqual(self.counts(result)['access_tokens'],1)
        self.assertEqual(self.counts(result)['primary_metadata_unknown'],1)
        self.assertEqual(result.unsupported_sources,1)

    def test_projection_cannot_select_different_primary_group(self):
        entries=tuple(replace(e,primary_group_id='different') if e.kind=='projection-shared' else e for e in self.manifest.entries)
        with self.assertRaises(RecordError):self.run_account(manifest=replace(self.manifest,entries=entries))

    def test_config_and_model_material_counted_once_under_conditional_context(self):
        config={'provider':{'p':{'name':'p','options':{'apiKey':'FAKE-KEY'},'models':{'m':{'name':'m'}}}},'defaultModel':'p/m'}
        model={'provider':'p','model_id':'m','api_key':'FAKE-HOST'}
        sg=replace(self.sg,hypothesis=replace(self.hypothesis,selection_source='host-model-ref'))
        manifest=replace(self.manifest,selection_groups=(sg,))
        result=self.run_account(self.sources(**{'mcode-config':raw(config),'host-model-ref':raw(model)}),manifest)
        self.assertEqual(self.counts(result)['configured_key_fields'],1)
        self.assertEqual(self.counts(result)['host_key_fields'],1)
        self.assertEqual(self.counts(result)['conditional_sources'],2)
        self.assertEqual(result.unsupported_sources,2)

    def test_config_unknown_fields_preserve_known_material_and_unknown_counts(self):
        config={'logLevel':'debug','provider':{'minimax':{'options':{'apiKey':'FAKE-KEY'}}}}
        result=self.run_account(self.sources(**{'mcode-config':raw(config)}))
        self.assertEqual(self.counts(result)['configured_key_fields'],1)
        self.assertGreater(self.counts(result)['unparsed_config_fields'],0)
        self.assertGreater(self.counts(result)['unknown_sections'],0)
        self.assertEqual(result.unsupported_sources,1)

    def test_missing_config_context_or_partner_never_invents_empty_config(self):
        model={'provider':'p','model_id':'m','api_key':'FAKE-HOST'}
        result=self.run_account(self.sources(**{'host-model-ref':raw(model)}))
        self.assertEqual(result.unsupported_sources,1)
        self.assertEqual(self.counts(result)['host_key_fields'],1)
        with self.assertRaises(RecordError):self.run_account(manifest=replace(self.manifest,selection_groups=()))

    def test_distinct_consumer_budget_and_per_source_limit_are_strict(self):
        value=self.audit.manifest();value['limits']['consumers']=len(self.m.SOURCE_KINDS)
        digest=hashlib.sha256(CredentialAuditRequirements.encode(value)).hexdigest()
        audit=replace(self.audit,sha256=digest,limits=tuple(sorted(value['limits'].items())))
        ctx=replace(self.context,policy_sha256=digest)
        manifest=replace(self.manifest,audit=audit,context=ctx)
        with self.assertRaises(RecordError):
            self.run_account(tuple(replace(o,context=ctx) for o in self.observations),manifest)
        with self.assertRaises(RecordError):self.run_account(self.sources(**{'environment':b' '*65536}))

    def test_unknown_empty_and_bad_typed_present_data_cannot_be_absent(self):
        entry=next(e for e in self.manifest.entries if e.kind=='environment')
        for data in [b'',None,bytearray(b'{}'),'{}']:
            with self.assertRaises(RecordError):self.run_account((self.obs(entry,'present',data),))

    def test_partial_unknown_pi_counts_not_erased_by_other_unsupported_sources(self):
        value={'x':{'type':'oauth','access':'FAKE-A','refresh':'FAKE-R','expires':True}}
        result=self.run_account(self.sources(**{'pi-auth':raw(value),'lease-capability':b'FAKE-CAP'}))
        self.assertEqual(self.counts(result)['access_tokens'],1)
        self.assertEqual(self.counts(result)['unknown_records'],1)
        self.assertEqual(result.unsupported_sources,2)

    def test_group_role_and_namespace_mismatches_refuse_or_stay_unknown(self):
        groups=(replace(self.og,region='cn'),)
        result=self.run_account(self.sources(**self.pair()),replace(self.manifest,oauth_groups=groups))
        self.assertEqual(result.unsupported_sources,2)
        entry=next(e for e in self.manifest.entries if e.kind=='oauth-state')
        entries=tuple(replace(e,group_id='other') if e==entry else e for e in self.manifest.entries)
        other=replace(self.og,group_id='other',data_directory_id='OTHER-DIR')
        result=self.run_account(self.sources(**self.pair()),replace(self.manifest,entries=entries,oauth_groups=(self.og,other)))
        self.assertEqual(result.unsupported_sources,2)
        self.assertEqual(self.counts(result)['access_tokens'],0)

    def test_projection_without_explicit_primary_never_compares(self):
        entries=tuple(replace(e,primary_group_id=None) if e.kind=='projection-shared' else e for e in self.manifest.entries)
        data={**self.pair(),'projection-shared':self.projection()}
        result=self.run_account(self.sources(**data),replace(self.manifest,entries=entries))
        self.assertEqual(self.counts(result)['primary_metadata_unknown'],1)
        self.assertEqual(result.unsupported_sources,1)

    def test_wholly_unsupported_families_never_resolve(self):
        data={e.kind:b'FAKE-UNSUPPORTED' for e in self.manifest.entries}
        result=self.run_account(self.sources(**data))
        self.assertEqual(result.unsupported_sources,result.required_sources)
        self.assertEqual(len(result.unresolved_coverage_families),3)

    def test_assembly_accounting_does_not_read_files_environment_or_launch(self):
        with patch('builtins.open',side_effect=AssertionError('file read')), \
             patch('os.getenv',side_effect=AssertionError('environment read')), \
             patch('subprocess.run',side_effect=AssertionError('launch')):
            result=self.run_account(self.sources(**{'pi-auth':b'{}','environment':b'{}'}))
        self.assertEqual(result.parsed_sources,2)

    def test_stable_same_group_projection_matches_but_not_physical_coverage(self):
        data={**self.pair(),'projection-legacy':self.projection()}
        result=self.run_account(self.sources(**data))
        self.assertEqual(result.parsed_sources,3)
        self.assertEqual(self.counts(result)['access_tokens'],2)
        self.assertEqual(self.counts(result)['projection_mismatches'],0)
        self.assertEqual(len(result.unresolved_coverage_families),3)

    def test_clock_rollback_and_nonfinite_duration_refuse(self):
        for pair in [(2,1),(0,float('nan')),(False,1)]:
            times=iter(pair)
            self.accounting=self.m.CredentialSourceAccounting(clock=lambda:self.now,monotonic=lambda:next(times))
            with self.assertRaises(RecordError):self.run_account()

    def test_unknown_selection_fields_never_leak_fingerprint_or_resolver(self):
        result=self.run_account(self.sources(**{'mcode-config':b'{}'}))
        text=json.dumps(asdict(result))
        for forbidden in ('hypothesis_fingerprint','FAKE-SELECTION-REF','token_plan','managed-bearer-assumed'):
            self.assertNotIn(forbidden,text)

    def test_review_missing_host_partner_preserves_independent_config_counts(self):
        config={'logLevel':'debug','provider':{'minimax':{'options':{'apiKey':'FAKE-KEY'}}}}
        sg=replace(self.sg,hypothesis=replace(self.hypothesis,selection_source='host-model-ref'))
        manifest=replace(self.manifest,selection_groups=(sg,))
        result=self.run_account(self.sources(**{'mcode-config':raw(config)}),manifest)
        self.assertEqual(self.counts(result)['configured_key_fields'],1)
        self.assertEqual(self.counts(result)['unknown_sections'],1)
        self.assertEqual(self.counts(result)['unparsed_config_fields'],1)
        self.assertEqual(result.unsupported_sources,1)

    def test_review_unused_host_material_and_unparsed_fields_preserved(self):
        model={'provider':'p','model_id':'m','api_key':'FAKE-HOST','thinking':'extra'}
        result=self.run_account(self.sources(**{'host-model-ref':raw(model)}))
        self.assertEqual(self.counts(result)['host_key_fields'],1)
        self.assertEqual(self.counts(result)['unparsed_model_ref_fields'],1)
        self.assertEqual(result.unsupported_sources,1)

    def test_review_primary_group_and_digest_subclasses_refuse(self):
        class Alias(str):pass
        class MutableAlias:
            def __eq__(self,other):return other=='oauth'
        for value in [Alias('oauth'),MutableAlias()]:
            entries=tuple(replace(e,primary_group_id=value) if e.kind=='projection-shared' else e for e in self.manifest.entries)
            with self.assertRaises(RecordError):self.run_account(manifest=replace(self.manifest,entries=entries))
        for field,value in [('assembly_sha256',Alias('b'*64)),('policy_sha256',Alias(self.audit.sha256)),('container_id',Alias('f'*64))]:
            with self.assertRaises(RecordError):
                self.run_account(manifest=replace(self.manifest,context=replace(self.context,**{field:value})))
        audit=replace(self.audit)
        object.__setattr__(audit,'audit_authority_reference',Alias(self.audit.audit_authority_reference))
        with self.assertRaises(RecordError):self.run_account(manifest=replace(self.manifest,audit=audit))

    def test_review_custom_timezone_is_refused_without_execution_or_error_leak(self):
        calls=[]
        class HostileZone(tzinfo):
            def utcoffset(self,dt):
                calls.append(True)
                raise RuntimeError('FAKE-SECRET-TZ')
        moment=self.now.replace(tzinfo=HostileZone())
        for operation in [lambda:self.run_account(begin=moment),
                lambda:self.run_account((replace(self.observations[0],observed_at=moment),))]:
            with self.assertRaises(RecordError) as caught:operation()
            self.assertNotIn('FAKE-SECRET',str(caught.exception))
        self.assertEqual(calls,[])


if __name__=='__main__':unittest.main()
