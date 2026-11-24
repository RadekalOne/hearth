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
from contextlib import contextmanager

from option_a_sign_in import AUTH_HOST, EXCHANGE, POLL, USERCODE, SignInRoute, loopback_tls_server


CLIENT_ID = 'app_EMoamEEZ73f0CkXaXp7hrann'
WORKSPACE = '00000000-0000-4000-8000-000000000001'


def _fake_token():
    def segment(value):
        return base64.urlsafe_b64encode(json.dumps(value).encode()).decode().rstrip('=')
    return '.'.join((segment({'alg': 'none', 'typ': 'JWT'}),
                     segment({'email': 'fixture@example.test',
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
    if os.getenv('HEARTH_OPTION_A_FIXTURE') != '1' or len(socket.if_nameindex()) != 1:
        raise SystemExit('requires an opted-in loopback-only fixture')
    assert socket.gethostbyname(AUTH_HOST) == '127.0.0.1'
    with socket.socket() as probe:
        probe.settimeout(.5)
        assert probe.connect_ex(('192.0.2.1', 443)) != 0

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

        route = SignInRoute(CLIENT_ID, exchange)
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

        with serving(loopback_tls_server(route, context)):
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
            with tempfile.TemporaryDirectory(dir='/tmp') as home:
                env = {'HOME':home, 'CODEX_HOME':home, 'PATH':'/usr/bin:/bin',
                       'CODEX_CA_CERTIFICATE':'/fixture/tls/ca.pem',
                       'SSL_CERT_FILE':'/fixture/tls/ca.pem'}
                command = ['/opt/codex','-c','forced_login_method="chatgpt"',
                           '-c','forced_chatgpt_workspace_id="' + WORKSPACE + '"',
                           '-c','cli_auth_credentials_store="file"']
                login = subprocess.run([*command, 'login','--device-auth'],env=env,
                                       capture_output=True,text=True,timeout=16)
                if login.returncode:
                    # The child sees only synthetic values. Emit no codes or token bodies.
                    raise AssertionError(f'pinned fixture login failed (exit {login.returncode}; paths={forwarded})')
                assert Path(home,'auth.json').is_file()
                status = subprocess.run([*command,'login','status'],env=env,check=True,
                                        capture_output=True,text=True,timeout=8)
                assert 'chatgpt' in (status.stdout + status.stderr).lower()
            route.close()
            denied(USERCODE,body=json.dumps({'client_id':CLIENT_ID}).encode())
            assert forwarded == [USERCODE, POLL, EXCHANGE]
        print('Pinned default-issuer device sign-in and local ChatGPT status passed with fake credentials.')
        print('Exactly three auth requests reached the mock. Model, alternate, tunneling and fallback probes reached none.')
        print('Route closed, loopback listeners stopped, and temporary login state removed.')


if __name__ == '__main__':
    run()
