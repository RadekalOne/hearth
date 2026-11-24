import sys
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'ops/hearth2'))
from option_a_setup import AccountBinding, SetupRefused, account_status, bounded_enrollment


class AccountStatusTests(unittest.TestCase):
    def setUp(self):
        self.expected = AccountBinding('fixture-workspace', 'trial@example.test', 'Business Premium', 'chatgpt', 'openai', 'fixture-session')
        self.call = Mock(return_value={'account': {'type': 'chatgpt', 'email': 'trial@example.test',
                                                  'planType': 'business'}, 'requiresOpenaiAuth': True})

    def test_reports_native_status_and_controller_attestation_separately(self):
        result = account_status(self.call, 'account/read', {'refreshToken': False},
                                expected=self.expected, attested=self.expected)
        self.call.assert_called_once_with('account/read', {'refreshToken': False})
        self.assertEqual(result, {
            'auth_method': 'chatgpt',
            'email_matched': True,
            'plan': 'business',
            'workspace_binding': 'controller_attested',
            'seat': 'controller_attested',
        })

    def test_rejects_other_calls_before_transport(self):
        for method, params in [('thread/start', {}), ('turn/start', {}), ('model/list', {}),
                               ('account/login/start', {}), ('account/read', {'refreshToken': True}),
                               ('account/read', {'refreshToken': False, 'provider': 'alternate'})]:
            with self.subTest(method=method, params=params), self.assertRaises(SetupRefused):
                account_status(self.call, method, params, expected=self.expected, attested=self.expected)
        self.call.assert_not_called()

    def test_wrong_or_missing_trusted_binding_is_refused_before_transport(self):
        for fake in [None, replace(self.expected, workspace_id='wrong'), replace(self.expected, workspace_id=''),
                     replace(self.expected, seat='wrong'), replace(self.expected, provider='bedrock'),
                     replace(self.expected, provider='fallback'), replace(self.expected, auth_method='apiKey'),
                     replace(self.expected, session_id='other')]:
            with self.subTest(fake=fake), self.assertRaises(SetupRefused):
                account_status(self.call, 'account/read', {'refreshToken': False},
                               expected=self.expected, attested=fake)
        self.call.assert_not_called()

    def test_invalid_expected_provider_and_seat_cannot_self_attest(self):
        for binding in [replace(self.expected, auth_method='apiKey'),
                        replace(self.expected, provider='fallback'),
                        replace(self.expected, seat='Business')]:
            with self.subTest(binding=binding), self.assertRaises(SetupRefused):
                account_status(self.call, 'account/read', {'refreshToken': False},
                               expected=binding, attested=binding)
        self.call.assert_not_called()

    def test_wrong_native_account_type_email_or_plan_is_refused(self):
        for account in [None, {'type': 'apiKey'}, {'type': 'amazonBedrock'},
                        {'type': 'chatgpt', 'email': 'other@example.test', 'planType': 'business'},
                        {'type': 'chatgpt', 'email': self.expected.email, 'planType': 'free'}]:
            self.call.return_value['account'] = account
            with self.subTest(account=account), self.assertRaises(SetupRefused):
                account_status(self.call, 'account/read', {'refreshToken': False},
                               expected=self.expected, attested=self.expected)


class EnrollmentOrderTests(unittest.TestCase):
    def test_watchdog_failure_never_starts_workload(self):
        port = Mock()
        port.create.return_value = 'a' * 64
        port.arm.side_effect = SetupRefused('watchdog unavailable')
        port.remove.return_value = True
        channel = Mock()
        with self.assertRaises(SetupRefused):
            with bounded_enrollment(port, channel):
                self.fail('unarmed enrollment yielded')
        port.start.assert_not_called()
        port.remove.assert_called_once_with('a' * 64)
        channel.close.assert_called_once()

    def test_watchdog_precedes_start_and_failure_revokes_and_cleans(self):
        port = Mock()
        cid = 'a' * 64
        port.create.return_value = cid
        port.remove.return_value = True
        port.start.side_effect = RuntimeError('fixture startup failure')
        channel = Mock()
        channel.check.return_value = True
        parent = Mock()
        parent.attach_mock(channel, 'channel')
        parent.attach_mock(port, 'port')
        with self.assertRaises(RuntimeError):
            with bounded_enrollment(port, channel):
                self.fail('failed start yielded')
        self.assertEqual([call[0] for call in parent.mock_calls],
                         ['channel.start', 'port.create', 'port.arm', 'port.start',
                          'channel.close', 'port.remove', 'port.disarm'])

    def test_unconfirmed_cleanup_keeps_watchdog_armed(self):
        port = Mock()
        port.create.return_value = 'a' * 64
        port.remove.return_value = False
        channel = Mock()
        channel.check.return_value = True
        with self.assertRaisesRegex(SetupRefused, 'cleanup_unconfirmed'):
            with bounded_enrollment(port, channel):
                pass
        channel.close.assert_called_once()
        port.disarm.assert_not_called()


if __name__ == '__main__':
    unittest.main()
