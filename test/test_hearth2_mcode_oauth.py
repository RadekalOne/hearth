from copy import deepcopy
from dataclasses import asdict, FrozenInstanceError
import importlib.util
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1] / 'mcp/memory'))
from hearth2.store import RecordError

OAUTH = 'acf1ff9d270aca155e09b747d3e475a7e48c24bd5f84241d5268c1e3e1155674'
PROJECTION = 'b79bf405b47654e4295b918bfc0bf5d84e4f73d3b05197c89c909dedef8f9b9f'
ACCOUNT = 'A'*43
KEY = 'com.minimax.mcode.oauth.prod.en\0' + ACCOUNT


def raw(value): return json.dumps(value, ensure_ascii=True).encode()


class MCodeOAuthTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('hearth2.mcode_oauth'), 'OAuth parser missing')
        from hearth2 import mcode_oauth
        self.module = mcode_oauth
        self.parser = mcode_oauth.MCodeOAuthParser('0.4.1', OAUTH, PROJECTION)
        self.record = dict(schemaVersion=1, accessToken='FAKE-ACCESS', refreshToken='FAKE-REFRESH',
                           tokenType='Bearer', clientId='mcode-public', audience='agent-backend',
                           scopes=['agent.default'], expiresAtMs=2000, generation=3,
                           accountId='FAKE-IDENTITY', loginEpoch='FAKE-EPOCH')
        self.auth = dict(schemaVersion=1, records={KEY: self.record})
        self.state = dict(schemaVersion=2, status='authenticated', storeKind='file',
                          clientId='mcode-public', audience='agent-backend', scopes=['agent.default'],
                          expiresAtMs=2000, generation=3, buildEnv='prod', region='en')
        self.projection = dict(version=1, updatedAtMs=1000,
                               auth=dict(accessToken='FAKE-ACCESS', userEmail='FAKE-EMAIL'))
        self.context = dict(build_env='prod', region='en', account=ACCOUNT, now_ms=1000)

    def store(self, auth=None, state=None, **context):
        return self.parser.store_json(raw(self.auth if auth is None else auth),
            raw(self.state if state is None else state), **{**self.context, **context})

    def test_exact_reviewed_version_and_both_bundle_hashes(self):
        for values in [('0.4.2', OAUTH, PROJECTION), ('0.4.1', 'a'*64, PROJECTION),
                       ('0.4.1', OAUTH, 'a'*64), (True, OAUTH, PROJECTION)]:
            with self.assertRaises(RecordError): self.module.MCodeOAuthParser(*values)

    def test_store_state_match_returns_only_safe_summary(self):
        result = self.store()
        self.assertEqual((result.access_tokens, result.refresh_tokens, result.identity_fields), (1, 1, 2))
        self.assertEqual(result.expiry_state, 'future')
        self.assertEqual(result.state_status, 'authenticated')
        self.assertIsNone(result.matches_primary)
        with self.assertRaises(FrozenInstanceError): result.access_tokens = 0

    def test_expired_token_is_present_even_if_state_claims_authenticated(self):
        result = self.store(now_ms=2000)
        self.assertEqual(result.expiry_state, 'expired')
        self.assertEqual((result.access_tokens, result.refresh_tokens), (1, 1))

    def test_generation_and_namespace_mismatch_refuse(self):
        for changes in [dict(generation=4),
                        dict(region='cn'), dict(buildEnv='test')]:
            with self.subTest(changes=changes), self.assertRaises(RecordError):
                self.store(state={**self.state, **changes})

    def test_foreign_and_additional_records_are_never_ignored(self):
        for key in [KEY.replace('prod.en', 'prod.cn'), KEY[:-1]+'B', 'arbitrary', 'bad\0key']:
            with self.assertRaises(RecordError): self.store(auth=dict(schemaVersion=1, records={key:self.record}))
            with self.assertRaises(RecordError): self.store(auth=dict(schemaVersion=1, records={KEY:self.record, key:self.record}))

    def test_empty_store_is_not_a_missing_source_or_absence_authority(self):
        state = {k:v for k,v in self.state.items() if k != 'expiresAtMs'}
        state['status'] = 'anonymous'
        result = self.store(auth=dict(schemaVersion=1,records={}), state=state)
        self.assertEqual((result.access_tokens, result.refresh_tokens, result.expiry_state), (0,0,'absent'))
        self.assertNotIn('complete', asdict(result))
        with self.assertRaises(RecordError): self.store(auth=dict(schemaVersion=1,records={}))
        with self.assertRaises(RecordError): self.parser.store_json(None, raw(state), **self.context)

    def test_anonymous_retained_credential_is_still_counted(self):
        result = self.store(state={**self.state, 'status':'anonymous'})
        self.assertEqual((result.access_tokens, result.refresh_tokens), (1,1))

    def test_unknown_fields_and_schemas_refuse(self):
        for changes in [dict(schemaVersion=2), dict(accessToken=''), dict(tokenType='Basic'),
                        dict(scopes=[True]), dict(secret='FAKE-HIDDEN')]:
            with self.assertRaises(RecordError):
                self.store(auth=dict(schemaVersion=1,records={KEY:{**self.record, **changes}}))
        for changes in [dict(schemaVersion=1), dict(storeKind='os-keyring'), dict(unknown='FAKE'),
                        dict(accessToken='FAKE'), dict(authorization=dict(device_code='FAKE'))]:
            with self.assertRaises(RecordError): self.store(state={**self.state, **changes})

    def test_numbers_are_safe_integers_not_bools_floats_or_switches(self):
        for key in ['schemaVersion','generation','expiresAtMs']:
            for value in [True,-1,1.5,2**53]:
                with self.assertRaises(RecordError):
                    self.store(auth=dict(schemaVersion=1,records={KEY:{**self.record,key:value}}))
        for value in [True,-1,1.5,2**53]:
            with self.assertRaises(RecordError): self.store(now_ms=value)

    def test_projection_shapes_literal_tokens_and_unknown_expiry(self):
        for kind in ['namespaced','legacy','shared']:
            data = {**self.projection,'auth':{'accessToken':'  !literal $ENV  '}}
            result = self.parser.projection_json(raw(data), source_kind=kind)
            self.assertEqual((result.access_tokens,result.refresh_tokens,result.expiry_state), (1,0,'unknown'))
            self.assertEqual(result.source_kind, 'mcode-projection-'+kind)

    def test_projection_empty_effective_token_or_unknown_fields_refuse(self):
        for value in ['', '   ', None, 7]:
            with self.assertRaises(RecordError):
                self.parser.projection_json(raw({**self.projection,'auth':{'accessToken':value}}), source_kind='shared')
        for data in [{**self.projection,'unknown':'FAKE'},
                     {**self.projection,'auth':{**self.projection['auth'],'refreshToken':'FAKE'}},
                     {**self.projection,'version':True}, {**self.projection,'updatedAtMs':2**53}]:
            with self.assertRaises(RecordError): self.parser.projection_json(raw(data),source_kind='shared')

    def test_projection_comparison_detects_stale_token_without_disclosing_it(self):
        def compare(data):
            return self.parser.compare_projection(raw(self.auth),raw(self.state),raw(data),
                                                  source_kind='namespaced',**self.context)
        self.assertTrue(compare(self.projection).matches_primary)
        changed = {**self.projection,'auth':{'accessToken':'FAKE-OLD'}}
        result = compare(changed)
        self.assertFalse(result.matches_primary)
        self.assertEqual(result.access_tokens,1)
        self.assertTrue(compare({**self.projection,'auth':{'accessToken':'  FAKE-ACCESS  '}}).matches_primary)

    def test_missing_primary_with_projection_is_a_mismatch_not_absence(self):
        state = {**self.state, 'status':'anonymous'}
        state.pop('expiresAtMs')
        result = self.parser.compare_projection(raw(dict(schemaVersion=1,records={})),raw(state),
            raw(self.projection),source_kind='shared',**self.context)
        self.assertFalse(result.matches_primary)
        self.assertEqual(result.access_tokens,1)

    def test_authorization_material_is_counted_and_never_output(self):
        state = {**self.state,'status':'authorizing','authorization':dict(
            leaseId='FAKE-LEASE',leaseExpiresAtMs=3000,userCode='FAKE-USER-CODE',
            verificationUri='https://example.invalid/FAKE-URL')}
        state.pop('expiresAtMs')
        result = self.store(auth=dict(schemaVersion=1,records={}), state=state)
        self.assertEqual(result.authorization_fields,3)
        for secret in ['FAKE-LEASE','FAKE-USER-CODE','FAKE-URL']:
            self.assertNotIn(secret,repr(result))

    def test_results_have_no_tokens_identities_or_inventory_authority(self):
        text = repr(self.store()) + str(asdict(self.store()))
        for secret in ['FAKE-ACCESS','FAKE-REFRESH','FAKE-IDENTITY','FAKE-EPOCH',ACCOUNT,
                       'complete','credential_entries','observed_at','sha256','generation']:
            self.assertNotIn(secret,text)
        self.assertFalse(hasattr(self.parser,'observe'))
        self.assertFalse(hasattr(self.parser,'scan'))

    def test_fixed_errors_have_no_source_exception_context(self):
        for auth in [b'{"FAKE-SECRET":', b'\xff', b'{"schemaVersion":1,"schemaVersion":1}',
                     b'{"FAKE":"\\ud800"}', b' '*65537]:
            with self.assertRaises(RecordError) as error:
                self.parser.store_json(auth,raw(self.state),**self.context)
            self.assertEqual(str(error.exception),'unsupported MCode OAuth input')
            self.assertIsNone(error.exception.__context__)
            self.assertIsNone(error.exception.__cause__)

    def test_no_file_environment_or_provider_access(self):
        with patch('builtins.open',side_effect=AssertionError('file access forbidden')), \
                patch('os.getenv',side_effect=AssertionError('environment forbidden')), \
                patch('subprocess.run',side_effect=AssertionError('execution forbidden')):
            self.store()
            self.parser.projection_json(raw(self.projection),source_kind='shared')

    def test_namespace_and_projection_kind_are_strict(self):
        for changes in [dict(build_env='unknown'),dict(region='global'),dict(account='short'),
                        dict(account='A'*42+'='),dict(account='A'*42+'\0')]:
            with self.assertRaises(RecordError): self.store(**changes)
        with self.assertRaises(RecordError):
            self.parser.projection_json(raw(self.projection),source_kind='caller-selected-path')

    def test_existing_decoder_does_not_accept_oauth_control_keys_by_default(self):
        from hearth2.minimax_consumer import _load
        with self.assertRaises(RecordError): _load(raw(self.auth))
        self.store()
        with self.assertRaises(RecordError): _load(raw(self.auth))

    def test_ecmascript_projection_trim_and_primary_is_unnormalized(self):
        for char, expected in [('\u0085',False), ('\u001c',False), ('\ufeff',True)]:
            with self.subTest(character=ord(char)):
                data = {**self.projection,'auth':{'accessToken':char+'FAKE-ACCESS'+char}}
                result = self.parser.compare_projection(raw(self.auth),raw(self.state),raw(data),
                                                        source_kind='shared',**self.context)
                self.assertEqual(result.matches_primary,expected)
        record = {**self.record,'accessToken':'\ufeffFAKE-ACCESS\ufeff'}
        result = self.parser.compare_projection(raw(dict(schemaVersion=1,records={KEY:record})),
            raw(self.state),raw(self.projection),source_kind='shared',**self.context)
        self.assertFalse(result.matches_primary)

    def test_native_bom_only_projection_refuses(self):
        data = {**self.projection,'auth':{'accessToken':'\ufeff'}}
        with self.assertRaises(RecordError):
            self.parser.projection_json(raw(data),source_kind='shared')

    def test_ecmascript_non_whitespace_is_retained_in_projection(self):
        for char in ['\u0085','\u001c']:
            result = self.parser.projection_json(
                raw({**self.projection,'auth':{'accessToken':char}}),source_kind='shared')
            self.assertEqual(result.access_tokens,1)

    def test_record_state_expiry_divergence_is_reported_not_dropped(self):
        result=self.store(state={**self.state,'expiresAtMs':1000})
        self.assertEqual((result.access_tokens,result.refresh_tokens,result.expiry_state),(1,1,'future'))
        self.assertTrue(result.expiry_mismatch)
        state={k:v for k,v in self.state.items() if k!='expiresAtMs'}
        self.assertTrue(self.store(state=state).expiry_mismatch)

    def test_missing_and_extra_scopes_are_visible_without_claiming_usable_login(self):
        record={**self.record,'scopes':['other.scope']}
        state={**self.state,'status':'scope_upgrade_required','scopes':['other.scope']}
        result=self.store(auth=dict(schemaVersion=1,records={KEY:record}),state=state)
        self.assertTrue(result.record_missing_required_scope)
        self.assertEqual((result.extra_scope_fields,result.access_tokens,result.refresh_tokens),(2,1,1))
        self.assertFalse(result.state_scope_mismatch)
        result=self.store(state={**self.state,'scopes':[]})
        self.assertTrue(result.state_scope_mismatch)
        self.assertFalse(result.record_missing_required_scope)
        record={**self.record,'scopes':['agent.default','FAKE-SCOPE-NAME']}
        result=self.store(auth=dict(schemaVersion=1,records={KEY:record}))
        self.assertEqual(result.extra_scope_fields,1)
        self.assertNotIn('FAKE-SCOPE-NAME',repr(result))

    def test_invalid_or_unbounded_scopes_still_refuse(self):
        for scopes in ['agent.default',[1],['a']*65]:
            with self.assertRaises(RecordError):self.store(state={**self.state,'scopes':scopes})

    def test_comparison_retains_primary_expiry_and_scope_alerts(self):
        record={**self.record,'scopes':['other.scope']}
        state={**self.state,'expiresAtMs':1000}
        result=self.parser.compare_projection(raw(dict(schemaVersion=1,records={KEY:record})),raw(state),
            raw(self.projection),source_kind='shared',**self.context)
        self.assertTrue(result.matches_primary)
        self.assertTrue(result.expiry_mismatch)
        self.assertTrue(result.record_missing_required_scope)
        self.assertTrue(result.state_scope_mismatch)
        self.assertEqual(result.extra_scope_fields,1)
        self.assertEqual(result.expiry_state,'unknown')

    def test_standalone_projection_does_not_assert_primary_scope_metadata(self):
        result=self.parser.projection_json(raw(self.projection),source_kind='shared')
        self.assertIsNone(result.expiry_mismatch)
        self.assertIsNone(result.record_missing_required_scope)
        self.assertIsNone(result.state_scope_mismatch)
        self.assertIsNone(result.extra_scope_fields)


if __name__=='__main__': unittest.main()
