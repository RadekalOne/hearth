"""Run only inside the disposable, network-disabled Option A TLS fixture."""
import base64
import http.client
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from pathlib import Path
import socket
import ssl
import subprocess
import tempfile
import threading
import time
from contextlib import contextmanager
from unittest.mock import patch

from option_a_sign_in import AUTH_HOST, EXCHANGE, POLL, USERCODE, SignInRoute, loopback_tls_server
from option_a_live_sign_in import (
    CLIENT_ID, UnixSignInPort, live_sign_in_socket, login_status_command, private_sign_in_socket,
)


WORKSPACE = '00000000-0000-4000-8000-000000000001'


def _fake_token():
    def segment(value):
        return base64.urlsafe_b64encode(json.dumps(value).encode()).decode().rstrip('=')
    now = int(time.time())
    return '.'.join((segment({'alg': 'none', 'typ': 'JWT'}),
                     segment({'email': 'fixture@example.test', 'sub': 'fixture-user',
                              'iat': now, 'exp': now + 3600,
                              'https://api.openai.com/auth': {'chatgpt_account_id': WORKSPACE,
                                                              'chatgpt_plan_type': 'business'}}),
                     'Zml4dHVyZQ'))


@contextmanager
def serving(server):
    with server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield server
        finally:
            server.shutdown()
            thread.join()


def run():
    if os.getenv('HEARTH_OPTION_A_FIXTURE') != '1' or [name for _, name in socket.if_nameindex()] != ['lo']:
        raise SystemExit('requires an opted-in loopback-only fixture')
    assert socket.gethostbyname(AUTH_HOST) == '127.0.0.1'
    with socket.socket() as probe:
        probe.settimeout(.5)
        assert probe.connect_ex(('192.0.2.1', 443)) != 0

    idle_calls = []
    idle = SignInRoute(CLIENT_ID, lambda *args: idle_calls.append(args), idle_seconds=1)
    with tempfile.TemporaryDirectory(dir='/tmp') as private:
        with private_sign_in_socket(idle, Path(private)) as expired:
            end = time.monotonic() + 4
            while expired.exists() and time.monotonic() < end:
                time.sleep(.05)
            assert not expired.exists()
            assert UnixSignInPort(expired).request(
                'POST', AUTH_HOST, USERCODE, 'application/json', b'{}')[0] == 502
        assert not idle_calls

    forwarded = []
    token = _fake_token()
    replies = {
        USERCODE: {'device_auth_id':'fixture-device', 'user_code':'TEST-CODE', 'interval':'1'},
        POLL: {'authorization_code':'fixture-code', 'code_verifier':'fixture-verifier',
               'code_challenge':'fixture-challenge'},
        EXCHANGE: {'id_token':token, 'access_token':token, 'refresh_token':'fixture-refresh'},
    }

    class FakeProvider(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_POST(self):
            self.rfile.read(int(self.headers['Content-Length']))
            forwarded.append(self.path)
            result = json.dumps(replies[self.path]).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(result)))
            self.end_headers()
            self.wfile.write(result)

    with serving(HTTPServer(('127.0.0.1', 0), FakeProvider)) as upstream:
        def exchange(path, kind, body):
            conn = http.client.HTTPConnection('127.0.0.1', upstream.server_port, timeout=2)
            try:
                conn.request('POST', path, body, {'Content-Type':kind})
                response = conn.getresponse()
                return response.status, response.read(65537)
            finally:
                conn.close()

        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain('/fixture/tls/server.pem', '/fixture/tls/server.key')
        client = ssl.create_default_context(cafile='/fixture/tls/ca.pem')

        def denied(path, *, host=AUTH_HOST, method='POST', headers=None, body=b'{}'):
            conn = http.client.HTTPSConnection(AUTH_HOST, context=client, timeout=3)
            try:
                conn.request(method, path, body, {'Host':host,'Content-Type':'application/json',**(headers or {})})
                response = conn.getresponse()
                assert response.status == 403 and response.read() == b'{}', path
            finally:
                conn.close()

        with tempfile.TemporaryDirectory(dir='/tmp') as home, tempfile.TemporaryDirectory(dir='/tmp') as private:
            with patch('option_a_live_sign_in.OpenAIAuthTransport', return_value=exchange), \
                    live_sign_in_socket(Path(private), WORKSPACE, 'fixture@example.test') as (path, command):
                port = UnixSignInPort(path)
                assert port.request('POST', AUTH_HOST, '/backend-api/codex/responses',
                                    'application/json', b'{}')[0] == 403
                assert port.request('POST', 'api.openai.com', USERCODE, 'application/json',
                                    json.dumps({'client_id':CLIENT_ID}).encode())[0] == 403
                with serving(loopback_tls_server(port, context)):
                    denied('/v1/responses')
                    denied('/backend-api/codex/responses')
                    denied(USERCODE,host='api.openai.com')
                    denied(USERCODE,headers={'Authorization':'Bearer fake'})
                    denied(USERCODE + '?upstream=other.test')
                    denied('https://auth.openai.com' + USERCODE)
                    denied(AUTH_HOST + ':443',method='CONNECT')
                    denied(EXCHANGE,headers={'Content-Type':'application/x-www-form-urlencoded'},
                           body=b'grant_type=refresh_token')
                    denied(EXCHANGE,headers={'Content-Type':'application/x-www-form-urlencoded'},
                           body=b'grant_type=urn:ietf:params:oauth:grant-type:token-exchange&requested_token=openai-api-key')
                    assert not forwarded
                    env = {'HOME':home, 'CODEX_HOME':home, 'PATH':'/usr/bin:/bin',
                           'CODEX_CA_CERTIFICATE':'/fixture/tls/ca.pem',
                           'SSL_CERT_FILE':'/fixture/tls/ca.pem'}
                    login = subprocess.run(command,env=env,
                                           capture_output=True,text=True,timeout=16)
                    if login.returncode:
                        raise AssertionError(f'pinned fixture login failed (exit {login.returncode}; paths={forwarded})')
                    assert Path(home,'auth.json').is_file()
                    denied(USERCODE,body=json.dumps({'client_id':CLIENT_ID}).encode())
            assert not path.exists()
            assert port.request('POST', AUTH_HOST, USERCODE, 'application/json',
                                json.dumps({'client_id':CLIENT_ID}).encode())[0] == 502
            status = subprocess.run(login_status_command(WORKSPACE),
                                    env={'HOME':home, 'CODEX_HOME':home, 'PATH':'/usr/bin:/bin'},
                                    capture_output=True, text=True, timeout=8)
            assert status.returncode == 0 and 'chatgpt' in (status.stdout + status.stderr).lower()
            assert forwarded == [USERCODE, POLL, EXCHANGE]
            receipt_path = Path(private, 'sign-in-receipt.json')
            receipt = receipt_path.read_text(encoding='utf-8')
            assert receipt_path.stat().st_mode & 0o777 == 0o600
            assert json.loads(receipt)['workspace_binding'] == 'matched'
            assert all(secret not in receipt for secret in (WORKSPACE, 'fixture@example.test', token, 'TEST-CODE'))
        print('Unused Unix route closed on idle without sending a request.')
        print('Pinned sign-in passed through TLS and the Unix gate with fake credentials.')
        print('After both listeners closed, Codex login status passed on the same home with network disabled.')
        print('Exactly three auth requests reached the mock. Model, alternate, tunneling and fallback probes reached none.')
        print('Route closed, loopback listeners stopped, and temporary login state removed.')


if __name__ == '__main__':
    run()
