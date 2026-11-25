"""Closed-by-default path gate for one pinned Codex device login.

The caller supplies a bounded, trusted transport. The trial proof uses loopback.
"""
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading
import time
from urllib.parse import parse_qsl, urlencode


AUTH_HOST = 'auth.openai.com'
USERCODE = '/api/accounts/deviceauth/usercode'
POLL = '/api/accounts/deviceauth/token'
EXCHANGE = '/oauth/token'
CALLBACK = 'https://' + AUTH_HOST + '/deviceauth/callback'
JSON = 'application/json'
FORM = 'application/x-www-form-urlencoded'
BODY_LIMIT = 8192
REPLY_LIMIT = 65536
DENIED = (403, b'{}')
FAILED = (502, b'{}')


def _object(pairs):
    fields = dict(pairs)
    if len(fields) != len(pairs):
        raise ValueError('duplicate field')
    return fields


def _parse(body, kind):
    text = body.decode('utf-8')
    if kind == JSON:
        fields = json.loads(text, object_pairs_hook=_object)
    else:
        fields = _object(parse_qsl(text, strict_parsing=True, keep_blank_values=True,
                                  errors='strict', max_num_fields=5))
    if type(fields) is not dict:
        raise ValueError('object required')
    return fields


def _values(fields, *names):
    values = tuple(fields.get(name) for name in names)
    if any(type(value) is not str or not value or len(value) > 4096 for value in values):
        raise ValueError('missing or malformed device authentication field')
    return values


class SignInRoute:
    """A single device authorization, with no tunneling or alternate origin."""

    def __init__(self, client_id, exchange, *, window_seconds=60, max_polls=20,
                 idle_seconds=None, accept_tokens=None, monotonic=time.monotonic):
        if type(client_id) is not str or not client_id or len(client_id) > 128:
            raise ValueError('fixed OAuth client ID required')
        if (type(window_seconds) is not int or not 1 <= window_seconds <= 900
                or type(max_polls) is not int or not 1 <= max_polls <= 600):
            raise ValueError('bounded device authentication policy required')
        if idle_seconds is not None and (type(idle_seconds) is not int or not 1 <= idle_seconds <= 60):
            raise ValueError('bounded idle timeout required')
        self._client_id = client_id
        self._exchange = exchange
        self._monotonic = monotonic
        self._window = window_seconds
        self._max_polls = max_polls
        self._deadline = None
        self._idle_deadline = None if idle_seconds is None else monotonic() + idle_seconds
        self._idle_expired = False
        self._accept_tokens = accept_tokens
        self._lock = threading.Lock()
        self._stage = 'initial'
        self._device = None
        self._authorization = None
        self._polls = 0

    def _close(self):
        self._stage = 'closed'
        self._device = self._authorization = None

    def close(self):
        with self._lock:
            self._close()

    def _expire_idle(self, now):
        if self._stage == 'initial' and self._idle_deadline is not None and now >= self._idle_deadline:
            self._idle_expired = True
            self._close()
        return self._idle_expired

    def expire_idle(self):
        with self._lock:
            return self._expire_idle(self._monotonic())

    def _allowed(self, path, fields):
        if self._stage == 'initial' and path == USERCODE:
            return fields == {'client_id': self._client_id}
        if self._stage == 'poll' and path == POLL:
            device_id, user_code = self._device
            return fields == {'device_auth_id': device_id, 'user_code': user_code}
        if self._stage == 'exchange' and path == EXCHANGE:
            code, verifier = self._authorization
            return fields == {'grant_type': 'authorization_code', 'client_id': self._client_id,
                              'code': code, 'code_verifier': verifier, 'redirect_uri': CALLBACK}
        return False

    def request(self, method, host, path, kind, body):
        if (method != 'POST' or host != AUTH_HOST or path not in (USERCODE, POLL, EXCHANGE)
                or kind != (FORM if path == EXCHANGE else JSON)
                or type(body) is not bytes or not 0 < len(body) <= BODY_LIMIT):
            return DENIED
        try:
            fields = _parse(body, kind)
        except (ValueError, RecursionError):
            return DENIED
        with self._lock:
            now = self._monotonic()
            if self._expire_idle(now):
                return DENIED
            if self._deadline is not None and now >= self._deadline:
                self._close()
                return DENIED
            if not self._allowed(path, fields):
                return DENIED
            if self._deadline is None:
                self._deadline = now + self._window
            if path == POLL:
                self._polls += 1
                if self._polls > self._max_polls:
                    self._close()
                    return DENIED
            try:
                payload = urlencode(fields) if kind == FORM else json.dumps(fields, separators=(',', ':'))
                status, result = self._exchange(path, kind, payload.encode('utf-8'))
                if self._monotonic() >= self._deadline:
                    raise ValueError('closed during exchange')
                if path == POLL and status in (403, 404):
                    return status, b'{}'
                if status != 200 or type(result) is not bytes or not 0 < len(result) <= REPLY_LIMIT:
                    raise ValueError('sign-in upstream response refused')
                response = _parse(result, JSON)
                if path == USERCODE:
                    code_key = 'user_code' if 'user_code' in response else 'usercode'
                    self._device = _values(response, 'device_auth_id', code_key)
                    self._stage = 'poll'
                elif path == POLL:
                    self._authorization = _values(response, 'authorization_code', 'code_verifier')
                    self._device = None
                    self._stage = 'exchange'
                else:
                    if self._accept_tokens is not None and self._accept_tokens(response) is not True:
                        raise ValueError('sign-in binding refused')
                    _values(response, 'id_token', 'access_token', 'refresh_token')
                    self._close()
                return status, result
            except Exception:
                self._close()
                return FAILED


def loopback_tls_server(route, context):
    """Bind the path-aware gate to TLS loopback in the isolated namespace."""
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def _reply(self, status, body):
            self.send_response(status)
            self.send_header('Content-Type', JSON)
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Connection', 'close')
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            hosts = self.headers.get_all('Host', [])
            sizes = self.headers.get_all('Content-Length', [])
            kinds = self.headers.get_all('Content-Type', [])
            denied_fields = ('Authorization', 'Proxy-Authorization', 'Transfer-Encoding',
                             'Content-Encoding', 'Cookie', 'Forwarded', 'X-Forwarded-Host',
                             'Expect', 'Upgrade', 'Trailer')
            raw = self.requestline.split()
            if (hosts != [AUTH_HOST] or len(kinds) != 1 or len(sizes) != 1
                    or len(raw) != 3 or raw[1] != self.path
                    or not sizes[0].isascii() or not sizes[0].isdigit() or len(sizes[0]) > 4
                    or not 0 < int(sizes[0]) <= BODY_LIMIT
                    or any(field in self.headers for field in denied_fields)):
                self._reply(*DENIED)
                return
            length = int(sizes[0])
            body = self.rfile.read(length)
            self._reply(*(route.request('POST', hosts[0], self.path, kinds[0], body)
                          if len(body) == length else DENIED))

        def do_GET(self):
            self._reply(*DENIED)

        do_CONNECT = do_GET

    class Server(HTTPServer):
        def get_request(self):
            conn, peer = super().get_request()
            conn.settimeout(3)
            try:
                return context.wrap_socket(conn, server_side=True), peer
            except BaseException:
                conn.close()
                raise

        def handle_error(self, *_args):
            pass

    return Server(('127.0.0.1', 443), Handler)
