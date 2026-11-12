"""Fixed root/TRIAL-only credential-free acceptance harness, not a live runner."""
import fcntl
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import time

ROOT=Path('/root/hearth-runner-trial/offline-relay-20261112')
IMAGE='sha256:5e2bdb1b0d542d5039cffb8181c65930093949194a65c365dfb1b0fe13a4fa5b'


def command(*args):
    p=subprocess.run(args,capture_output=True,text=True,timeout=10,check=True)
    if len(p.stdout)>32768:raise RuntimeError('bounded fixture output required')
    return p.stdout.strip()


def write(path,value):
    temp=path.with_name(path.name+'.'+str(os.getpid())+'.tmp')
    with temp.open('w') as f:json.dump(value,f);f.flush();os.fsync(f.fileno())
    temp.replace(path)


def cg(pid):
    value=next(x.split(':',2)[2] for x in Path(f'/proc/{pid}/cgroup').read_text().splitlines() if x.startswith('0::'))
    path=Path('/sys/fs/cgroup')/value.lstrip('/')
    if not path.resolve().is_relative_to('/sys/fs/cgroup') or path==Path('/sys/fs/cgroup'):raise RuntimeError('cgroup refused')
    return path


def inspect(ident):
    ids=command('docker','container','ls','--all','--no-trunc','--filter','label=hearth.offline.job='+ident,'--format','{{.ID}}').splitlines()
    if len(ids)>1:raise RuntimeError('ambiguous fixture identity')
    if not ids:return None
    row=json.loads(command('docker','inspect',ids[0]))[0]
    if row['Config']['Labels'].get('hearth.offline.job')!=ident or row['Name']!='/hearth-offline-'+ident:
        raise RuntimeError('fixture identity refused')
    return row


def arm_watchdog(ident):
    ready=ROOT/(ident+'.watch-ready')
    p=subprocess.Popen([sys.executable,__file__,'watch',ident],stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
    end=time.monotonic()+5
    while time.monotonic()<end:
        if ready.exists():return p.pid
        if p.poll() is not None:break
        time.sleep(.02)
    raise RuntimeError('fixture supervision unavailable')


def watch(ident):
    end=time.monotonic()+15
    write(ROOT/(ident+'.watch-ready'),{'job':ident,'supervised':True})
    while time.monotonic()<end:
        done=ROOT/(ident+'.stopped.json')
        if done.exists() and json.loads(done.read_text()).get('confirmed_empty') is True:return
        time.sleep(.1)
    # A pause request is not cleanup proof. Latch even if the starter still holds
    # control.lock; start rechecks before docker start and the payload is also15s.
    write(ROOT/(ident+'.paused'),{'job':ident,'paused':True})
    action('stop',ident)


def action(op,ident):
    stopped=ROOT/(ident+'.paused');receipt=ROOT/(ident+'.json')
    with (ROOT/'control.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        if op=='start':
            if stopped.exists() or receipt.exists():return {'job':ident,'refused':True}
            watchdog_pid=arm_watchdog(ident)
            cid=command('docker','create','--name','hearth-offline-'+ident,'--label','hearth.offline.job='+ident,
                '--pull','never','--network','none','--read-only','--user','1000:1000','--cap-drop','ALL',
                '--security-opt','no-new-privileges','--pids-limit','32','--memory','256m','--cpus','1',
                '--tmpfs','/work:rw,nosuid,nodev,uid=1000,gid=1000,size=16m','--workdir','/work',
                '--log-opt','max-size=64k','--log-opt','max-file=1',
                '--mount',f'type=bind,src={ROOT}/probe.py,dst=/fixture/probe.py,readonly',IMAGE,'python','-I','/fixture/probe.py')
            write(receipt,{'job':ident,'container_id':cid,'phase':'created'})
            if stopped.exists():return {'job':ident,'refused':True}
            command('docker','start',cid);row=inspect(ident);path=cg(row['State']['Pid'])
            result={'job':ident,'container_id':cid,'phase':'active','cgroup':str(path),'network':row['HostConfig']['NetworkMode'],
                'readonly':row['HostConfig']['ReadonlyRootfs'],'user':row['Config']['User'],
                'cap_drop':row['HostConfig']['CapDrop'],'mounts':[x['Destination'] for x in row['Mounts']]}
            write(receipt,result)
            result['watchdog_pid']=watchdog_pid
            return result
        if op=='inspect':
            row=inspect(ident)
            if not row:return {'job':ident,'absent':True}
            logs=command('docker','logs','--tail','10',row['Id'])
            return {'job':ident,'running':row['State']['Running'],'probe':json.loads(logs.splitlines()[0]) if logs else None}
        if op!='stop':raise RuntimeError('fixed operation required')
        # Durable tombstone under the SAME lock makes late launch impossible.
        write(stopped,{'job':ident,'paused':True})
        row=inspect(ident)
        if not row:return {'job':ident,'confirmed_empty':True,'late_launch_denied':True}
        saved=json.loads(receipt.read_text()) if receipt.exists() else {}
        if not row['State']['Running'] and row['State']['Pid']==0 and not saved.get('cgroup'):
            command('docker','rm',row['Id']);absent=inspect(ident) is None
            result={'job':ident,'confirmed_empty':absent,'container_removed':absent,'late_launch_denied':True}
            write(ROOT/(ident+'.stopped.json'),result);return result
        path=Path(saved['cgroup']) if saved.get('cgroup') else cg(row['State']['Pid'])
        if row['State']['Running']:command('docker','kill','--signal','KILL',row['Id'])
        command('docker','wait',row['Id']);final=inspect(ident)
        empty=(final['State']['Running'] is False and final['State']['Pid']==0
            and (not path.exists() or 'populated 0' in (path/'cgroup.events').read_text()))
        if not empty:return {'job':ident,'confirmed_empty':False}
        command('docker','rm',row['Id']);absent=inspect(ident) is None
        result={'job':ident,'confirmed_empty':absent,'container_removed':absent,'late_launch_denied':True}
        write(ROOT/(ident+'.stopped.json'),result);return result


if __name__=='__main__':
    if socket.gethostname()!='srv2065995' or os.geteuid()!=0:raise SystemExit('exact root trial host required')
    op,ident=sys.argv[1:]
    if not re.fullmatch('[0-9a-f]{32}',ident):raise SystemExit('fixture identity refused')
    if op=='watch':watch(ident)
    else:print(json.dumps(action(op,ident)))
