"""Trial-only independent systemd deadline around a disposable Docker workload.

The submitting process exits before the deadline. PID 1 owns the deadline and
whole-container kill; a separate host observer reads the retained parent cgroup.
No native client, login, provider request or persistent service is involved.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import time
import uuid


PAYLOAD = '''import os,signal,subprocess,sys,time
child = 'import os,signal,time; os.setsid(); signal.signal(signal.SIGTERM,signal.SIG_IGN); print("CHILD_READY",flush=True); time.sleep(60)'
subprocess.Popen([sys.executable,'-c',child])
time.sleep(60)
'''


def command(*args, timeout=10):
    result = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError('fixture host operation failed: ' + args[0])
    return result.stdout.strip()


def inspect(container):
    return json.loads(command('docker', 'inspect', container))[0]


def events(group):
    return dict(line.split() for line in (group/'cgroup.events').read_text().splitlines())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute-trial-fixture', action='store_true')
    args = parser.parse_args()
    if not args.execute_trial_fixture or os.geteuid() != 0 or socket.gethostname() != 'srv2065995':
        parser.error('explicit opt-in, root and exact isolated trial host required')
    identity = uuid.uuid4().hex
    name, guard, parent = ('hearth2-deadline-'+identity,
        'hearth2-deadline-'+identity+'.service', 'hearth2fixture'+identity+'.slice')
    group = Path('/sys/fs/cgroup')/parent
    directory = Path(tempfile.mkdtemp(prefix='deadline-fixture-', dir='/root/hearth-runner-trial'))
    directory.chmod(0o755)
    payload = directory/'probe.py';payload.write_text(PAYLOAD);payload.chmod(0o444)
    container = None
    started = time.monotonic()
    try:
        # Retain the empty parent until the observer has read populated=0.
        # Docker's systemd driver owns a child scope, never this observer.
        command('busctl', 'call', 'org.freedesktop.systemd1', '/org/freedesktop/systemd1',
            'org.freedesktop.systemd1.Manager', 'StartTransientUnit', 'ssa(sv)a(sa(sv))',
            parent, 'fail', '1', 'Description', 's', 'Hearth 2 deadline fixture', '0')
        image = command('docker', 'image', 'inspect', '--format', '{{.Id}}', 'hearth2-verify:20261028')
        container = command('docker', 'create', '--name', name,
            '--label', 'hearth2.deadline='+identity, '--pull', 'never',
            '--network', 'none', '--read-only', '--user', '1000:1000',
            '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges',
            '--pids-limit', '16', '--memory', '128m', '--cpus', '0.5',
            '--restart', 'no', '--cgroup-parent', parent,
            '--mount', 'type=bind,src='+str(payload)+',dst=/opt/probe.py,readonly',
            '--env', 'PYTHONDONTWRITEBYTECODE=1', image, 'python', '/opt/probe.py')
        config = inspect(container)
        assert config['Config']['Labels']['hearth2.deadline'] == identity
        assert config['HostConfig']['PidsLimit'] == 16
        assert config['HostConfig']['RestartPolicy']['Name'] == 'no'
        assert config['HostConfig']['CgroupParent'] == parent
        assert config['HostConfig']['ReadonlyRootfs']
        assert config['HostConfig']['NetworkMode'] == 'none'
        # No --wait/--pipe: the submitter exits, leaving PID 1 to enforce time.
        started = time.monotonic()
        command('systemd-run', '--quiet', '--unit='+guard, '--service-type=exec',
            '--property=RuntimeMaxSec=5s', '--property=TimeoutStopSec=1s',
            '--property=Restart=no', '--property=KillMode=control-group',
            '--property=ExecStopPost=-/usr/bin/docker kill --signal=KILL '+container,
            '/usr/bin/docker', 'start', '--attach', container)
        ready = False
        while time.monotonic()-started < 4:
            if 'CHILD_READY' in command('docker', 'logs', '--tail', '5', container):
                ready = True;break
            time.sleep(0.05)
        assert ready, 'resistant child not ready before fixture deadline'
        assert inspect(container)['State']['Running']
        assert events(group)['populated'] == '1'
        own = Path('/proc/self/cgroup').read_text().splitlines()
        assert not any(line.split(':',2)[-1].startswith('/'+parent) for line in own)
        before = events(group)
        while time.monotonic()-started < 12:
            state = inspect(container)['State']
            if not state['Running'] and events(group)['populated'] == '0':
                break
            time.sleep(0.05)
        elapsed = time.monotonic()-started
        assert not state['Running'] and state['Pid'] == 0
        assert state['ExitCode'] == 137, 'fixture did not observe whole-container SIGKILL'
        assert events(group)['populated'] == '0'
        unit_result = command('systemctl', 'show', guard, '--property=Result', '--value')
        assert unit_result == 'timeout', 'guard did not terminate on its own deadline'
        result = {'submitter_exited_while_workload_live':True,
            'observer_outside_live_workload':True, 'pids_cap_before_start':16,
            'deadline_seconds':5, 'observed_elapsed_seconds':round(elapsed,3),
            'before':before, 'after':events(group), 'guard_result':unit_result,
            'observed_exit_status':state['ExitCode'], 'whole_workload_empty':True,
            'network':'none', 'model_called':False, 'real_credentials_used':False,
            'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    finally:
        # Stop only this invocation's transient unit and label-verified container.
        # Unknown daemon state cannot become a successful cleanup receipt.
        subprocess.run(['systemctl','stop',guard], capture_output=True,timeout=10)
        if container is not None:
            label = inspect(container)['Config']['Labels'].get('hearth2.deadline')
            if label != identity:raise RuntimeError('fixture container identity mismatch')
            command('docker','rm','--force',container)
            names=command('docker','container','ls','--all','--filter','name=^/'+name+'$',
                          '--format','{{.Names}}')
            if names:raise RuntimeError('fixture container remains after cleanup')
        command('systemctl','stop',parent)
        subprocess.run(['systemctl','reset-failed',guard],capture_output=True,timeout=5)
        if group.exists():raise RuntimeError('fixture cgroup remains after cleanup')
    result['container_and_cgroup_cleanup_verified']=True
    (directory/'receipt.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'receipt_directory':str(directory),**result},sort_keys=True))


if __name__ == '__main__':main()
