"""Opt-in trial absolute-deadline primitive, independent of the submitter.

PID1 owns a one-shot absolute UTC timer before any workload start. A separate
root job freezes/kills the retained parent cgroup before Docker operations and
removes the immutable container ID, so a delayed start cannot resurrect it.
Synthetic resistant processes only; no native CLI, credentials or provider.
Not an installed launcher or authoritative run-record recovery implementation.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import time
import uuid

PAYLOAD = r"""import os,signal,subprocess,sys,time
subprocess.Popen([sys.executable,'-c',
    'import os,signal,time;os.setsid();signal.signal(signal.SIGTERM,signal.SIG_IGN);print("CHILD_READY",flush=True);time.sleep(120)'])
time.sleep(120)
"""
TERMINATE = r"""import json,re,subprocess,sys,time
from pathlib import Path
container,parent,identity,receipt,deadline,fail_docker=sys.argv[1:]
assert re.fullmatch('[a-f0-9]{64}',container)
assert re.fullmatch('hearth2absfixture[a-f0-9]{32}[.]slice',parent)
assert parent=='hearth2absfixture'+identity+'.slice'
group=Path('/sys/fs/cgroup')/parent

def command(*args):
    if fail_docker=='1' and args[0]=='docker':raise RuntimeError('injected unavailable Docker daemon')
    r=subprocess.run(args,capture_output=True,text=True,timeout=5)
    if r.returncode:raise RuntimeError('guard operation failed: '+args[0])
    return r.stdout.strip()
# This must precede Docker access: daemon failure must not keep workers running.
(group/'cgroup.freeze').write_text('1')
frozen_at=time.time();(group/'cgroup.kill').write_text('1')
config=json.loads(command('docker','inspect',container))[0]
assert config['Config']['Labels'].get('hearth2.absolute')==identity
assert config['HostConfig']['CgroupParent']==parent
started=config['State']['StartedAt']!='0001-01-01T00:00:00Z'
exit_status=None
if started:
    end=time.monotonic()+3
    while time.monotonic()<end:
        state=json.loads(command('docker','inspect',container))[0]['State']
        if not state['Running'] and state['Pid']==0:
            exit_status=state['ExitCode'];break
        time.sleep(.02)
    assert exit_status==137,'whole-container SIGKILL not observed'
command('docker','rm','--force',container)
assert not command('docker','container','ls','--all','--no-trunc','--filter','id='+container,'--format','{{.ID}}')
events=dict(line.split() for line in (group/'cgroup.events').read_text().splitlines())
assert events['populated']=='0'
result={'container':container,'parent':parent,'deadline_at':float(deadline),
        'frozen_at':frozen_at,'observed_at':time.time(),'worker_started':started,
        'observed_exit_status':exit_status,'parent_events':events,
        'immutable_container_absent':True,'whole_workload_empty':True}
Path(receipt).write_text(json.dumps(result,sort_keys=True)+'\n');Path(receipt).chmod(0o600)
"""


def command(*args, timeout=12):
    r=subprocess.run(args,capture_output=True,text=True,timeout=timeout)
    if r.returncode:raise RuntimeError('fixture host operation failed: '+args[0])
    return r.stdout.strip()


def populated(group):
    return dict(line.split() for line in (group/'cgroup.events').read_text().splitlines())['populated']


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute-trial-fixture',action='store_true')
    parser.add_argument('--late-start',action='store_true')
    parser.add_argument('--daemon-failure',action='store_true')
    parser.add_argument('--early-cleanup-failure',action='store_true',help='expected failure; requires independent root cleanup observer')
    args=parser.parse_args()
    if not args.execute_trial_fixture or os.geteuid()!=0 or socket.gethostname()!='srv2065995':
        parser.error('explicit opt-in, root and exact isolated trial host required')
    if args.early_cleanup_failure and (args.daemon_failure or args.late_start):parser.error('early cleanup control is a separate running-workload case')
    if args.daemon_failure and args.late_start:parser.error('daemon failure requires a running synthetic workload')
    identity=uuid.uuid4().hex;name='hearth2-absolute-'+identity
    service=name+'.service';timer=name+'.timer';parent='hearth2absfixture'+identity+'.slice'
    group=Path('/sys/fs/cgroup')/parent
    directory=Path(tempfile.mkdtemp(prefix='absolute-deadline-',dir='/root/hearth-runner-trial'))
    directory.chmod(0o755)
    payload=directory/'work.py';payload.write_text(PAYLOAD);payload.chmod(0o444)
    terminate=directory/'terminate.py';terminate.write_text(TERMINATE);terminate.chmod(0o400)
    observation=directory/'termination.json';container=None
    try:
        command('busctl','call','org.freedesktop.systemd1','/org/freedesktop/systemd1',
            'org.freedesktop.systemd1.Manager','StartTransientUnit','ssa(sv)a(sa(sv))',
            parent,'fail','1','Description','s','Hearth absolute deadline fixture','0')
        image=command('docker','image','inspect','--format','{{.Id}}','hearth2-verify:20261028')
        container=command('docker','create','--name',name,'--label','hearth2.absolute='+identity,
            '--pull','never','--network','none','--read-only','--user','1000:1000',
            '--cap-drop','ALL','--security-opt','no-new-privileges','--pids-limit','16',
            '--memory','128m','--cpus','.5','--restart','no','--cgroup-parent',parent,
            '--mount','type=bind,src='+str(payload)+',dst=/opt/work.py,readonly',
            '--env','PYTHONDONTWRITEBYTECODE=1',image,'python','/opt/work.py')
        config=json.loads(command('docker','inspect',container))[0]
        assert config['Config']['Labels']['hearth2.absolute']==identity
        assert config['State']['Status']=='created' and config['HostConfig']['RestartPolicy']['Name']=='no'
        assert config['HostConfig']['PidsLimit']==16 and config['HostConfig']['CgroupParent']==parent
        assert populated(group)=='0'
        deadline=time.time()+8
        calendar=datetime.fromtimestamp(deadline,timezone.utc).strftime('%Y-%m-%d %H:%M:%S.%f UTC')
        submit=['systemd-run','--quiet','--unit='+service,'--on-calendar='+calendar,
            '--timer-property=AccuracySec=1ms','--timer-property=RandomizedDelaySec=0',
            '--property=Type=oneshot','--property=RemainAfterExit=yes',
            '--property=TimeoutStartSec=15s','--property=Restart=no',
            '/usr/bin/python3',str(terminate),container,parent,identity,str(observation),str(deadline),'1' if args.daemon_failure else '0']
        command(*submit)
        assert time.time()<deadline,'timer arm already missed deadline'
        scheduled=command('systemctl','show',timer,'--property=NextElapseUSecRealtime','--value')
        assert scheduled and command('systemctl','is-active',timer)=='active'
        assert command('systemctl','show',timer,'--property=Transient','--value')=='yes'
        if args.early_cleanup_failure:
            state=directory/'state.json'
            state.write_text(json.dumps({'container':container,'identity':identity,'parent':parent,
                'service':service,'timer':timer,'deadline_at':deadline,'directory':str(directory)}))
            state.chmod(0o600);print(json.dumps({'fixture_state':str(state)}),flush=True)
        # The submitting child exited. Recreated controller cannot reset this ID.
        rearm=[('--on-calendar='+datetime.fromtimestamp(deadline+60,timezone.utc).strftime('%Y-%m-%d %H:%M:%S.%f UTC'))
               if value.startswith('--on-calendar=') else value for value in submit]
        duplicate=subprocess.run(rearm,capture_output=True,text=True,timeout=12)
        assert duplicate.returncode!=0,'duplicate unit submission unexpectedly succeeded'
        assert command('systemctl','show',timer,'--property=NextElapseUSecRealtime','--value')==scheduled
        own=Path('/proc/self/cgroup').read_text().splitlines()
        assert not any(line.split(':',2)[-1].startswith('/'+parent) for line in own)
        if not args.late_start:
            time.sleep(2.5) # eats the sealed budget; does not reset a runtime timer.
            command('docker','start',container)
            end=time.monotonic()+2
            while time.monotonic()<end:
                if 'CHILD_READY' in command('docker','logs','--tail','5',container):break
                time.sleep(.02)
            else:raise AssertionError('resistant descendant not ready')
            assert populated(group)=='1'
        if args.early_cleanup_failure:raise RuntimeError('injected early observer failure')
        end=time.monotonic()+15
        if args.daemon_failure:
            while time.monotonic()<end:
                if populated(group)=='0' and command('systemctl','show',service,'--property=Result','--value')=='exit-code':break
                time.sleep(.02)
            else:raise AssertionError('daemon failure did not independently kill/fail closed')
            assert deadline-.02<=time.time()<=deadline+1.5,'daemon-failure stop missed absolute deadline'
            assert not observation.exists(),'failed removal must not produce a success receipt'
            state=json.loads(command('docker','inspect',container))[0]['State']
            assert not state['Running'] and state['Pid']==0 and state['ExitCode']==137
            assert command('docker','container','ls','--all','--no-trunc','--filter','id='+container,'--format','{{.ID}}')==container
            observed={'container':container,'parent':parent,'deadline_at':deadline,
                'observed_at':time.time(),'worker_started':True,'observed_exit_status':137,
                'whole_workload_empty':True,'immutable_container_absent':False,
                'daemon_failure_injected':True,'guard_failed_without_success_receipt':True,
                'removal_and_launch_release_still_unproved':True}
        else:
            while not observation.exists() and time.monotonic()<end:time.sleep(.02)
            assert observation.exists(),'absolute guard did not finish independently'
            observed=json.loads(observation.read_text())
            assert observed['frozen_at']>=deadline-.02
            assert observed['frozen_at']<=deadline+1.5,'guard exceeded permitted fixture scheduling tolerance'
            assert observed['worker_started'] is (not args.late_start)
            assert populated(group)=='0' and observed['whole_workload_empty']
            assert command('systemctl','show',service,'--property=Result','--value')=='success'
            # Removal, rather than kill alone, makes late start of the same ID fail.
            late=subprocess.run(['docker','start',container],capture_output=True,text=True,timeout=10)
            assert late.returncode!=0
            assert not command('docker','container','ls','--all','--no-trunc','--filter','id='+container,'--format','{{.ID}}')
        result={**observed,'case':'daemon-failure' if args.daemon_failure else ('late-start' if args.late_start else 'delayed-start'),
            'submitter_exited_before_workload_start':True,'duplicate_rearm_refused':True,
            'observer_outside_workload':True,'delayed_start_refused_after_deadline':not args.daemon_failure,
            'network':'none','model_called':False,'real_credentials_used':False,
            'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    finally:
        # Never disarm PID1 before independent kernel emptiness. Even Docker
        # cleanup failure leaves the frozen parent and original guard in place.
        if group.exists():
            (group/'cgroup.freeze').write_text('1');(group/'cgroup.kill').write_text('1')
            end=time.monotonic()+3
            while populated(group)!='0' and time.monotonic()<end:time.sleep(.02)
            if populated(group)!='0':raise RuntimeError('cleanup workload emptiness unknown; guard retained')
        if args.early_cleanup_failure:raise RuntimeError('injected Docker cleanup unavailability; guard retained')
        if container is not None:
            found=command('docker','container','ls','--all','--no-trunc','--filter','id='+container,'--format','{{.ID}}')
            if found:
                config=json.loads(command('docker','inspect',container))[0]
                if config['Config']['Labels'].get('hearth2.absolute')!=identity:
                    raise RuntimeError('fixture cleanup ownership mismatch')
                command('docker','rm','--force',container)
            if command('docker','container','ls','--all','--no-trunc','--filter','id='+container,'--format','{{.ID}}'):
                raise RuntimeError('fixture container remains')
        # A completed transient timer may already be collected. Require the
        # successful outside inventory below, rather than infer stop from status.
        subprocess.run(['systemctl','stop',timer,service,parent],capture_output=True,timeout=20)
        subprocess.run(['systemctl','reset-failed',service,timer],capture_output=True,timeout=5)
        if group.exists():raise RuntimeError('fixture parent remains')
        if command('systemctl','list-units','--all','--plain','--no-legend',
                   '--state=active,activating,deactivating',service,timer,parent):
            raise RuntimeError('fixture transient unit remains active')
    result['container_cgroup_units_cleanup_verified']=True
    (directory/'receipt.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'receipt_directory':str(directory),**result},sort_keys=True))


if __name__=='__main__':main()
