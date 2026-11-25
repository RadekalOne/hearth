"""Trial-only, explicitly gated transport for the pinned Codex device flow.

The host owns the policy and the only external transport. The container owns
its loopback TLS listener and a mount of the per-attempt Unix socket inode.
"""
import base64
from collections import Counter
from contextlib import contextmanager
import json
import os
from pathlib import Path
import re
import socket
import socketserver
import stat
import subprocess
import threading
import time
from uuid import UUID

from option_a_sign_in import (
    AUTH_HOST, BODY_LIMIT, DENIED, EXCHANGE, FAILED, FORM, JSON, POLL, REPLY_LIMIT,
    USERCODE, SignInRoute, _object,
)


CLIENT_ID = 'app_EMoamEEZ73f0CkXaXp7hrann'
WINDOW_SECONDS = 480
MAX_POLLS = 180
IDLE_SECONDS = 30
USER_AGENT = 'Hearth-Option-A-device-sign-in/1'
REQUEST_FRAME = 12000
RESPONSE_FRAME = 90000
CURL = '/usr/bin/curl'
SSL_CERTS = '/etc/ssl/certs/ca-certificates.crt'
HOST = 'srv2065995'
AUTH_CLAIMS = 'https://api.openai.com/auth'


def _require_trial_root():
    if (os.name != 'posix' or os.geteuid() != 0
            or os.uname().nodename.split('.')[0] != HOST):
        raise ValueError('live route requires the exact trial host and root controller')


def _validate_workspace(workspace_id):
    if type(workspace_id) is not str:
        raise ValueError('canonical workspace ID required')
    workspace = UUID(workspace_id)
    if not workspace.int or str(workspace) != workspace_id:
        raise ValueError('canonical workspace ID required')


def _workspace_config(workspace_id):
    _validate_workspace(workspace_id)
    return ['/opt/codex', '-c', 'forced_login_method="chatgpt"',
            '-c', 'forced_chatgpt_workspace_id="' + workspace_id + '"',
            '-c', 'cli_auth_credentials_store="file"']


def login_command(workspace_id):
    return [*_workspace_config(workspace_id), 'login', '--device-auth']


def login_status_command(workspace_id):
    return [*_workspace_config(workspace_id), 'login', 'status']


class SignInReceipt:
    """Only fixed paths, status codes, failure counts and a binding outcome."""

    def __init__(self):
        self._status = {path: Counter() for path in (USERCODE, POLL, EXCHANGE)}
        self._failures = {path: 0 for path in self._status}
        self._binding = 'not_checked'

    def snapshot(self):
        return {
            'http_status_counts': {path: dict(counts) for path, counts in self._status.items()},
            'transport_failures': self._failures.copy(),
            'workspace_binding': self._binding,
        }


class WorkspaceBinding:
    """Compare controller expectations to claims from the host TLS response.

    This is a host attestation of the observed claims, not JWT signature
    verification and not evidence of the Premium seat tier.
    """

    def __init__(self, workspace_id, email, receipt):
        _validate_workspace(workspace_id)
        if (type(email) is not str or not 3 <= len(email) <= 254
                or '@' not in email or any(c.isspace() for c in email)):
            raise ValueError('validated expected account identity required')
        self._workspace = workspace_id
        self._email = email
        self._receipt = receipt

    def check(self, response):
        matched = False
        try:
            token = response.get('id_token')
            if type(token) is not str or len(token) > 4096:
                raise ValueError('invalid ID token')
            parts = token.split('.')
            if len(parts) != 3 or any(not re.fullmatch('[A-Za-z0-9_-]+', part) for part in parts):
                raise ValueError('invalid ID token shape')
            payload = parts[1]
            claims = json.loads(base64.urlsafe_b64decode(payload + '=' * (-len(payload) % 4)),
                                object_pairs_hook=_object)
            auth = claims.get(AUTH_CLAIMS) if type(claims) is dict else None
            matched = (type(auth) is dict and claims.get('email') == self._email
                       and auth.get('chatgpt_account_id') == self._workspace
                       and auth.get('chatgpt_plan_type') == 'business')
        except (ValueError, RecursionError):
            pass
        self._receipt._binding = 'matched' if matched else 'mismatch'
        return matched


class OpenAIAuthTransport:
    """Only the host gate may call this transport. Message bodies stay on stdin."""

    def __init__(self, *, authorized=False, receipt=None):
        if authorized is not True:
            raise ValueError('live auth transport authorization required')
        _require_trial_root()
        version = subprocess.run([CURL, '--disable', '--version'], check=True,
                                 capture_output=True, timeout=3, env={'PATH':'/usr/bin:/bin'})
        first = version.stdout.splitlines()[0]
        match = re.match(rb'curl (\d+)\.(\d+)\.(\d+)', first)
        if not match or tuple(map(int, match.groups())) < (8, 4, 0):
            raise ValueError('curl with streaming response size enforcement required')
        self.receipt = SignInReceipt() if receipt is None else receipt

    def __call__(self, path, kind, body):
        if (path not in (USERCODE, POLL, EXCHANGE) or kind != (FORM if path == EXCHANGE else JSON)
                or type(body) is not bytes or not 0 < len(body) <= BODY_LIMIT):
            return DENIED
        command = [
            CURL, '--disable', '--silent', '--proto', '=https', '--proto-redir', '=https',
            '--noproxy', '*', '--proxy', '', '--cacert', SSL_CERTS, '--tlsv1.2',
            '--connect-timeout', '4', '--max-time', '8', '--max-filesize', str(REPLY_LIMIT),
            '--max-redirs', '0', '--request', 'POST', '--user-agent', USER_AGENT,
            '--header', 'Content-Type: ' + kind,
            '--data-binary', '@-', '--write-out', '\n%{http_code}', 'https://' + AUTH_HOST + path,
        ]
        try:
            response = subprocess.run(command, input=body, stdout=subprocess.PIPE,
                                      stderr=subprocess.DEVNULL, timeout=10,
                                      env={'PATH':'/usr/bin:/bin'})
            payload, status = response.stdout.rsplit(b'\n', 1)
            if re.fullmatch(rb'[1-5][0-9]{2}', status):
                self.receipt._status[path][status.decode('ascii')] += 1
            if (response.returncode or len(payload) > REPLY_LIMIT
                    or status not in (b'200', b'403', b'404')):
                raise ValueError('upstream response refused')
            return int(status), payload
        except (ValueError, OSError, subprocess.SubprocessError):
            self.receipt._failures[path] += 1
            return FAILED


def _frame(conn, limit, seconds):
    data = bytearray()
    end = time.monotonic() + seconds
    while len(data) <= limit:
        remaining = end - time.monotonic()
        if remaining <= 0:
            raise TimeoutError
        conn.settimeout(remaining)
        chunk = conn.recv(min(4096, limit + 1 - len(data)))
        if not chunk:
            break
        data.extend(chunk)
        if b'\n' in data:
            if data.endswith(b'\n') and data.count(b'\n') == 1 and len(data) <= limit:
                return json.loads(data, object_pairs_hook=_object)
            break
    raise ValueError('invalid sign-in frame')


def _wire(value):
    return json.dumps(value, separators=(',', ':'), ensure_ascii=True).encode('ascii') + b'\n'


def _private_directory(directory):
    directory = Path(directory)
    info = directory.stat()
    if (directory.resolve() != directory or not stat.S_ISDIR(info.st_mode)
            or info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) != 0o700):
        raise ValueError('private sign-in directory required')
    return directory


@contextmanager
def private_sign_in_socket(route, directory):
    """Expose only a private Unix inode; the host checks all requests again."""
    path = _private_directory(directory) / 'sign-in.sock'
    if len(os.fsencode(path)) > 100 or path.exists() or path.is_symlink():
        raise ValueError('private unused sign-in socket path required')

    class Handler(socketserver.BaseRequestHandler):
        def handle(self):
            try:
                request = _frame(self.request, REQUEST_FRAME, 2)
                if (type(request) is not dict or set(request) != {'method','host','path','kind','body'}
                        or any(type(value) is not str for value in request.values())):
                    raise ValueError('invalid request')
                body = base64.b64decode(request.pop('body'), validate=True)
                status, result = route.request(**request, body=body)
            except Exception:
                status, result = DENIED
            try:
                self.request.settimeout(2)
                self.request.sendall(_wire({'status':status, 'body':base64.b64encode(result).decode()}))
            except OSError:
                pass

    with socketserver.UnixStreamServer(str(path), Handler) as server:
        inode = path.lstat()
        stop = threading.Event()
        server.timeout = .1

        def remove_socket():
            try:
                current = path.lstat()
                if stat.S_ISSOCK(current.st_mode) and (current.st_dev, current.st_ino) == (inode.st_dev, inode.st_ino):
                    path.unlink()
            except FileNotFoundError:
                pass

        def serve():
            try:
                while not stop.is_set() and not route.expire_idle():
                    server.handle_request()
            finally:
                server.server_close()
                remove_socket()

        thread = threading.Thread(target=serve, daemon=True)
        started = False
        try:
            path.chmod(0o666)
            thread.start()
            started = True
            yield path
        finally:
            route.close()
            stop.set()
            if started:
                thread.join()
            else:
                remove_socket()


class UnixSignInPort:
    """Container-side relay. It has no external network transport."""

    def __init__(self, path):
        self.path = str(path)

    def request(self, method, host, path, kind, body):
        try:
            with socket.socket(socket.AF_UNIX) as conn:
                conn.settimeout(2)
                conn.connect(self.path)
                conn.sendall(_wire({'method':method, 'host':host, 'path':path, 'kind':kind,
                                    'body':base64.b64encode(body).decode()}))
                response = _frame(conn, RESPONSE_FRAME, 12)
            if type(response) is not dict or set(response) != {'status', 'body'}:
                return FAILED
            result = base64.b64decode(response['body'], validate=True)
            status = response['status']
            if type(status) is not int or status not in (200, 403, 404, 502) or len(result) > REPLY_LIMIT:
                return FAILED
            return status, result
        except (ValueError, OSError, TypeError):
            return FAILED


@contextmanager
def live_sign_in_socket(directory, workspace_id, expected_email, *, authorized=False):
    """No listener or real request exists until a future explicit activation."""
    command = login_command(workspace_id)
    receipt = SignInReceipt()
    binding = WorkspaceBinding(workspace_id, expected_email, receipt)
    transport = OpenAIAuthTransport(authorized=authorized, receipt=receipt)
    directory = _private_directory(directory)
    receipt_path = directory / 'sign-in-receipt.json'
    with open(receipt_path, 'x', encoding='utf-8',
              opener=lambda path, flags: os.open(path, flags | os.O_NOFOLLOW, 0o600)) as stream:
        route = SignInRoute(CLIENT_ID, transport, window_seconds=WINDOW_SECONDS, max_polls=MAX_POLLS,
                            idle_seconds=IDLE_SECONDS, accept_tokens=binding.check)
        try:
            with private_sign_in_socket(route, directory) as path:
                yield path, command
        finally:
            json.dump(receipt.snapshot(), stream, sort_keys=True)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
