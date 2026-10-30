"""Opt-in root fixture on srv2065995 only; no provider or live service calls.

Run --mode parent as the expected-failure control, then --mode cgroup.
This checks isolated OS primitives, not native CLI or Hearth runner acceptance.
"""
import argparse
import ctypes
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import tempfile
import time
import uuid


def populated(group):
    return dict(line.split() for line in (group / 'cgroup.events').read_text().splitlines())['populated'] == '1'


def wait_empty(group):
    end = time.monotonic() + 5
    while populated(group):
        if time.monotonic() > end:
            raise RuntimeError('fixture cgroup failed to empty')
        time.sleep(0.02)


def process_probe(mode, fixture_id):
    # No controller settings are enabled or changed by this fixture.
    group = Path('/sys/fs/cgroup') / ('hearth2-fixture-' + fixture_id)
    group.mkdir()
    proc = None
    result = {'mode': mode, 'process_check_passed': False}
    try:
        (group / 'pids.max').write_text('16')
        assert (group / 'pids.max').read_text().strip() == '16'
        assert (group / 'cgroup.kill').is_file()

        def enter():
            (group / 'cgroup.procs').write_text(str(os.getpid()))
            assert ctypes.CDLL(None).prctl(38, 1, 0, 0, 0) == 0
            os.setgroups([])
            os.setgid(1000)
            os.setuid(1000)

        child_code = 'import os,signal,time; os.setsid(); signal.signal(signal.SIGTERM,signal.SIG_IGN); print("CHILD_READY",flush=True); time.sleep(60)'
        parent_code = ('import subprocess,sys,time; '
                       'subprocess.Popen([sys.executable,"-c",' + repr(child_code) + ']); '
                       'time.sleep(60)')
        proc = subprocess.Popen([sys.executable, '-c', parent_code], preexec_fn=enter,
                                env={'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8'},
                                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        # A bounded readiness wait, even when the untrusted fixture hangs.
        import select
        assert select.select([proc.stdout], [], [], 5)[0], 'child not ready'
        assert proc.stdout.readline().strip() == 'CHILD_READY'
        assert populated(group)
        result['observer_outside_workload'] = str(os.getpid()) not in (group / 'cgroup.procs').read_text().split()
        assert result['observer_outside_workload'], 'observer must be outside the live workload'
        if mode == 'parent':
            proc.send_signal(signal.SIGTERM)
            proc.wait(timeout=5)
            # This must fail: an escaped-session descendant survives parent-only kill.
            result['process_check_passed'] = not populated(group)
        else:
            (group / 'cgroup.kill').write_text('1')
            wait_empty(group)
            proc.wait(timeout=5)
            result['process_check_passed'] = True
        result['pids_cap_before_start'] = 16
    finally:
        if populated(group):
            (group / 'cgroup.kill').write_text('1')
        wait_empty(group)
        if proc is not None:
            proc.wait(timeout=5)
            proc.stdout.close()
        result['cleanup_empty_verified'] = True
        group.rmdir()
    return result


PAYLOAD = r'''
import errno,json,os,socket
from pathlib import Path
checks={}
checks['unprivileged_uid']=os.getuid()==1000
status=dict(line.split(':',1) for line in Path('/proc/self/status').read_text().splitlines() if ':' in line)
checks['no_capabilities']=int(status['CapEff'].strip(),16)==0
checks['no_new_privileges']=status['NoNewPrivs'].strip()=='1'
Path('/scratch/allowed').write_text('scratch-only')
checks['scratch_writable']=Path('/scratch/allowed').read_text()=='scratch-only'
for name,path in [('rootfs_read_only','/etc/hearth2-probe'),('fixture_read_only','/opt/probe.py'),('cgroup_write_denied','/sys/fs/cgroup/cgroup.procs')]:
    try:
        with open(path,'a') as f: f.write('denied')
        checks[name]=False
    except OSError as e:
        checks[name]=e.errno in (errno.EACCES,errno.EPERM,errno.EROFS)
checks['docker_socket_absent']=not Path('/var/run/docker.sock').exists()
checks['host_account_home_absent']=not Path('/home/cloudroom-agent').exists()
try:
    checks['host_root_fixture_unavailable']=not Path('/root/hearth-runner-trial').exists()
except PermissionError:
    checks['host_root_fixture_unavailable']=True
checks['no_provider_credentials']=not any(os.environ.get(k) for k in ['OPENAI_API_KEY','ANTHROPIC_API_KEY','CLAUDE_CODE_OAUTH_TOKEN','HEARTH_MEMORY_TOKEN','HEARTH_API_KEY'])
s=socket.socket(); s.settimeout(1)
try:
    checks['external_network_denied']=s.connect_ex(('192.0.2.1',443))!=0
finally: s.close()
print(json.dumps(checks,sort_keys=True))
raise SystemExit(0 if all(checks.values()) else 1)
'''


def isolation_probe(fixture_id, directory):
    payload = directory / 'probe.py'
    payload.write_text(PAYLOAD)
    payload.chmod(0o644)
    name = 'hearth2-fixture-' + fixture_id
    docker = ['docker']
    args = ['create', '--name', name, '--label', 'hearth2.fixture=' + fixture_id,
            '--pull', 'never', '--network', 'none', '--read-only', '--user', '1000:1000',
            '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges', '--pids-limit', '16',
            '--memory', '128m', '--cpus', '0.5', '--workdir', '/scratch',
            '--tmpfs', '/scratch:rw,noexec,nosuid,nodev,uid=1000,gid=1000,size=8m',
            '--mount', 'type=bind,src=' + str(payload) + ',dst=/opt/probe.py,readonly',
            '--env', 'HOME=/scratch', '--env', 'PYTHONDONTWRITEBYTECODE=1',
            'hearth2-verify:20261028', 'python', '/opt/probe.py']
    container = subprocess.check_output(docker + args, text=True, timeout=20).strip()
    try:
        config = json.loads(subprocess.check_output(docker + ['inspect', container], text=True, timeout=10))[0]
        assert config['Config']['Labels']['hearth2.fixture'] == fixture_id
        assert config['HostConfig']['PidsLimit'] == 16
        assert config['HostConfig']['NetworkMode'] == 'none'
        assert config['HostConfig']['ReadonlyRootfs']
        ran = subprocess.run(docker + ['start', '--attach', container], text=True, capture_output=True, timeout=20)
        assert ran.returncode == 0, 'isolation fixture refused; details retained in fixture output only'
        result = json.loads(ran.stdout.strip())
        assert all(result.values())
        return result
    finally:
        # Delete only this invocation's container, verified above by its private label.
        label = subprocess.check_output(docker + ['inspect', '-f', '{{index .Config.Labels "hearth2.fixture"}}', container], text=True, timeout=10).strip()
        assert label == fixture_id
        subprocess.run(docker + ['rm', '--force', container], check=True, stdout=subprocess.DEVNULL, timeout=15)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute-trial-fixture', action='store_true')
    parser.add_argument('--mode', choices=['parent', 'cgroup'], required=True)
    args = parser.parse_args()
    if not args.execute_trial_fixture or os.geteuid() != 0 or socket.gethostname() != 'srv2065995':
        parser.error('explicit opt-in, root and the exact isolated trial host are required')
    fixture_id = uuid.uuid4().hex
    base = Path('/root/hearth-runner-trial')
    assert base.is_dir()
    directory = Path(tempfile.mkdtemp(prefix='containment-fixture-', dir=base))
    result = process_probe(args.mode, fixture_id)
    result['isolation_checks'] = isolation_probe(fixture_id, directory)
    result['native_cli_exercised'] = False
    result['model_called'] = False
    (directory / 'receipt.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, sort_keys=True))
    raise SystemExit(0 if result['process_check_passed'] else 1)


if __name__ == '__main__':
    main()
