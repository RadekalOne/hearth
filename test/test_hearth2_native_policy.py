"""Fail-closed native argument policy; no providers or account credentials."""
import importlib
import json
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).parents[1] / 'mcp/memory'))
from hearth2.store import RecordError


class NativePolicyTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('hearth2.native_policy'),
                             'native policy boundary is not implemented')
        self.policy = importlib.import_module('hearth2.native_policy')
        self.model = 'claude-fixture-exact'
        self.session = '11111111-2222-4333-8444-555555555555'
        self.sdk = json.dumps({'mcpServers':{'cloudroom':{'type':'sdk','name':'cloudroom'}}})
        self.arguments = ['-p','--input-format','stream-json','--output-format','stream-json',
            '--verbose','--include-partial-messages','--replay-user-messages',
            '--dangerously-skip-permissions','--permission-prompts','none','--no-chrome',
            '--model',self.model,'--append-system-prompt','task context',
            '--disallowedTools','AskUserQuestion,EnterPlanMode,ExitPlanMode,Agent,Task,Workflow,SendMessage',
            '--mcp-config',self.sdk,'--session-id',self.session]

    def rewrite(self, arguments=None):
        return self.policy.claude_arguments(
            self.arguments if arguments is None else arguments, expected_model=self.model)

    def test_pinned_core_arguments_become_fixed_noninteractive_memory_only_surface(self):
        args = self.rewrite()
        self.assertNotIn('--dangerously-skip-permissions', args)
        self.assertNotIn('--allow-dangerously-skip-permissions', args)
        self.assertEqual(args[args.index('--permission-mode')+1], 'dontAsk')
        self.assertEqual(args[args.index('--tools')+1], '')
        self.assertIn('--strict-mcp-config', args)
        self.assertIn('--disable-slash-commands', args)
        self.assertEqual(args[args.index('--setting-sources')+1], '')
        self.assertEqual(args[args.index('--model')+1], self.model)
        self.assertEqual(args[args.index('--session-id')+1], self.session)
        self.assertIn('--settings', args)
        self.assertEqual(json.loads(args[args.index('--settings')+1]),
                         {'fastMode':False,'enableWorkflows':False})

    def test_resume_delegation_provider_and_permission_injection_are_refused(self):
        for tail in [['--resume','other'], ['--fork-session'], ['--agent','other'],
                     ['--settings','{"permissions":{"defaultMode":"bypassPermissions"}}'],
                     ['--tools','Bash'], ['--permission-mode','bypassPermissions'],
                     ['--add-dir','/'], ['--plugin-dir','/tmp/plugin'], ['--fallback-model','other']]:
            with self.subTest(tail=tail), self.assertRaises(RecordError):
                self.rewrite(self.arguments+tail)

    def test_missing_duplicate_or_changed_model_and_session_are_refused(self):
        for args in [self.arguments+['--model',self.model],
                     [x if x!=self.model else 'other' for x in self.arguments],
                     self.arguments[:-2], self.arguments+['--session-id',self.session],
                     [x if x!=self.session else '../../foreign' for x in self.arguments]]:
            with self.subTest(args=args), self.assertRaises(RecordError):
                self.rewrite(args)

    def test_foreign_mcp_and_duplicate_json_keys_are_refused(self):
        for value in ['{"mcpServers":{"external":{"command":"sh"}}}',
                      '{"mcpServers":{},"mcpServers":{"cloudroom":{"type":"sdk","name":"cloudroom"}}}']:
            args=[value if x==self.sdk else x for x in self.arguments]
            with self.subTest(value=value), self.assertRaises(RecordError):
                self.rewrite(args)

    def test_only_known_pinned_core_settings_are_accepted(self):
        safe = ['{"fastMode":false,"enableWorkflows":false}',
                '{"attribution":{"commit":"","pr":""}}']
        for value in safe:
            args=self.rewrite(self.arguments+['--settings',value])
            self.assertEqual(args[args.index('--permission-mode')+1], 'dontAsk')
        for value in ['{"env":{"ANTHROPIC_BASE_URL":"https://elsewhere.test"}}',
                      '{"fastMode":true}', '{bad', '{"apiKeyHelper":"command"}',
                      '{"fastMode":0,"enableWorkflows":0}']:
            with self.subTest(value=value), self.assertRaises(RecordError):
                self.rewrite(self.arguments+['--settings',value])


if __name__ == '__main__':
    unittest.main()
