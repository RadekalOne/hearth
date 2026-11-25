import json
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock
from urllib.parse import urlencode

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'ops/hearth2'))
from option_a_sign_in import AUTH_HOST, EXCHANGE, POLL, USERCODE, SignInRoute


class SignInTests(unittest.TestCase):
    def setUp(self):
        self.exchange = Mock(side_effect=[
            (200, b'{"device_auth_id":"device","user_code":"CODE","interval":"1"}'),
            (403, b'{}'),
            (200, b'{"authorization_code":"code","code_verifier":"verifier","code_challenge":"challenge"}'),
            (200, b'{"id_token":"fake-id","access_token":"fake-access","refresh_token":"fake-refresh"}'),
        ])
        self.route = SignInRoute('fixture-client', self.exchange)

    def request(self, path, fields, *, host=AUTH_HOST, method='POST', form=False):
        body = urlencode(fields).encode() if form else json.dumps(fields).encode()
        kind = 'application/x-www-form-urlencoded' if form else 'application/json'
        return self.route.request(method, host, path, kind, body)

    def test_only_bound_device_code_flow_reaches_upstream(self):
        self.assertEqual(self.request(USERCODE, {'client_id': 'fixture-client'})[0], 200)
        self.assertEqual(self.request(POLL, {'device_auth_id':'other','user_code':'CODE'})[0], 403)
        active = {'device_auth_id':'device','user_code':'CODE'}
        self.assertEqual(self.request(POLL, active)[0], 403)
        self.assertEqual(self.request(POLL, active)[0], 200)
        exchange = {'grant_type':'authorization_code','client_id':'fixture-client','code':'code',
                    'code_verifier':'verifier','redirect_uri':'https://auth.openai.com/deviceauth/callback'}
        self.assertEqual(self.request(EXCHANGE, {**exchange, 'code_verifier':'wrong'}, form=True)[0], 403)
        self.assertEqual(self.request(EXCHANGE, {**exchange, 'grant_type':'refresh_token'}, form=True)[0], 403)
        self.assertEqual(self.request(EXCHANGE, {**exchange, 'grant_type':'urn:ietf:params:oauth:grant-type:token-exchange'}, form=True)[0], 403)
        self.assertEqual(self.request(EXCHANGE, exchange, form=True)[0], 200)
        self.assertEqual(self.request(EXCHANGE, exchange, form=True)[0], 403)
        self.assertEqual([args[0] for args, _ in self.exchange.call_args_list],
                         [USERCODE, POLL, POLL, EXCHANGE])

    def test_denies_same_host_model_oauth_bypasses_and_alternate_host(self):
        for args in [
            ('POST', AUTH_HOST, '/v1/responses', 'application/json', b'{}'),
            ('POST', AUTH_HOST, '/backend-api/codex/responses', 'application/json', b'{}'),
            ('POST', 'api.openai.com', USERCODE, 'application/json', b'{"client_id":"fixture-client"}'),
            ('CONNECT', AUTH_HOST, 'auth.openai.com:443', '', b''),
            ('POST', AUTH_HOST, 'https://auth.openai.com' + USERCODE, 'application/json', b'{}'),
            ('POST', AUTH_HOST, USERCODE + '?redirect=evil.test', 'application/json', b'{}'),
            ('POST', AUTH_HOST, USERCODE, 'application/json', b'{"client_id":"fixture-client","client_id":"fixture-client"}'),
            ('POST', AUTH_HOST, EXCHANGE, 'application/x-www-form-urlencoded', b'grant_type=refresh_token'),
            ('POST', AUTH_HOST, EXCHANGE, 'application/x-www-form-urlencoded', b'grant_type=urn:ietf:params:oauth:grant-type:token-exchange&requested_token=openai-api-key'),
        ]:
            with self.subTest(args=args):
                self.assertEqual(self.route.request(*args)[0], 403)
        self.exchange.assert_not_called()

    def test_redirect_fails_closed(self):
        self.exchange.side_effect = None
        self.exchange.return_value = (302, b'{"location":"https://untrusted.test"}')
        self.assertEqual(self.request(USERCODE, {'client_id':'fixture-client'})[0], 502)
        self.assertEqual(self.request(USERCODE, {'client_id':'fixture-client'})[0], 403)
        self.exchange.assert_called_once()

    def test_canonical_json_reaches_transport(self):
        self.exchange.side_effect = None
        self.exchange.return_value = (200, b'{"device_auth_id":"device","user_code":"CODE"}')
        raw = b' { "client_id": "fixture-client" } '
        self.assertEqual(self.route.request('POST', AUTH_HOST, USERCODE, 'application/json', raw)[0], 200)
        self.exchange.assert_called_once_with(USERCODE, 'application/json', b'{"client_id":"fixture-client"}')

    def test_operator_close_and_expiry_prevent_forwarding(self):
        self.route.close()
        self.assertEqual(self.request(USERCODE, {'client_id':'fixture-client'})[0], 403)
        self.exchange.assert_not_called()
        clock = Mock(return_value=10)
        self.exchange.side_effect = [(200, b'{"device_auth_id":"device","user_code":"CODE"}')]
        expired = SignInRoute('fixture-client', self.exchange, monotonic=clock)
        self.assertEqual(expired.request('POST', AUTH_HOST, USERCODE, 'application/json',
                                         b'{"client_id":"fixture-client"}')[0], 200)
        clock.return_value = 70
        self.assertEqual(expired.request('POST', AUTH_HOST, POLL, 'application/json',
                                         b'{"device_auth_id":"device","user_code":"CODE"}')[0], 403)
        self.exchange.assert_called_once()

    def test_long_window_starts_at_first_valid_request_and_expires_at_boundary(self):
        clock = Mock(return_value=100)
        self.exchange.side_effect = [(200, b'{"device_auth_id":"device","user_code":"CODE"}'),
                                     (403, b'{}')]
        self.route = SignInRoute('fixture-client', self.exchange, monotonic=clock,
                                 window_seconds=480, max_polls=180)
        clock.return_value = 1200
        self.assertEqual(self.request(USERCODE, {'client_id':'wrong'})[0], 403)
        clock.return_value = 1300
        self.assertEqual(self.request(USERCODE, {'client_id':'fixture-client'})[0], 200)
        fields = {'device_auth_id':'device','user_code':'CODE'}
        clock.return_value = 1779
        self.assertEqual(self.request(POLL, fields)[0], 403)  # Mock's pending response
        clock.return_value = 1780
        self.assertEqual(self.request(POLL, fields)[0], 403)  # Refused before transport
        self.assertEqual(self.exchange.call_count, 2)

    def test_poll_cap_closes_before_next_upstream_request(self):
        self.exchange.side_effect = [(200, b'{"device_auth_id":"device","user_code":"CODE"}'),
                                     (403, b'{}'), (404, b'{}')]
        self.route = SignInRoute('fixture-client', self.exchange, window_seconds=480, max_polls=2)
        self.assertEqual(self.request(USERCODE, {'client_id':'fixture-client'})[0], 200)
        fields = {'device_auth_id':'device','user_code':'CODE'}
        self.assertEqual(self.request(POLL, fields)[0], 403)
        self.assertEqual(self.request(POLL, fields)[0], 404)
        self.assertEqual(self.request(POLL, fields)[0], 403)
        self.assertEqual(self.exchange.call_count, 3)

    def test_idle_window_starts_at_activation_and_ignores_invalid_request(self):
        clock = Mock(return_value=10)
        self.route = SignInRoute('fixture-client', self.exchange, monotonic=clock,
                                 idle_seconds=30, window_seconds=480, max_polls=180)
        clock.return_value = 39
        self.assertEqual(self.request(USERCODE, {'client_id':'invalid'})[0], 403)
        self.assertFalse(self.route.expire_idle())
        clock.return_value = 40
        self.assertTrue(self.route.expire_idle())
        self.assertEqual(self.request(USERCODE, {'client_id':'fixture-client'})[0], 403)
        self.exchange.assert_not_called()

    def test_first_code_switches_from_idle_to_sign_in_window(self):
        clock = Mock(return_value=10)
        self.route = SignInRoute('fixture-client', self.exchange, monotonic=clock,
                                 idle_seconds=30, window_seconds=480, max_polls=180)
        clock.return_value = 39
        self.assertEqual(self.request(USERCODE, {'client_id':'fixture-client'})[0], 200)
        clock.return_value = 40
        self.assertFalse(self.route.expire_idle())
