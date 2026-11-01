"""Inactive bounded local root command ports; no installed daemon entry point.

Executable paths/permissions are trusted root configuration. The transport is
POSIX-only and cleans up its OWN helper process group, not Docker workloads or
arbitrary escaped sessions. Worker containment remains the independent cgroup.
"""
import json
import math
import os
from pathlib import Path
import re
import selectors
import signal
import subprocess
import time
from .store import RecordError


class BoundedCommand:
    def __init__(self,executable,*,timeout_seconds=5,max_output=65536):
        if (not isinstance(executable,(str,Path)) or not Path(executable).is_absolute()
                or '\0' in str(executable) or type(timeout_seconds) not in {int,float}
                or not math.isfinite(timeout_seconds) or not .05<=timeout_seconds<=10
                or type(max_output) is not int or not 1024<=max_output<=262144):
            raise RecordError('fixed executable and bounded command limits required')
        self.executable=str(executable);self.timeout_seconds=timeout_seconds;self.max_output=max_output

    @staticmethod
    def validate_arguments(args):
        if (not isinstance(args,list) or len(args)>40
                or any(not isinstance(v,str) or '\0' in v or len(v)>8192 for v in args)
                or sum(len(v.encode('utf-8')) for v in args)>32768):
            raise RecordError('bounded root command arguments required')

    def run(self,args):
        self.validate_arguments(args)
        environment={'PATH':'/usr/sbin:/usr/bin:/sbin:/bin','HOME':'/nonexistent',
                     'LANG':'C.UTF-8','LC_ALL':'C.UTF-8','TZ':'UTC'}
        selector=selectors.DefaultSelector();process=None;output=bytearray();used=0
        deadline=time.monotonic()+self.timeout_seconds
        try:
            process=subprocess.Popen([self.executable,*args],stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=environment,cwd='/',
                shell=False,start_new_session=True,close_fds=True)
            for stream,name in [(process.stdout,'stdout'),(process.stderr,'stderr')]:
                os.set_blocking(stream.fileno(),False);selector.register(stream,selectors.EVENT_READ,name)
            exited=False
            while selector.get_map() or not exited:
                remaining=deadline-time.monotonic()
                if remaining<=0:raise RecordError('root command exceeded time bound')
                for key,_ in selector.select(min(.05,remaining)):
                    try:chunk=os.read(key.fileobj.fileno(),min(4096,self.max_output-used+1))
                    except BlockingIOError:continue
                    if not chunk:selector.unregister(key.fileobj);continue
                    used+=len(chunk)
                    if used>self.max_output:raise RecordError('root command exceeded output bound')
                    if key.data=='stdout':output.extend(chunk)
                # Do NOT reap until group cleanup: retain the helper PID while
                # targeting its group, even if the parent exited before a child.
                exited=os.waitid(os.P_PID,process.pid,os.WEXITED|os.WNOHANG|os.WNOWAIT) is not None
        except (OSError,ValueError) as exc:
            raise RecordError('root command unavailable') from None
        finally:
            try:
                if process is not None:
                    try:os.killpg(process.pid,signal.SIGKILL)
                    except ProcessLookupError:pass
                    try:code=process.wait(timeout=1)
                    except subprocess.TimeoutExpired:
                        raise RecordError('root helper termination unconfirmed') from None
            finally:
                selector.close()
                if process is not None:
                    process.stdout.close();process.stderr.close()
        if code!=0:raise RecordError('root command failed')
        return bytes(output)


# Explicit selected projection: never request Config.Env, Path, Args, Mounts,
# arbitrary labels or full State.Error/health logs from the daemon.
_LABELS=['hearth2.run','hearth2.creation_epoch','hearth2.policy_sha256','hearth2.workload']
_STATE=['Running','Pid','Status','ExitCode','StartedAt','FinishedAt']
_INSPECT=('{'+'"Id":{{json .Id}},"Config":{"Labels":{'+
    ','.join(json.dumps(key)+':{{json (index .Config.Labels '+json.dumps(key)+')}}' for key in _LABELS)+
    '}},"HostConfig":{"CgroupParent":{{json .HostConfig.CgroupParent}}},"State":{'+
    ','.join(json.dumps(key)+':{{json .State.'+key+'}}' for key in _STATE)+'}}')


def _object(pairs):
    value={}
    for key,item in pairs:
        if key in value:raise ValueError('duplicate field')
        value[key]=item
    return value


def _container(value):
    if not isinstance(value,str) or re.fullmatch(r'[a-f0-9]{64}',value) is None:
        raise RecordError('exact immutable container ID required')


class DockerSystemdCommands:
    def __init__(self,docker=None,systemctl=None):
        self.docker=docker if docker is not None else BoundedCommand('/usr/bin/docker')
        self.systemctl=systemctl if systemctl is not None else BoundedCommand('/usr/bin/systemctl')

    def _docker(self,args):
        return self.docker.run(['--host','unix:///var/run/docker.sock',*args])

    def inspect(self,container):
        _container(container)
        raw=self._docker(['container','inspect','--format',_INSPECT,'--',container])
        try:
            data=json.loads(raw.decode('utf-8'),object_pairs_hook=_object,
                            parse_constant=lambda _:(_ for _ in ()).throw(ValueError('nonfinite')))
            if (not isinstance(data,dict) or set(data)!={'Id','Config','HostConfig','State'}
                    or data['Id']!=container or not isinstance(data['Config'],dict)
                    or set(data['Config'])!={'Labels'} or not isinstance(data['Config']['Labels'],dict)
                    or set(data['Config']['Labels'])!=set(_LABELS)
                    or any(not isinstance(v,str) or len(v)>256 for v in data['Config']['Labels'].values())
                    or not isinstance(data['HostConfig'],dict) or set(data['HostConfig'])!={'CgroupParent'}
                    or not isinstance(data['HostConfig']['CgroupParent'],str)
                    or len(data['HostConfig']['CgroupParent'])>256
                    or not isinstance(data['State'],dict) or set(data['State'])!=set(_STATE)):
                raise ValueError('unexpected projection')
            state=data['State']
            if (type(state['Running']) is not bool or type(state['Pid']) is not int or state['Pid']<0
                    or type(state['ExitCode']) is not int or not -(1<<63)<=state['ExitCode']<(1<<63)
                    or any(not isinstance(state[k],str) or len(state[k])>128
                           for k in ['Status','StartedAt','FinishedAt'])):
                raise ValueError('unexpected process state')
            return data
        except (ValueError,UnicodeError,RecursionError,TypeError,KeyError):
            raise RecordError('daemon inspection projection invalid') from None

    def remove(self,container):
        _container(container)
        self._docker(['container','rm','--force','--',container])

    def absent(self,container):
        _container(container)
        raw=self._docker(['container','ls','--all','--no-trunc','--filter','id='+container,'--format','{{.ID}}'])
        if raw.strip()==b'':return True
        if raw.strip()==container.encode('ascii'):return False
        raise RecordError('exact immutable-container inventory unconfirmed')

    def disarm(self,guard):
        if not isinstance(guard,str) or re.fullmatch(r'hearth2-deadline-[a-f0-9]{64}',guard) is None:
            raise RecordError('sealed guard identity required')
        prefix=['--system','--no-ask-password','--no-pager'];units=[guard+'.timer',guard+'.service']
        self.systemctl.run(prefix+['stop','--',*units])
        raw=self.systemctl.run(prefix+['list-units','--all','--plain','--no-legend',
            '--state=active,activating,deactivating','--',*units])
        if raw.strip():raise RecordError('guard units still active or unconfirmed')
