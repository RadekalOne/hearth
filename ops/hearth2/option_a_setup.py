"""Disabled Option A setup candidate. No live enrollment, login, egress or model dispatch."""
from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile
import time
import uuid


RUN = 'entitlement-20261116-01'
IMAGE = 'sha256:5e2bdb1b0d542d5039cffb8181c65930093949194a65c365dfb1b0fe13a4fa5b'
BINARY_HASH = 'f1cd7fa4ac866c724122f173d408a95385257cbcc9ac5ce5ddba42669c74ba97'
CONFIG_HASH = '50983c4dcb4e433c18c3fa9243ca75d46d13591063545c061fcdf2c1dabd4721'
BRIDGE_HASH = '3189a4b00d342bd9ed30928266828fbff981aa043f67fd38cd8342e9d9e94546'
FIXTURE_HASH = '15e2073c5bcf2dafc6a73268f2a4579d725cf9378abf652d9b3aea33ca8a7621'
MARKER = 'HEARTH-RECEIPT-16NOV'
DOCKER = ('/usr/bin/docker', '--host=unix:///var/run/docker.sock')
CID = re.compile(r'[a-f0-9]{64}')
ATTEMPT = re.compile(r'hearth\.entitlement\.proof=option-a-[a-f0-9]{32}')


class SetupRefused(RuntimeError):
    pass


@dataclass(frozen=True)
class AccountBinding:
    workspace_id: str
    email: str
    seat: str
    auth_method: str
    provider: str
    session_id: str


def account_status(call, method, params, *, expected, attested):
    """Use only a trusted local transport and independent controller observations.

    The trusted host supplies both bindings. The pinned native status alone
    cannot attest workspace or Premium seat. Never expose this as public RPC.
    """
    if (type(method) is not str or method != 'account/read' or type(params) is not dict
            or set(params) != {'refreshToken'} or params['refreshToken'] is not False):
        raise SetupRefused('account_status_method_refused')
    if (type(expected) is not AccountBinding or type(attested) is not AccountBinding
            or any(type(field) is not str or not field.strip() for field in vars(expected).values())
            or any(type(field) is not str for field in vars(attested).values())
            or expected.seat != 'Business Premium'
            or expected.auth_method != 'chatgpt' or expected.provider != 'openai'
            or expected != attested):
        raise SetupRefused('workspace_or_route_binding_unverified')
    try:
        result = call('account/read', {'refreshToken': False})
    except Exception:
        raise SetupRefused('account_status_unavailable') from None
    account = result.get('account') if type(result) is dict else None
    if (type(account) is not dict or account.get('type') != 'chatgpt'
            or account.get('email') != expected.email or account.get('planType') != 'business'
            or result.get('requiresOpenaiAuth') is not True):
        raise SetupRefused('chatgpt_account_unverified')
    return {
        'auth_method': 'chatgpt',
        'email_matched': True,
        'plan': 'business',
        'workspace_binding': 'controller_attested',
        'seat': 'controller_attested',
    }


def _pinned_file(path, digest):
    path = Path(path)
    if (not path.is_absolute() or path.resolve() != path or not path.is_file()
            or ',' in str(path) or hashlib.sha256(path.read_bytes()).hexdigest() != digest):
        raise SetupRefused('file_pin_mismatch')
    return path


def fixture_upstream(path):
    """Close over the exact fixture, with no network, token or general storage."""
    record = json.loads(_pinned_file(path, FIXTURE_HASH).read_text(encoding='utf-8'))
    row = {**record, 'drawer_id': 'drawer_' + RUN}

    def read(tool, params):
        if tool == 'memory_search' and params == {
            'query': RUN, 'limit': 1, 'wing': 'entitlement-fixture', 'room': 'synthetic',
        }:
            return {'results': [dict(row)]}
        if tool == 'memory_get' and params == {'drawer_id': row['drawer_id']}:
            return dict(row)
        raise SetupRefused('outside_synthetic_fixture')

    return read


@contextmanager
def bounded_enrollment(port, channel):
    """Only a staging CID is owned. Revoke first and disarm after observed absence."""
    cid = None
    watchdog = None
    try:
        channel.start()
        created = port.create(channel.socket_path)
        if type(created) is not str or not CID.fullmatch(created):
            raise SetupRefused('staging_cid_invalid')
        cid = created
        watchdog = port.arm(cid)
        port.start(cid)
        yield cid
    finally:
        try:
            channel.close()
        finally:
            if cid is not None:
                if port.remove(cid) is not True:
                    raise SetupRefused('cleanup_unconfirmed')
                if watchdog is not None:
                    port.disarm(watchdog)


def _docker(*args, check=True, timeout=8):
    return subprocess.run((*DOCKER, *args), capture_output=True, text=True, check=check,
                          timeout=timeout, env={'PATH': '/usr/bin:/bin'})


def _registered(attempt):
    return _docker('ps', '-aq', '--no-trunc', '--filter', 'label=' + attempt).stdout.split()


def _remove_owned(cid, attempt):
    if not CID.fullmatch(cid) or not ATTEMPT.fullmatch(attempt):
        return False
    try:
        matches = _registered(attempt)
        if not matches:
            return not _docker('ps', '-aq', '--no-trunc', '--filter', 'id=' + cid).stdout.strip()
        if matches != [cid]:
            return False
        _docker('rm', '-f', cid, check=False, timeout=5)
        return not _docker('ps', '-aq', '--no-trunc', '--filter', 'id=' + cid).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return False


class DockerEnrollment:
    """Trial-root staging port. A unique proof label is never the real run label."""
    def __init__(self, *, binary, config, bridge, state_dir):
        if os.name != 'posix' or os.geteuid() != 0 or os.uname().nodename.split('.')[0] != 'srv2065995':
            raise SetupRefused('trial_root_required')
        self.binary = _pinned_file(binary, BINARY_HASH)
        self.config = _pinned_file(config, CONFIG_HASH)
        self.bridge = _pinned_file(bridge, BRIDGE_HASH)
        self.state_dir = Path(state_dir)
        if (not self.state_dir.is_absolute() or self.state_dir.resolve() != self.state_dir
                or not self.state_dir.is_dir() or self.state_dir.stat().st_uid != 0
                or stat.S_IMODE(self.state_dir.stat().st_mode) != 0o700):
            raise SetupRefused('private_watchdog_state_required')
        self.attempt = 'hearth.entitlement.proof=option-a-' + uuid.uuid4().hex
        self.receipt = self.state_dir / (self.attempt.split('=', 1)[1] + '.json')
        self.socket = None
        self.cid = None
        self.watchdog = None

    def create(self, socket_path):
        if self.socket is not None:
            raise SetupRefused('staging_port_consumed')
        path = Path(socket_path)
        if (not path.is_absolute() or path.resolve() != path or ',' in str(path)
                or not stat.S_ISSOCK(path.lstat().st_mode)):
            raise SetupRefused('private_socket_required')
        self.socket = path
        # Keep intent even if Docker's response is lost. Recovery can resolve
        # the unique staging label without touching the original enrollment.
        with self.receipt.open('x', encoding='utf-8') as stream:
            json.dump({'staging_label': self.attempt, 'run': RUN}, stream)
            stream.flush()
            os.fsync(stream.fileno())
        mounts = ((self.binary, '/opt/codex'), (self.config, '/scratch/codex-home/config.toml'),
                  (self.bridge, '/probe/bridge.py'), (path, '/run/hearth-memory.sock'))
        args = ['create', '--pull=never', '--network=none', '--read-only', '--cap-drop=ALL',
                '--security-opt=no-new-privileges', '--user=1000:1000', '--pids-limit=32',
                '--memory=128m', '--restart=no', '--label', self.attempt,
                '--tmpfs=/tmp:rw,noexec,nosuid,nodev,mode=1777,size=16m']
        for source, target in mounts:
            args += ['--mount', f'type=bind,src={source},dst={target},readonly']
        try:
            cid = _docker(*args, IMAGE, 'python', '-B', '/probe/bridge.py').stdout.strip()
            if not CID.fullmatch(cid) or _registered(self.attempt) != [cid]:
                raise SetupRefused('staging_identity_unconfirmed')
        except (SetupRefused, OSError, subprocess.SubprocessError):
            matches = _registered(self.attempt)
            if len(matches) != 1 or not _remove_owned(matches[0], self.attempt):
                raise SetupRefused('staging_creation_or_cleanup_unconfirmed') from None
            raise SetupRefused('staging_creation_failed') from None
        self.cid = cid
        return cid

    def arm(self, cid):
        if cid != self.cid or self.watchdog is not None or _registered(self.attempt) != [cid]:
            raise SetupRefused('watchdog_identity_unconfirmed')
        ready = self.receipt.with_suffix('.armed')
        outcome = self.receipt.with_suffix('.outcome')
        info = self.socket.lstat()
        watchdog = subprocess.Popen(
            [sys.executable, '-I', str(Path(__file__).resolve()), '--watchdog', cid, self.attempt,
             str(self.socket), str(info.st_dev), str(info.st_ino), str(ready), str(outcome)],
            start_new_session=True, stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        self.watchdog = watchdog
        end = time.monotonic() + 3
        while time.monotonic() < end and watchdog.poll() is None:
            if ready.is_file():
                return watchdog
            time.sleep(.03)
        raise SetupRefused('watchdog_not_armed')

    def start(self, cid):
        if cid != self.cid or self.watchdog is None or self.watchdog.poll() is not None:
            raise SetupRefused('outside_watchdog_required')
        _docker('start', cid)

    def read_native_account(self, method, params):
        """Read a credential-free staged client; a live binding is separate work."""
        if (method != 'account/read' or type(params) is not dict
                or set(params) != {'refreshToken'} or params['refreshToken'] is not False):
            raise SetupRefused('account_status_method_refused')
        if (self.cid is None or self.watchdog is None or self.watchdog.poll() is not None
                or _registered(self.attempt) != [self.cid]):
            raise SetupRefused('status_workload_unverified')
        from relay_native import NativeSession
        entry = """import os, shutil, tempfile
home = tempfile.mkdtemp(prefix='status-', dir='/tmp')
shutil.copyfile('/scratch/codex-home/config.toml', home+'/config.toml')
os.execve('/opt/codex', ['/opt/codex','-c','forced_login_method="chatgpt"',
          'app-server','--listen','stdio://'], {'PATH':'/usr/bin:/bin',
          'HOME':home,'CODEX_HOME':home,'TMPDIR':home})
"""
        command = [*DOCKER, 'exec', '-i', self.cid, 'python', '-B', '-c', entry]
        with tempfile.TemporaryDirectory(prefix='account-status-', dir=self.state_dir) as root:
            session = NativeSession(command, root, timeout=6,
                                    check_active=lambda: self.watchdog.poll() is None)
            try:
                session.call('initialize', {'clientInfo': {'name': 'hearth-option-a-status', 'version': '1'}})
                session._send({'method': 'initialized'})
                return session.call('account/read', {'refreshToken': False})
            finally:
                if not session.close():
                    raise SetupRefused('status_process_cleanup_unconfirmed')

    def remove(self, cid):
        return cid == self.cid and _remove_owned(cid, self.attempt)

    def disarm(self, watchdog):
        if watchdog is not self.watchdog:
            raise SetupRefused('watchdog_identity_unconfirmed')
        if watchdog.poll() is None:
            watchdog.terminate()
        watchdog.wait(timeout=4)


def _watchdog(cid, attempt, path, device, inode, ready, outcome):
    if (os.geteuid() != 0 or os.uname().nodename.split('.')[0] != 'srv2065995'
            or not CID.fullmatch(cid) or not ATTEMPT.fullmatch(attempt)
            or _registered(attempt) != [cid]):
        raise SetupRefused('watchdog_identity_unconfirmed')
    deadline = time.monotonic() + 90
    ready_path = Path(ready)
    staging = ready_path.with_suffix('.arming')
    with staging.open('x', encoding='utf-8') as stream:
        stream.write(cid + '\n')
        stream.flush()
        os.fsync(stream.fileno())
    staging.rename(ready_path)
    time.sleep(max(0, deadline - time.monotonic()))
    removed = _remove_owned(cid, attempt)
    if removed:
        try:
            info = Path(path).lstat()
            if stat.S_ISSOCK(info.st_mode) and (info.st_dev, info.st_ino) == (int(device), int(inode)):
                Path(path).unlink()
        except FileNotFoundError:
            pass
    with Path(outcome).open('x', encoding='utf-8') as stream:
        json.dump({'cid': cid, 'removed': removed}, stream)
        stream.flush()
        os.fsync(stream.fileno())


if __name__ == '__main__':
    if len(sys.argv) != 9 or sys.argv[1] != '--watchdog':
        raise SystemExit('internal staging watchdog only')
    _watchdog(*sys.argv[2:])
