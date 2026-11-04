from dataclasses import asdict, replace
import importlib.util
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).parents[1]/'mcp/memory'))
from hearth2.store import RecordError

CONFIG='b79bf405b47654e4295b918bfc0bf5d84e4f73d3b05197c89c909dedef8f9b9f'
OD='7f91af66b8692739662669da6a04ba294d9da871bb667b19ce6ff98cddd42e73'
MI='fc77436612ef5b8d771252eb6f47772e2f4b19ee82e8a815b351f78540f4c9a0'

def raw(value):return json.dumps(value).encode()


class MCodeConfigTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('hearth2.mcode_config'),'config analysis missing')
        from hearth2 import mcode_config
        self.module=mcode_config
        self.parser=mcode_config.MCodeConfigParser('0.4.1',CONFIG,OD,MI)

    def context(self,**changes):
        values=dict(resolver='OD',region='en',preset_models=('MiniMax-M3','MiniMax-M2.7'),preset_default_model='MiniMax-M3',
            api_models=('MiniMax-M3','MiniMax-M2.7'),managed_runtime=True,
            managed_bearer_present=True,selection_source='runtime-default',require_catalog=False,
            check_availability=False,allow_custom_prefix_fallback=False,reference='fixture:context')
        return self.module.SelectionHypothesis(**{**values,**changes})

    def analyze(self,value,**changes):return self.parser.analyze(raw(value),self.context(**changes))

    def custom(self,**changes):
        provider=dict(kind='custom',enabled=True,options=dict(apiKey='FAKE-KEY',baseURL='https://acme.example.test/v1'),models={'m1':{}})
        return dict(custom_provider={'acme':{**provider,**changes}},defaultModel='custom_provider:acme/m1')

    def test_exact_sources_and_context_are_required(self):
        for values in [('0.4.2',CONFIG,OD,MI),('0.4.1','a'*64,OD,MI),('0.4.1',CONFIG,OD,'a'*64)]:
            with self.assertRaises(RecordError):self.module.MCodeConfigParser(*values)
        with self.assertRaises(RecordError):self.parser.analyze(b'{}',None)
        for changes in [dict(resolver='unknown'),dict(build_env='test'),dict(require_catalog=1),
                        dict(preset_models=['MiniMax-M3']),dict(reference='')]:
            with self.assertRaises(RecordError):self.context(**changes)

    def test_M1_empty_production_config_requires_managed_oauth(self):
        result=self.analyze({})
        self.assertEqual((result.outcome,result.route,result.credential_source),('conditional','token_plan','managed-bearer-assumed'))
        self.assertFalse(result.fallback)
        self.assertEqual(result.configured_key_fields,0)

    def test_user_authorization_can_satisfy_native_sync_check_but_is_unresolved(self):
        value={'provider':{'minimax':{'options':{'headers':{'Authorization':'FAKE-USER-AUTH'}}}}}
        result=self.analyze(value,managed_bearer_present=False)
        self.assertEqual(result.route,'token_plan')
        self.assertTrue(result.unresolved_http_auth)

    def test_M2_M4_managed_rewrite_key_reset_is_conditional(self):
        for url,conflict in [('https://proxy.example.test/v1',False),('https://agent.minimax.io/v1',True),(None,True)]:
            options={'apiKey':'FAKE-USER'}
            if url:options['baseURL']=url
            result=self.analyze({'provider':{'minimax':{'options':options}}})
            self.assertEqual(result.route,'token_plan')
            self.assertEqual(result.unresolved_http_auth,conflict)
            self.assertEqual(result.configured_key_fields,1)

    def test_M5_nonempty_models_replace_empty_models_keep_preset(self):
        value={'provider':{'minimax':{'models':{'MiniMax-M2.7':{}}}}}
        self.assertEqual(self.analyze(value,check_availability=True).outcome,'error')
        self.assertEqual(self.analyze(value).route,'token_plan')
        value['provider']['minimax']['models']={}
        self.assertEqual(self.analyze(value,check_availability=True).route,'token_plan')

    def test_unprotected_preset_placeholder_is_not_a_stored_user_key(self):
        value={'provider':{'minimax':{'options':{'authMode':'api-key','baseURL':'https://agent.minimax.io/v1'}}}}
        result=self.analyze(value,managed_runtime=False)
        self.assertEqual((result.route,result.credential_source,result.configured_key_fields),
                         ('provider_api_key','preset-placeholder',0))

    def test_I1_I2_managed_inference_for_arbitrary_plain_provider(self):
        for url in ['https://agent.minimax.io/v1','HTTPS://Agent.MiniMax.io:443/v1']:
            result=self.analyze(dict(provider={'myproxy':dict(options={'baseURL':url},models={'m':{}})},defaultModel='myproxy/m'))
            self.assertEqual(result.route,'token_plan')

    def test_I3_I5_unsupported_url_or_authmode_refuses(self):
        for options in [dict(apiKey='FAKE',baseURL='https://u:p@agent.minimax.io/v1'),
                        dict(apiKey='FAKE',baseURL='https://foo.example.test/v1',authMode='bearer')]:
            with self.assertRaises(RecordError):self.analyze(dict(provider={'foo':{'options':options}},defaultModel='foo/m'))

    def test_I4_explicit_managed_with_foreign_url_is_error(self):
        result=self.analyze(dict(provider={'foo':dict(options=dict(authMode='managed-login',baseURL='https://proxy.example.test/v1'))},defaultModel='foo/m'))
        self.assertEqual(result.outcome,'error')

    def test_B1_B2_API_source_missing_differs_by_resolver(self):
        value=dict(minimaxModelSource='minimax_api_key')
        self.assertEqual(self.analyze(value,resolver='OD').route,'token_plan')
        self.assertEqual(self.analyze(value,resolver='MI').outcome,'error')
        value['minimax_api']={'apiKey':'FAKE-OPEN-PLATFORM'}
        for resolver in ['OD','MI']:
            self.assertEqual(self.analyze(value,resolver=resolver).route,'minimax_api_key')

    def test_B3_empty_key_errors_without_fallback(self):
        for resolver in ['OD','MI']:
            result=self.analyze(dict(minimaxModelSource='minimax_api_key',minimax_api={'apiKey':'  '}),resolver=resolver)
            self.assertEqual((result.outcome,result.fallback),('error',False))

    def test_B4_prefix_overrides_switch(self):
        value=dict(defaultModel='minimax_api/MiniMax-M3',minimaxModelSource='token_plan',minimax_api={'apiKey':'FAKE'})
        self.assertEqual(self.analyze(value).route,'minimax_api_key')

    def test_B6_custom_case_insensitive_header_merge_and_conflict(self):
        value=self.custom()
        value['custom_provider']['acme']['options']['headers']={'X-Trace':'prov','Authorization':'FAKE-HEADER'}
        value['custom_provider']['acme']['models']['m1']['headers']={'x-trace':'model'}
        result=self.analyze(value)
        self.assertEqual(result.route,'custom_provider')
        self.assertEqual((result.stored_header_fields,result.effective_header_fields),(3,2))
        self.assertTrue(result.unresolved_http_auth)

    def test_B7_B8_pi_auth_getter_remains_unresolved(self):
        result=self.analyze(self.custom(kind='oauth',options={'baseURL':'https://acme.example.test/v1'}))
        self.assertEqual((result.outcome,result.credential_source),('unresolved','pi-auth-unparsed'))
        self.assertIsNone(result.effective_header_fields)

    def test_B9_values_are_literal_never_helpers_or_environment(self):
        for key in ['$ACME_KEY','!never-execute','\ufeffFAKE\ufeff']:
            value=self.custom(options=dict(apiKey=key,baseURL='https://acme.example.test/v1'))
            self.assertEqual(self.analyze(value).route,'custom_provider')

    def test_N1_N2_D1_BYOK_misses_preserve_OD_MI_difference(self):
        for changes in [dict(models={}),dict(enabled=False),dict(models={'m9':{}})]:
            value=self.custom(**changes)
            od=self.analyze(value,resolver='OD');mi=self.analyze(value,resolver='MI')
            self.assertEqual((od.route,od.fallback),('token_plan',True))
            self.assertEqual(mi.outcome,'error')

    def test_N3_plain_provider_no_models_does_not_use_fallback(self):
        value=dict(provider={'foo':{'options':{'apiKey':'FAKE','baseURL':'https://foo.example.test/v1'}}},defaultModel='foo/m')
        result=self.analyze(value)
        self.assertEqual((result.route,result.fallback),('provider_api_key',False))
        self.assertEqual(self.analyze(value,check_availability=True).outcome,'error')

    def test_N6_bare_custom_key_requires_explicit_remapping_flag(self):
        value=self.custom();value['defaultModel']='acme/m1'
        self.assertEqual(self.analyze(value).outcome,'error')
        ctx=self.context(selection_source='host-model-ref',allow_custom_prefix_fallback=True)
        result=self.parser.analyze(raw(value),ctx,model_ref_json=raw(dict(provider='acme',model_id='m1')))
        self.assertEqual(result.route,'custom_provider')

    def test_runtime_default_cannot_claim_native_host_remapping_flags(self):
        with self.assertRaises(RecordError):self.context(allow_custom_prefix_fallback=True)

    def test_blank_context_reference_is_not_meaningful(self):
        with self.assertRaises(RecordError):self.context(reference='   ')

    def test_D2_disabled_model_differs_from_disabled_provider(self):
        value=self.custom(models={'m1':{'enabled':False}})
        self.assertEqual(self.analyze(value).route,'custom_provider')
        ctx=self.context(selection_source='host-model-ref',require_catalog=True)
        result=self.parser.analyze(raw(value),ctx,model_ref_json=raw(dict(provider='custom_provider:acme',model_id='m1')))
        self.assertEqual(result.outcome,'error')

    def test_H1_H2_plain_headers_are_case_sensitive(self):
        value=dict(provider={'minimax':dict(options={'headers':{'X-Trace':'p','authorization':'FAKE'}},models={'MiniMax-M3':{'headers':{'X-Trace':'m'}}})})
        result=self.analyze(value)
        self.assertEqual(result.stored_header_fields,3)
        self.assertEqual(result.effective_header_fields,3)
        self.assertTrue(result.unresolved_http_auth)

    def test_H3_host_model_ref_overrides_are_a_separate_credential_source(self):
        value=dict(provider={'foo':{'options':{'apiKey':'FAKE-BASE','baseURL':'https://foo.example.test/v1'}}})
        ctx=self.context(selection_source='host-model-ref')
        result=self.parser.analyze(raw(value),ctx,model_ref_json=raw(dict(provider='foo',model_id='m',api_key='FAKE-HOST',base_url='https://alt.example.test/v1')))
        self.assertEqual((result.route,result.host_key_fields,result.configured_key_fields),('provider_api_key',1,1))
        with self.assertRaises(RecordError):self.parser.analyze(raw(value),ctx)

    def test_unused_disabled_reserved_credentials_are_counted_before_rewrite(self):
        value=self.custom(enabled=False)
        value['provider']={'minimax_api':{'options':{'apiKey':'FAKE-RESERVED'}}}
        result=self.analyze(value)
        self.assertEqual(result.configured_key_fields,2)

    def test_yaml12_strings_on_off_are_not_yaml11_booleans(self):
        data=b'provider:\n  foo:\n    options:\n      apiKey: on\n      baseURL: https://foo.example.test/v1\ndefaultModel: foo/m\n'
        self.assertEqual(self.parser.analyze(data,self.context()).route,'provider_api_key')

    def test_yaml_aliases_anchors_tags_merges_duplicates_multidoc_refuse(self):
        for data in [b'provider: &a {}',b'provider: *a',b'provider: !!python/object:os.system {}',
                     b'provider: {}\nprovider: {}',b'provider: {foo: {options: {apiKey: a, apiKey: b}}}',
                     b'<<: {}',b'{}\n---\n{}',b'%YAML 1.1\n---\n{}']:
            with self.subTest(data=data),self.assertRaises(RecordError):self.parser.analyze(data,self.context())

    def test_unknown_fields_and_unsupported_native_formats_refuse(self):
        for value in [self.custom(enabled='false'),self.custom(enabled=0),dict(defaultModel='custom_provider:minimax-legacy/m'),
                      dict(provider={'foo':{'options':{'baseURL':'https://foo.example.test/v1?key=FAKE'}}})]:
            with self.assertRaises(RecordError):self.analyze(value)

    def test_bounds_invalid_unicode_and_numeric_ambiguities_refuse(self):
        for data in [b' '*65537,b'provider: '+b'['*10+b']'*10,raw(dict(defaultModel='x'*8193)),
                     b'\xff',b'defaultModel: "\\uD800"',b'defaultModel: 01',b'defaultModel: 1e9']:
            with self.assertRaises(RecordError):self.parser.analyze(data,self.context())

    def test_outputs_errors_and_context_repr_are_value_free(self):
        result=self.analyze(self.custom())
        output=repr(result)+str(asdict(result))
        for text in ['FAKE-KEY','acme.example.test','complete','credential_entries','observed_at','reference']:
            self.assertNotIn(text,output)
        self.assertNotIn('fixture:context',repr(self.context()))
        self.assertFalse(hasattr(self.parser,'observe'));self.assertFalse(hasattr(self.parser,'scan'))
        for data in [b'provider: [FAKE-SECRET',raw(dict(provider='FAKE-SECRET'))]:
            with self.assertRaises(RecordError) as error:self.parser.analyze(data,self.context())
            self.assertEqual(str(error.exception),'unsupported MCode configuration input')
            self.assertIsNone(error.exception.__context__)

    def test_no_files_env_helpers_or_yaml_constructors(self):
        import yaml
        with patch('builtins.open',side_effect=AssertionError('file forbidden')), \
             patch('os.getenv',side_effect=AssertionError('env forbidden')), \
             patch('subprocess.run',side_effect=AssertionError('exec forbidden')), \
             patch.object(yaml,'load',side_effect=AssertionError('constructor forbidden')):
            self.analyze(self.custom())

    def test_reviewed_full_OD_hash_accepted_and_shortened_typo_rejected(self):
        correct='7f91af66b8692739662669da6a04ba294d9da871bb667b19ce6ff98cddd42e73'
        shortened='7f91af66b8692739669da6a04ba294d9da871bb667b19ce6ff98cddd42e73'
        with self.subTest(identity='reviewed'):
            self.module.MCodeConfigParser('0.4.1',CONFIG,correct,MI)
        with self.subTest(identity='typo'):
            with self.assertRaises(RecordError):self.module.MCodeConfigParser('0.4.1',CONFIG,shortened,MI)

    def test_bare_custom_provider_without_requested_model_never_remaps(self):
        value=self.custom()
        for resolver in ['OD','MI']:
            ctx=self.context(resolver=resolver,selection_source='host-model-ref',allow_custom_prefix_fallback=True)
            result=self.parser.analyze(raw(value),ctx,model_ref_json=raw(dict(provider='acme',model_id='missing')))
            self.assertEqual((result.outcome,result.fallback),('error',False))

    def test_original_whitespace_base_url_resets_key_without_trimming_reset_condition(self):
        for url,source in [(' ','managed-bearer-assumed'),('\t\n','managed-bearer-assumed'),('','mixed-assumed')]:
            with self.subTest(url=url):
                value={'provider':{'minimax':{'options':{'apiKey':'FAKE-USER','baseURL':url}}}}
                result=self.analyze(value)
                self.assertEqual(result.credential_source,source)
                self.assertEqual(result.configured_key_fields,1)

    def test_competing_auth_headers_remain_unresolved_for_every_route(self):
        for name in ['x-api-key','X-Api-Key','api-key','X-Goog-Api-Key','Cookie']:
            for kind in ['plain','custom','managed']:
                with self.subTest(name=name,kind=kind):
                    if kind=='custom':
                        value=self.custom(options={'apiKey':'FAKE','baseURL':'https://acme.example.test/v1','headers':{name:'FAKE-HEADER'}})
                    elif kind=='managed':value={'provider':{'minimax':{'options':{'headers':{name:'FAKE-HEADER'}}}}}
                    else:value={'provider':{'foo':{'options':{'apiKey':'FAKE','baseURL':'https://foo.example.test/v1','headers':{name:'FAKE-HEADER'}}}},'defaultModel':'foo/m'}
                    self.assertTrue(self.analyze(value).unresolved_http_auth)

    def test_migration_eligible_raw_providers_refuse_even_when_unused(self):
        for models in [{'m':{}},{}]:
            value={'provider':{'foo':{'options':{'apiKey':'FAKE','baseURL':'https://foo.example.test/v1'},'models':models}}}
            with self.assertRaises(RecordError):self.analyze(value)
            with self.assertRaises(RecordError):self.analyze({**value,'defaultModel':'foo/m'})
            self.assertEqual(self.analyze({**value,'defaultModel':'foo/m'},managed_runtime=False).route,'provider_api_key')

    def test_non_ascii_url_margins_refuse_instead_of_guessing_whatwg_trimming(self):
        value={'provider':{'minimax':{'options':{'apiKey':'FAKE','baseURL':'\ufeffhttps://agent.minimax.io/v1\ufeff'}}}}
        with self.assertRaises(RecordError):self.analyze(value)

    def test_selection_is_bound_to_resolver_and_non_secret_hypothesis(self):
        first=self.analyze({});same=self.analyze({},reference='FAKE-SECRET-REFERENCE')
        self.assertEqual(first.resolver,'OD')
        self.assertRegex(first.hypothesis_fingerprint,r'^[0-9a-f]{64}$')
        self.assertEqual(first.hypothesis_fingerprint,same.hypothesis_fingerprint)
        self.assertNotEqual(first.hypothesis_fingerprint,self.analyze({},resolver='MI').hypothesis_fingerprint)
        self.assertNotEqual(first.hypothesis_fingerprint,self.analyze({},check_availability=True).hypothesis_fingerprint)
        self.assertNotIn('FAKE-SECRET-REFERENCE',repr(same))

    def test_bearer_and_pi_source_labels_state_assumptions(self):
        self.assertEqual(self.analyze({}).credential_source,'managed-bearer-assumed')
        value={'provider':{'minimax':{'options':{'apiKey':'FAKE'}}}}
        self.assertEqual(self.analyze(value).credential_source,'mixed-assumed')
        value=self.custom(kind='oauth',options={'baseURL':'https://acme.example.test/v1'})
        self.assertEqual(self.analyze(value).credential_source,'pi-auth-unparsed')

    def test_API_catalog_cannot_disagree_with_native_preset_alias(self):
        with self.assertRaises(RecordError):self.context(api_models=('MiniMax-M3',))

    def test_native_digit_prefixed_provider_and_model_ids(self):
        value=self.custom(models={'01-ai/yi-large':{}})
        value['custom_provider']={'3rd-party':value['custom_provider']['acme']}
        value['defaultModel']='custom_provider:3rd-party/01-ai/yi-large'
        self.assertEqual(self.analyze(value).route,'custom_provider')
        data=b'custom_provider:\n  3rd-party:\n    kind: custom\n    options: {apiKey: k, baseURL: https://x.example/v1}\n    models: {01-ai/yi-large: {}}\ndefaultModel: custom_provider:3rd-party/01-ai/yi-large\n'
        self.assertEqual(self.parser.analyze(data,self.context()).route,'custom_provider')

    def test_numeric_model_fallback_uses_JS_integer_index_order(self):
        value=self.custom(enabled=False)
        value['provider']={'minimax':{'models':{'10':{},'2':{'headers':{'x-api-key':'FAKE'}}}}}
        result=self.analyze(value)
        self.assertTrue(result.fallback)
        self.assertTrue(result.unresolved_http_auth)

    def test_numeric_provider_fallback_uses_JS_integer_index_order(self):
        value=self.custom(enabled=False)
        value['provider']={name:{'options':{'apiKey':'FAKE','baseURL':'https://foo.example/v1',
            'headers':({'x-api-key':'FAKE'} if name=='2' else {})},'models':{'m':{}}} for name in ['10','2']}
        result=self.analyze(value,managed_runtime=False)
        self.assertTrue(result.fallback)
        self.assertTrue(result.unresolved_http_auth)

    def test_unparsed_real_file_sections_force_unresolved_without_projection(self):
        value={'logLevel':'info','memory':{'secret':'FAKE-HIDDEN'},'beta':{'experimental':True},
            'provider':{'minimax':{'options':{'apiKey':'FAKE-KNOWN'},'models':{'MiniMax-M3':{
                'temperature':True,'limit':{'context':200000}}}}}}
        result=self.analyze(value)
        self.assertEqual((result.outcome,result.route),('unresolved','unresolved'))
        self.assertEqual((result.unknown_sections,result.unparsed_config_fields),(2,5))
        self.assertEqual(result.configured_key_fields,1)
        self.assertIsNone(result.effective_header_fields)
        self.assertFalse(result.fallback)
        self.assertNotIn('FAKE-HIDDEN',repr(result))

    def test_unparsed_native_ModelRef_fields_force_unresolved(self):
        ctx=self.context(selection_source='host-model-ref')
        ref=dict(provider='foo',model_id='m',api_key='FAKE-HOST',base_url='https://foo.example/v1',
                 thinking_level='high',capabilities={'vision':False})
        result=self.parser.analyze(b'{}',ctx,model_ref_json=raw(ref))
        self.assertEqual((result.outcome,result.route,result.host_key_fields),('unresolved','unresolved',1))
        self.assertEqual(result.unparsed_model_ref_fields,2)
        self.assertNotIn('FAKE-HOST',repr(result))

    def test_unparsed_metadata_cannot_hide_malformed_known_credential_fields(self):
        with self.assertRaises(RecordError):
            self.analyze({'logLevel':'info','provider':{'minimax':{'options':{'apiKey':None}}}})
        ref=dict(provider='foo',model_id='m',api_key=None,thinking_level='high')
        with self.assertRaises(RecordError):
            self.parser.analyze(b'{}',self.context(selection_source='host-model-ref'),model_ref_json=raw(ref))


if __name__=='__main__':unittest.main()
