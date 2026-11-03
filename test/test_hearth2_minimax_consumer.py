import dataclasses
import importlib
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1] / 'mcp/memory'))
from hearth2.store import RecordError


CORE = 'ab278b848d10c3b8721fc00f76512994f39db9eba6691492b74c2135afa2703b'


def encoded(value):
    return json.dumps(value, ensure_ascii=True).encode()


class MiniMaxConsumerTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('hearth2.minimax_consumer'), 'MiniMax parser missing')
        self.module = importlib.import_module('hearth2.minimax_consumer')
        self.parser = self.module.MiniMaxConsumerParser('0.4.1', CORE)

    def test_exact_version_and_reviewed_public_source_required(self):
        for version, digest in [('0.4.2', CORE), ('0.4.1', 'a'*64), (True, CORE)]:
            with self.assertRaises(RecordError):
                self.module.MiniMaxConsumerParser(version, digest)

    def test_all_auth_providers_and_unknown_records_are_counted(self):
        result = self.parser.auth_json(encoded({
            'minimax': {'type': 'api_key', 'key': 'FAKE-ONE'},
            'other': {'type': 'api_key', 'key': '${FAKE_ENV}'},
            'helper': {'type': 'api_key', 'key': '!do-not-execute'},
            'oauth': {'type': 'oauth', 'access': 'FAKE-OAUTH'},
            'future': {'type': 'api_key', 'key': 'FAKE-TWO', 'extra': True},
            'invalid': None,
        }))
        self.assertEqual((result.literal_fields, result.environment_fields,
                          result.command_fields, result.unknown_records), (1, 1, 1, 3))

    def test_native_escapes_and_malformed_templates_are_literal(self):
        result = self.parser.headers_json(encoded({
            'X-One': '$$HOME $!cmd ${BAD-NAME} ${unclosed $9 $',
            'X-Two': ' !literal', 'X-Three': 'plain',
        }))
        self.assertEqual((result.literal_fields, result.environment_fields,
                          result.command_fields, result.environment_references), (3, 0, 0, 0))

    def test_mixed_templates_count_repeated_and_lowercase_references(self):
        result = self.parser.headers_json(encoded({'Authorization': 'Bearer $KEY-${low}_$KEY'}))
        self.assertEqual((result.environment_fields, result.environment_references), (1, 3))
        result = self.parser.headers_json(encoded({'X': '$$KEY$!$KEY'}))
        self.assertEqual((result.environment_fields, result.environment_references), (1, 1))

    def test_commands_are_never_executed_even_if_they_contain_environment(self):
        with patch('subprocess.run', side_effect=AssertionError('execution forbidden')), \
                patch('subprocess.Popen', side_effect=AssertionError('execution forbidden')), \
                patch('os.system', side_effect=AssertionError('execution forbidden')), \
                patch('os.getenv', side_effect=AssertionError('ambient lookup forbidden')):
            result = self.parser.headers_json(encoded({'X': '!exit $KEY'}))
            self.parser.auth_json(encoded({'p': {'type': 'api_key', 'key': '$AMBIENT'}}))
        self.assertEqual((result.command_fields, result.environment_fields), (1, 0))

    def test_runtime_override_and_environment_values_are_not_expanded(self):
        for method in [self.parser.runtime_overrides_json, self.parser.environment_json]:
            result = method(encoded({'KEY': '!not-a-helper', 'OTHER': '$NOT_EXPANDED', 'EMPTY': ''}))
            self.assertEqual((result.literal_fields, result.empty_fields,
                              result.command_fields, result.environment_fields), (2, 1, 0, 0))

    def test_empty_auth_key_remains_explicit(self):
        result = self.parser.auth_json(encoded({'minimax': {'type': 'api_key', 'key': ''}}))
        self.assertEqual(result.empty_fields, 1)

    def test_unknown_auth_shapes_never_become_supported(self):
        for record in [[], 'FAKE', {}, {'type': 'api_key', 'key': None},
                       {'type': 'api_key', 'key': 7}, {'type': 'oauth'},
                       {'type': 'api_key', 'key': 'FAKE', 'headers': {}}]:
            self.assertEqual(self.parser.auth_json(encoded({'minimax': record})).unknown_records, 1)

    def test_no_values_names_secret_digests_or_success_authority_in_output(self):
        raw = encoded({'PRIVATE-PROVIDER': {'type': 'api_key', 'key': 'FAKE-SENSITIVE'}})
        result = self.parser.auth_json(raw)
        text = repr(result) + str(dataclasses.asdict(result))
        for forbidden in ['PRIVATE-PROVIDER', 'FAKE-SENSITIVE', 'complete', 'credential_entries',
                          'observed_at', 'sha256', 'states']:
            self.assertNotIn(forbidden, text)
        self.assertNotIn('references', dataclasses.asdict(result))
        with self.assertRaises(dataclasses.FrozenInstanceError): result.literal_fields = 0
        self.assertFalse(hasattr(self.parser, 'observe'))
        self.assertFalse(hasattr(self.parser, 'scan'))

    def test_duplicate_keys_at_all_levels_and_nonstandard_json_refuse(self):
        for raw in [b'{"minimax":{},"minimax":{}}',
                    b'{"minimax":{"type":"api_key","key":"FAKE","key":"OTHER"}}',
                    b'{"minimax":{"future":{"a":1,"a":2}}}',
                    b'{"minimax":NaN}', b'{"minimax":Infinity}', b'{} trailing', b'\xff']:
            with self.assertRaises(RecordError): self.parser.auth_json(raw)

    def test_bad_map_shapes_and_types_refuse_without_echo(self):
        for method in [self.parser.headers_json, self.parser.runtime_overrides_json,
                       self.parser.environment_json]:
            for value in [[], None, True, {'SECRET-KEY': None}, {'X': ['FAKE']}, {'X': 1}]:
                with self.assertRaises(RecordError) as error: method(encoded(value))
                self.assertEqual(str(error.exception), 'unsupported MiniMax consumer input')
                self.assertIsNone(error.exception.__cause__)
                self.assertIsNone(error.exception.__context__)

    def test_depth_node_byte_string_and_name_bounds(self):
        invalid = [b' '*65537, encoded({'p': 'x'*8193}), encoded({'k'*257: {}}),
                   encoded({'p': [[[[[[[[{}]]]]]]]]}),
                   encoded({str(i): {'type': 'api_key', 'key': 'x'} for i in range(500)})]
        for raw in invalid:
            with self.assertRaises(RecordError): self.parser.auth_json(raw)

    def test_unicode_scalar_validation_and_header_env_names(self):
        for raw in [b'{"p":{"key":"\\ud800"}}', b'{"\\ud800":{}}']:
            with self.assertRaises(RecordError): self.parser.auth_json(raw)
        for name in ['bad name', 'bad\nname', 'nonascii-\u00e9']:
            with self.assertRaises(RecordError): self.parser.headers_json(encoded({name: 'FAKE'}))
        with self.assertRaises(RecordError): self.parser.environment_json(encoded({'BAD-NAME': 'FAKE'}))
        self.assertEqual(self.parser.headers_json(encoded({'X-Test': 'FAKE-\u00e9'})).literal_fields, 1)

    def test_missing_source_is_not_silently_an_empty_map(self):
        for raw in [None, '', '{}', bytearray(b'{}'), b'']:
            with self.assertRaises(RecordError): self.parser.auth_json(raw)
        self.assertEqual(self.parser.auth_json(b'{}').unknown_records, 0)
        # Empty syntax result is still not complete inventory/absence evidence.
        self.assertNotIn('complete', dataclasses.asdict(self.parser.auth_json(b'{}')))

    def test_structural_characters_inside_strings_do_not_change_depth(self):
        result = self.parser.headers_json(encoded({'X': '[{\\"'*40 + 'FAKE'}))
        self.assertEqual(result.literal_fields, 1)

    def test_native_template_edge_cases(self):
        for value, fields, refs in [('$', 0, 0), ('$$NAME', 0, 0), ('$!NAME', 0, 0),
                                  ('$9', 0, 0), ('${}', 0, 0), ('${A-B}', 0, 0),
                                  ('${A_$B}', 0, 0), ('${A', 0, 0),
                                  ('${A$B', 1, 1), ('$$$A', 1, 1),
                                  ('$a0_ $Z ${_foo}', 1, 3)]:
            with self.subTest(value=value):
                result = self.parser.headers_json(encoded({'X': value}))
                self.assertEqual((result.environment_fields, result.environment_references), (fields, refs))

    def test_decode_errors_never_retain_secret_context(self):
        for raw in [b'{"FAKE-SECRET":', b'{"X":"\\ud800"}', b'{"X":1.2}', b'{"X":1e999}']:
            with self.assertRaises(RecordError) as error: self.parser.headers_json(raw)
            self.assertIsNone(error.exception.__context__)
            self.assertIsNone(error.exception.__cause__)
            self.assertNotIn('FAKE-SECRET', repr(error.exception))


if __name__ == '__main__': unittest.main()
