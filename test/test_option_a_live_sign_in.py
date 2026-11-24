from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'ops/hearth2'))
from option_a_live_sign_in import CURL, REPLY_LIMIT, OpenAIAuthTransport, login_command, login_status_command
from option_a_sign_in import DENIED, FAILED, JSON, USERCODE


class TransportTests(unittest.TestCase):
    def test_closed_by_default_before_subprocess(self):
        with patch('option_a_live_sign_in.subprocess.run') as run:
            with self.assertRaisesRegex(ValueError, 'authorization required'):
                OpenAIAuthTransport()
            run.assert_not_called()

    @patch('option_a_live_sign_in._require_trial_root')
    @patch('option_a_live_sign_in.subprocess.run')
    def test_fixed_tls_origin_and_bounded_stdin_transport(self, run, trial_root):
        run.side_effect = [subprocess.CompletedProcess([], 0, b'curl 8.5.0 (linux)\n'),
                           subprocess.CompletedProcess([], 0, b'{}\n200')]
        route = OpenAIAuthTransport(authorized=True)
        self.assertEqual(route('/backend-api/codex/responses', JSON, b'{}'), DENIED)
        self.assertEqual(route(USERCODE + '?x=1', JSON, b'{}'), DENIED)
        self.assertEqual(route(USERCODE, JSON, b'{}'), (200, b'{}'))
        self.assertEqual(run.call_count, 2)
        trial_root.assert_called_once()
        command = run.call_args.args[0]
        self.assertEqual(command[:2], [CURL, '--disable'])
        self.assertEqual(command[-1], 'https://auth.openai.com' + USERCODE)
        self.assertNotIn('--location', command)
        self.assertEqual(command[command.index('--noproxy') + 1], '*')
        self.assertEqual(command[command.index('--proxy') + 1], '')
        self.assertEqual(command[command.index('--max-filesize') + 1], str(REPLY_LIMIT))
        self.assertEqual(command[command.index('--data-binary') + 1], '@-')
        self.assertEqual(run.call_args.kwargs['input'], b'{}')
        self.assertEqual(run.call_args.kwargs['env'], {'PATH':'/usr/bin:/bin'})

    @patch('option_a_live_sign_in._require_trial_root')
    @patch('option_a_live_sign_in.subprocess.run')
    def test_redirect_error_unbounded_and_timeout_all_fail_closed(self, run, _trial_root):
        run.return_value = subprocess.CompletedProcess([], 0, b'curl 8.5.0 (linux)\n')
        route = OpenAIAuthTransport(authorized=True)
        for response in [subprocess.CompletedProcess([], 0, b'mock-body\n302'),
                         subprocess.CompletedProcess([], 1, b'mock-body\n200'),
                         subprocess.CompletedProcess([], 0, b'x' * (REPLY_LIMIT + 1) + b'\n200')]:
            with self.subTest(returncode=response.returncode, bytes=len(response.stdout)):
                run.return_value = response
                self.assertEqual(route(USERCODE, JSON, b'{}'), FAILED)
        run.side_effect = subprocess.TimeoutExpired(['fixture'], 10)
        self.assertEqual(route(USERCODE, JSON, b'{}'), FAILED)

    def test_login_and_status_lock_workspace_and_provider_mode(self):
        workspace = '00000000-0000-4000-8000-000000000001'
        launch = login_command(workspace)
        self.assertEqual(launch[-2:], ['login', '--device-auth'])
        self.assertIn('forced_chatgpt_workspace_id="' + workspace + '"', launch)
        self.assertIn('forced_login_method="chatgpt"', launch)
        self.assertEqual(login_status_command(workspace)[:-2], launch[:-2])
        self.assertEqual(login_status_command(workspace)[-2:], ['login', 'status'])
        for invalid in ['', None, '00000000-0000-0000-0000-000000000000', 'unknown']:
            with self.subTest(workspace=invalid), self.assertRaises(ValueError):
                login_command(invalid)
