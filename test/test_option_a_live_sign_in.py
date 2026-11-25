import base64
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'ops/hearth2'))
from option_a_live_sign_in import (
    CURL, REPLY_LIMIT, USER_AGENT, OpenAIAuthTransport, SignInReceipt, WorkspaceBinding,
    login_command, login_status_command,
)
from option_a_sign_in import AUTH_HOST, CALLBACK, DENIED, EXCHANGE, FAILED, FORM, JSON, POLL, USERCODE, SignInRoute
from urllib.parse import urlencode


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
        self.assertEqual(command[command.index('--user-agent') + 1], USER_AGENT)
        self.assertEqual(command[command.index('--max-filesize') + 1], str(REPLY_LIMIT))
        self.assertEqual(command[command.index('--data-binary') + 1], '@-')
        self.assertEqual(run.call_args.kwargs['input'], b'{}')
        self.assertEqual(run.call_args.kwargs['env'], {'PATH':'/usr/bin:/bin'})
        self.assertEqual(route.receipt.snapshot()['http_status_counts'][USERCODE], {'200':1})

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
        receipt = route.receipt.snapshot()
        self.assertEqual(receipt['http_status_counts'][USERCODE], {'302':1,'200':2})
        self.assertEqual(receipt['transport_failures'][USERCODE], 4)
        self.assertNotIn('mock-body', json.dumps(receipt))

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


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.workspace = '00000000-0000-4000-8000-000000000001'
        self.email = 'fixture@example.test'

    def exchange(self, claims):
        receipt = SignInReceipt()
        binding = WorkspaceBinding(self.workspace, self.email, receipt)
        header = 'eyJhbGciOiJSUzI1NiJ9'
        payload = base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip('=')
        token = f'{header}.{payload}.Zml4dHVyZQ'
        reply = json.dumps({'id_token':token,'access_token':'fake-access','refresh_token':'fake-refresh'}).encode()
        responses = {
            USERCODE: b'{"device_auth_id":"synthetic","user_code":"FAKE-CODE"}',
            POLL: b'{"authorization_code":"fake-code","code_verifier":"fake-verifier"}',
            EXCHANGE: reply,
        }
        route = SignInRoute('fixture', lambda path, *_: (200, responses[path]),
                            accept_tokens=binding.check)
        self.assertEqual(route.request('POST', AUTH_HOST, USERCODE, JSON, b'{"client_id":"fixture"}')[0], 200)
        self.assertEqual(route.request('POST', AUTH_HOST, POLL, JSON,
                                        b'{"device_auth_id":"synthetic","user_code":"FAKE-CODE"}')[0], 200)
        form = urlencode({'client_id':'fixture','grant_type':'authorization_code','code':'fake-code',
                          'code_verifier':'fake-verifier','redirect_uri':CALLBACK}).encode()
        response = route.request('POST', AUTH_HOST, EXCHANGE, FORM, form)
        self.assertEqual(route.request('POST', AUTH_HOST, EXCHANGE, FORM, form), DENIED)
        self.assertNotIn(self.email, json.dumps(receipt.snapshot()))
        self.assertNotIn(self.workspace, json.dumps(receipt.snapshot()))
        self.assertNotIn(token, json.dumps(receipt.snapshot()))
        return response, receipt.snapshot(), reply

    def test_matching_binding_releases_reply_with_redacted_receipt(self):
        claims = {'email':self.email, 'https://api.openai.com/auth':
                  {'chatgpt_account_id':self.workspace,'chatgpt_plan_type':'business'}}
        response, receipt, reply = self.exchange(claims)
        self.assertEqual(response, (200, reply))
        self.assertEqual(receipt['workspace_binding'], 'matched')

    def test_wrong_or_missing_claims_do_not_release_reply(self):
        for email, workspace, plan in [(self.email, 'wrong', 'business'),
                                       (self.email, self.workspace, 'plus'),
                                       ('other@example.test', self.workspace, 'business'),
                                       (None, self.workspace, 'business')]:
            response, receipt, _ = self.exchange({'email':email,'https://api.openai.com/auth':
                                                 {'chatgpt_account_id':workspace,'chatgpt_plan_type':plan}})
            self.assertEqual(response, FAILED)
            self.assertEqual(receipt['workspace_binding'], 'mismatch')

    def test_unparseable_id_token_is_redacted_and_refused(self):
        receipt = SignInReceipt()
        binding = WorkspaceBinding(self.workspace, self.email, receipt)
        for response in [{}, {'id_token':'invalid'}, {'id_token':'a.a.a'}]:
            self.assertFalse(binding.check(response))
            self.assertEqual(receipt.snapshot()['workspace_binding'], 'mismatch')
