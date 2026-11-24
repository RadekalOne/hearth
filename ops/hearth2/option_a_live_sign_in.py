"""Trial-only, explicitly gated transport for the pinned Codex device flow.

The host owns the policy and the only external transport. The container owns
its loopback TLS listener and a mount of the per-attempt Unix socket inode.
"""
import base64
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
REQUEST_FRAME = 12000
RESPONSE_FRAME = 90000
CURL = '/usr/bin/curl'
SSL_CERTS = '/etc/ssl/certs/ca-certificates.crt'
HOST = 'srv2065995'


def _require_trial_root():
    if (os.name != 'posix' or os.geteuid() != 0
            or os.uname().nodename.split('.')[0] != HOST):
        raise ValueError('live route requires the exact trial host and root controller')


def _workspace_config(workspace_id):
    if type(workspace_id) is not str:
        raise ValueError('canonical workspace ID required')
    workspace = UUID(workspace_id)
    if not workspace.int or str(workspace) != workspace_id:
        raise ValueError('canonical workspace ID required')
    return ['/opt/codex', '-c', 'forced_login_method="chatgpt"',
            '-c', 'forced_chatgpt_workspace_id="' + workspace_id + '"',
            '-c', 'cli_auth_credentials_store="file"']


def login_command(workspace_id):
    return [*_workspace_config(workspace_id), 'login', '--device-auth']


def login_status_command(workspace_id):
    return [*_workspace_config(workspace_id), 'login', 'status']


class OpenAIAuthTransport:
    """Only the host gate may call this transport. Message bodies stay on stdin."""

    def __init__(self, *, authorized=False):
        if authorized is not True:
            raise ValueError('live auth transport authorization required')
        _require_trial_root()
        version = subprocess.run([CURL, '--disable', '--version'], check=True,
                                 capture_output=True, timeout=3, env={'PATH':'/usr/bin:/bin'})
        first = version.stdout.splitlines()[0]
        match = re.match(rb'curl (\d+)\.(\d+)\.(\d+)', first)
        if not match or tuple(map(int, match.groups())) < (8, 4, 0):
            raise ValueError('curl with streaming response size enforcement required')

    def __call__(self, path, kind, body):
        if (path not in (USERCODE, POLL, EXCHANGE) or kind != (FORM if path == EXCHANGE else JSON)
                or type(body) is not bytes or not 0 < len(body) <= BODY_LIMIT):
            return DENIED
        command = [
            CURL, '--disable', '--silent', '--proto', '=https', '--proto-redir', '=https',
            '--noproxy', '*', '--proxy', '', '--cacert', SSL_CERTS, '--tlsv1.2',
            '--connect-timeout', '4', '--max-time', '8', '--max-filesize', str(REPLY_LIMIT),
            '--max-redirs', '0', '--request', 'POST', '--header', 'Content-Type: ' + kind,
            '--data-binary', '@-', '--write-out', '\n%{http_code}', 'https://' + AUTH_HOST + path,
        ]
        try:
            response = subprocess.run(command, input=body, stdout=subprocess.PIPE,
                                      stderr=subprocess.DEVNULL, timeout=10,
                                      env={'PATH':'/usr/bin:/bin'})
            payload, status = response.stdout.rsplit(b'\n', 1)
            if (response.returncode or len(payload) > REPLY_LIMIT
                    or status not in (b'200', b'403', b'404')):
                return FAILED
            return int(status), payload
        except (ValueError, OSError, subprocess.SubprocessError):
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


@contextmanager
def private_sign_in_socket(route, directory):
    """Expose only a private Unix inode; the host checks all requests again."""
    directory = Path(directory)
    info = directory.stat()
    path = directory / 'sign-in.sock'
    if (directory.resolve() != directory or not stat.S_ISDIR(info.st_mode)
            or info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) != 0o700
            or len(os.fsencode(path)) > 100 or path.exists() or path.is_symlink()):
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
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        started = False
        try:
            path.chmod(0o666)
            thread.start()
            started = True
            yield path
        finally:
            route.close()
            if started:
                server.shutdown()
                thread.join()
            try:
                current = path.lstat()
                if stat.S_ISSOCK(current.st_mode) and (current.st_dev, current.st_ino) == (inode.st_dev, inode.st_ino):
                    path.unlink()
            except FileNotFoundError:
                pass


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
def live_sign_in_socket(directory, workspace_id, *, authorized=False):
    """No listener or real request exists until a future explicit activation."""
    command = login_command(workspace_id)
    transport = OpenAIAuthTransport(authorized=authorized)
    route = SignInRoute(CLIENT_ID, transport, window_seconds=WINDOW_SECONDS, max_polls=MAX_POLLS)
    with private_sign_in_socket(route, directory) as path:
        yield path, command
