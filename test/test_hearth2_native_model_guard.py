"""The exact-model gate refuses before transport and records its decision first."""
import hashlib
import importlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1]/'mcp/memory'))


class NativeModelGuardTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('hearth2.native_model_guard'),
                             'Hearth exact-model pre-thread guard is not implemented')
        self.guard = importlib.import_module('hearth2.native_model_guard')
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.binary = Path(self.tmp.name)/'native'
        self.events = []
        self.catalog(['gpt-6.1-sol', 'other-catalog-model'])
        self.models = {'data': [{'id': x, 'model': x} for x in ['other-catalog-model','gpt-6.1-sol']],
                       'nextCursor': None}

    def catalog(self, slugs):
        raw = json.dumps({'models':[{'slug':s} for s in slugs]},indent=2).encode()
        self.binary.write_bytes(b'fixture executable prefix'+raw+b'\x00tail')
        self.binary_hash = hashlib.sha256(self.binary.read_bytes()).hexdigest()
        self.catalog_hash = hashlib.sha256(raw).hexdigest()

    def record(self, decision):
        self.events.append(('decision', dict(decision))); return True

    def start(self, request):
        self.events.append(('thread/start', dict(request)))
        return {'model':request['model'],'id':'fixture-thread'}

    def invoke(self, model='gpt-6.1-sol', request_changes=None, **changes):
        fields = dict(mounted_binary=self.binary, expected_binary_sha256=self.binary_hash,
            expected_catalog_sha256=self.catalog_hash, model_list=self.models,
            record_decision=self.record, thread_start=self.start)
        fields.update(changes)
        request = {'model':model,'cwd':'/scratch','approvalPolicy':'never',
                   'sandbox':'read-only','ephemeral':True}
        request.update(request_changes or {})
        return self.guard.start_codex_thread(request, **fields)

    def refused(self, reason, model='gpt-6.1-sol', **changes):
        with self.assertRaises(self.guard.ModelSelectionRefused) as error:
            self.invoke(model, **changes)
        self.assertEqual(error.exception.decision['reason'],reason)
        self.assertEqual([e[0] for e in self.events],['decision'])
        self.assertEqual(self.events[0][1]['outcome'],'refused')
        self.assertEqual(self.events[0][1]['failure_class'],'model_selection')

    def test_exact_model_in_both_catalogs_records_before_one_unchanged_request(self):
        result = self.invoke()
        self.assertEqual(result['model'],'gpt-6.1-sol')
        self.assertEqual([e[0] for e in self.events],['decision','thread/start'])
        self.assertEqual(self.events[0][1]['outcome'],'allowed')
        self.assertEqual(self.events[1][1],{'model':'gpt-6.1-sol','cwd':'/scratch',
            'approvalPolicy':'never','sandbox':'read-only','ephemeral':True})

    def test_provider_config_instruction_and_other_extra_keys_are_audited_refusals(self):
        for key,value in [('modelProvider','different-provider'),('modelProvider','openai'),
                          ('config',{'model_provider':'different-provider'}),
                          ('config',{}),('baseInstructions','custom instructions'),
                          ('developerInstructions','custom instructions'),
                          ('serviceTier','priority'),('unknownFutureField',True)]:
            with self.subTest(key=key,value=value):
                self.events=[]
                self.refused('request_fields_not_allowed',request_changes={key:value})

    def test_nonfixed_request_values_and_boolean_alias_are_audited_refusals(self):
        for key,value in [('cwd','/'),('approvalPolicy','on-request'),
                          ('sandbox','danger-full-access'),('ephemeral',False),
                          ('ephemeral',1)]:
            with self.subTest(key=key,value=value):
                self.events=[]
                self.refused('request_fields_not_allowed',request_changes={key:value})

    def test_missing_request_field_is_refused_instead_of_using_native_defaults(self):
        with self.assertRaises(self.guard.ModelSelectionRefused) as error:
            self.guard.start_codex_thread({'model':'gpt-6.1-sol'},
                mounted_binary=self.binary,expected_binary_sha256=self.binary_hash,
                expected_catalog_sha256=self.catalog_hash,model_list=self.models,
                record_decision=self.record,thread_start=self.start)
        self.assertEqual(error.exception.decision['reason'],'request_fields_not_allowed')
        self.assertEqual([e[0] for e in self.events],['decision'])

    def test_unsupported_model_is_recorded_and_never_reaches_transport(self):
        self.refused('model_not_allowed','hearth2-unsupported-model-negative-control')

    def test_another_advertised_model_is_not_an_additional_allowed_model(self):
        self.refused('model_not_allowed','other-catalog-model')

    def test_missing_exact_model_in_mounted_catalog_refuses(self):
        self.catalog(['other-catalog-model'])
        self.refused('allowed_model_missing_from_binary')

    def test_missing_exact_model_in_client_list_refuses(self):
        self.models['data'] = [{'model':'other-catalog-model'}]
        self.refused('allowed_model_missing_from_client')

    def test_changed_mounted_binary_refuses(self):
        self.binary.write_bytes(self.binary.read_bytes()+b'changed')
        self.refused('binary_pin_mismatch')

    def test_wrong_embedded_catalog_pin_refuses(self):
        self.refused('catalog_pin_mismatch',expected_catalog_sha256='0'*64)

    def test_duplicate_mounted_identity_is_invalid_not_set_deduplicated(self):
        self.catalog(['gpt-6.1-sol','gpt-6.1-sol'])
        self.refused('mounted_catalog_invalid')

    def test_partial_duplicate_or_malformed_client_catalog_refuses(self):
        for data in [None, {'data':[],'nextCursor':'more'},
                     {'data':[{'model':'gpt-6.1-sol'},{'model':'gpt-6.1-sol'}]},
                     {'data':[{'model':'gpt-6.1-sol','id':'different'}]},
                     {'data':[{'model':['gpt-6.1-sol']}]}]:
            with self.subTest(data=data):
                self.events=[]
                self.refused('client_catalog_invalid',model_list=data)

    def test_symlink_binary_and_missing_binary_refuse(self):
        link=Path(self.tmp.name)/'link'; link.symlink_to(self.binary)
        self.refused('binary_unavailable',mounted_binary=link)
        self.events=[]; self.binary.unlink(); self.refused('binary_unavailable')

    def test_audit_error_or_unacknowledged_audit_never_starts_native_thread(self):
        def unavailable(d): raise OSError('audit unavailable')
        for record, exception in [(unavailable,OSError),(lambda d:None,self.guard.ModelAuditUnavailable)]:
            with self.subTest(record=record), self.assertRaises(exception):
                self.invoke(record_decision=record)
        self.assertEqual(self.events,[])

    def test_transport_error_is_not_reclassified_as_model_refusal_or_retried(self):
        original=RuntimeError('synthetic downstream transport/runtime error')
        calls=[]
        def failed(request): calls.append(request); raise original
        with self.assertRaises(RuntimeError) as error:
            self.invoke(thread_start=failed)
        self.assertIs(error.exception,original)
        self.assertEqual(len(calls),1)
        self.assertEqual(self.events[0][1]['outcome'],'allowed')
        self.assertNotEqual(self.events[0][1]['failure_class'],'model_selection')

    def test_decision_callback_cannot_change_model_selection(self):
        def record(decision):
            self.events.append(('decision',dict(decision)))
            decision['outcome']='allowed';decision['requested_model']='gpt-6.1-sol'
            return True
        self.refused('model_not_allowed','not-approved',record_decision=record)

    def test_unexpected_checker_error_is_recorded_as_guard_error_before_transport(self):
        with patch.object(self.guard,'_check',side_effect=RuntimeError('untrusted detail')):
            with self.assertRaises(self.guard.ModelSelectionRefused) as error:
                self.invoke()
        self.assertEqual(error.exception.decision['reason'],'guard_error')
        self.assertEqual([e[0] for e in self.events],['decision'])
        self.assertEqual(self.events[0][1]['failure_class'],'guard_error')
        self.assertNotIn('untrusted detail',json.dumps(self.events))


if __name__ == '__main__': unittest.main()
