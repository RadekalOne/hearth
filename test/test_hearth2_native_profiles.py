"""Direct profiles are root-supplied configuration, with no raw credentials."""
import importlib
import json
from pathlib import Path
import sys
import tomllib
import unittest

sys.path.insert(0,str(Path(__file__).parents[1]/'mcp/memory'))
from hearth2.store import RecordError


class NativeProfileTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('hearth2.native_profiles'),
                             'direct native profiles are not implemented')
        self.profiles=importlib.import_module('hearth2.native_profiles')

    def test_codex_profile_preserves_model_and_has_only_fixed_read_broker(self):
        config=tomllib.loads(self.profiles.codex_config(model='gpt-6.1-sol'))
        self.assertEqual(config['model'],'gpt-6.1-sol')
        self.assertEqual(config['forced_login_method'],'chatgpt')
        self.assertEqual(set(config['mcp_servers']),{'hearth'})
        server=config['mcp_servers']['hearth']
        self.assertEqual(server['url'],'http://hearth-broker:8010/mcp')
        self.assertEqual(server['bearer_token_env_var'],'HEARTH_BROKER_CAPABILITY')
        self.assertEqual(server['enabled_tools'],['memory_search','memory_get'])
        self.assertTrue(server['required'])
        self.assertNotIn('model_providers',config)
        self.assertFalse(config['features']['shell_tool'])
        self.assertFalse(config['features']['shell_snapshot'])
        self.assertEqual(config['shell_environment_policy']['inherit'],'none')
        self.assertEqual(config['shell_environment_policy']['exclude'],['HEARTH_*'])
        self.assertNotIn('filters',config['shell_environment_policy'])

    def test_direct_models_cannot_inject_flags_config_or_provider_routes(self):
        for model in ['--dangerously-skip-permissions','gpt\n[model_providers.evil]',
                      'gpt model','x\x00','https://untrusted.example/model','',None]:
            with self.subTest(model=model),self.assertRaises(RecordError):
                self.profiles.codex_config(model=model)
            with self.assertRaises(RecordError):
                self.profiles.claude_arguments(model=model,session_id='11111111-1111-4111-8111-111111111111',context='fixed rules')

    def test_claude_direct_profile_explicitly_configures_hearth_not_old_sdk(self):
        args=self.profiles.claude_arguments(model='claude-opus-fixture',
            session_id='11111111-1111-4111-8111-111111111111',context='approved rules')
        config=json.loads(args[args.index('--mcp-config')+1])
        self.assertEqual(set(config['mcpServers']),{'hearth'})
        server=config['mcpServers']['hearth']
        self.assertEqual(server['type'],'http')
        self.assertEqual(server['url'],'http://hearth-broker:8010/mcp')
        self.assertEqual(server['headers']['Authorization'],'Bearer ${HEARTH_BROKER_CAPABILITY}')
        self.assertEqual(args[args.index('--model')+1],'claude-opus-fixture')
        self.assertNotIn('--dangerously-skip-permissions',args)
        self.assertNotIn('--fallback-model',args)
        self.assertEqual(args[args.index('--allowedTools')+1],
                         'mcp__hearth__memory_search,mcp__hearth__memory_get')

    def test_fixture_route_swap_aborts_on_missing_or_duplicate_settings(self):
        path=Path(__file__).parent/'fixtures/hearth2_direct_mcp_probe.py'
        spec=importlib.util.spec_from_file_location('hearth2_direct_mcp_fixture',path)
        fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)
        self.assertTrue(hasattr(fixture,'codex_fixture_config'),'fixture swap guard missing')
        config=self.profiles.codex_config(model='gpt-6.1-sol')
        changed=tomllib.loads(fixture.codex_fixture_config(config))
        self.assertEqual(changed['model_provider'],'hearth-fixture')
        self.assertEqual(changed['forced_login_method'],'api')
        self.assertFalse(changed['features']['shell_tool'])
        for line in ['forced_login_method = "chatgpt"','model_provider = "openai"']:
            for malformed in [config.replace(line,''),config+'\n'+line+'\n']:
                with self.subTest(line=line),self.assertRaises(ValueError):
                    fixture.codex_fixture_config(malformed)

    def test_invalid_session_or_context_is_rejected_before_native_start(self):
        fields={'model':'sonnet','session_id':'11111111-1111-4111-8111-111111111111','context':'rules'}
        for changes in [{'session_id':'not-a-session'},{'session_id':'11111111111141118111111111111111'},
                        {'context':''},{'context':'x\x00'},{'context':'x'*32769}]:
            with self.subTest(changes=changes),self.assertRaises(RecordError):
                self.profiles.claude_arguments(**{**fields,**changes})


if __name__=='__main__':unittest.main()
