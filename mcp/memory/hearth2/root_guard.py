"""Inactive root kernel termination/disarm boundaries, no installed OS driver.

The cgroup implementation performs real descriptor-relative file operations.
Daemon commands and host authentication are injected TRUSTED root ports. Tests
use private regular files/synthetic inventory; they never touch host cgroups.
"""
from contextlib import contextmanager
import os
from pathlib import Path
import re
import stat
from .creation import _digest, _names
from .store import RecordError, timestamp


class CgroupFiles:
    def __init__(self, root=Path('/sys/fs/cgroup')):
        self.root = Path(root).absolute()

    @contextmanager
    def _file(self, parent, name, *, write=False):
        if not isinstance(parent,str) or re.fullmatch(r'hearth2-[a-f0-9]{64}',parent) is None:
            raise RecordError('exact retained cgroup parent required')
        descriptors=[]
        try:
            root=os.open(self.root,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
            descriptors.append(root)
            group=os.open(parent,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=root)
            descriptors.append(group)
            control=os.open(name,(os.O_WRONLY if write else os.O_RDONLY)|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=group)
            descriptors.append(control)
            if not stat.S_ISREG(os.fstat(control).st_mode):
                raise RecordError('cgroup control file type invalid')
            yield control
        except OSError as exc:
            raise RecordError('retained cgroup operation unavailable') from exc
        finally:
            for descriptor in reversed(descriptors):os.close(descriptor)

    def _write(self,parent,name):
        with self._file(parent,name,write=True) as control:
            if os.write(control,b'1')!=1:raise RecordError('cgroup control write incomplete')

    def freeze(self,parent):self._write(parent,'cgroup.freeze')
    def kill(self,parent):self._write(parent,'cgroup.kill')

    def state(self,parent):
        with self._file(parent,'cgroup.events') as control:raw=os.read(control,4097)
        if len(raw)>4096:raise RecordError('cgroup events exceed bound')
        try:
            values={}
            for line in raw.decode('ascii').splitlines():
                key,value=line.split()
                if key in values or key not in {'populated','frozen'} or value not in {'0','1'}:
                    raise ValueError('ambiguous events')
                values[key]=int(value)
            if set(values)!={'populated','frozen'}:raise ValueError('incomplete events')
            return values
        except (ValueError,UnicodeError) as exc:
            raise RecordError('cgroup emptiness or freeze state unknown') from exc


def _identity(binding,host_identity):
    if (not isinstance(binding,dict) or not isinstance(binding.get('run_id'),str)
            or re.fullmatch(r'run_[a-f0-9]{32}',binding['run_id']) is None
            or not isinstance(binding.get('creation_epoch'),str)
            or not 1<=len(binding['creation_epoch'])<=128
            or any(not _digest(binding.get(key)) for key in ['host_id','container_id','policy_sha256'])
            or binding.get('workload_id')!='hearth2-'+binding['run_id'][4:]):
        raise RecordError('sealed original creation identity required')
    names=_names({'run_id':binding['run_id'],'restore_epoch':binding['creation_epoch']})
    if any(binding.get(key)!=value for key,value in names.items()):
        raise RecordError('original guard and retained parent identity changed')
    timestamp(binding.get('deadline_at'))
    if host_identity()!=binding['host_id']:
        raise RecordError('guard must execute on authenticated original host')


def _empty_frozen(state):
    return (isinstance(state,dict) and set(state)=={'populated','frozen'}
        and type(state['populated']) is int and type(state['frozen']) is int
        and state['populated']==0 and state['frozen']==1)


class RootKernelGuard:
    def __init__(self,files,commands,*,host_identity,clock,evidence=None):
        self.files,self.commands=files,commands
        self.host_identity,self.clock=host_identity,clock
        self.evidence=evidence

    def enforce(self,binding):
        """Kernel quiescence FIRST; no error path disarms or deletes the parent."""
        _identity(binding,self.host_identity)
        parent=binding['parent_cgroup'];container=binding['container_id']
        try:
            self.files.freeze(parent)
            self.files.kill(parent)
            config=self.commands.inspect(container)
            labels=config.get('Config',{}).get('Labels',{}) if isinstance(config,dict) else {}
            required={'hearth2.run':binding['run_id'],'hearth2.creation_epoch':binding['creation_epoch'],
                      'hearth2.policy_sha256':binding['policy_sha256'],'hearth2.workload':binding['workload_id']}
            if (not isinstance(config,dict) or config.get('Id')!=container
                    or not isinstance(labels,dict) or any(labels.get(key)!=value for key,value in required.items())
                    or config.get('HostConfig',{}).get('CgroupParent')!=parent):
                raise RecordError('daemon object does not match sealed workload')
            state=config.get('State',{});exit_status=ended=None
            if (isinstance(state,dict) and state.get('Running') is False
                    and type(state.get('Pid')) is int and state['Pid']==0 and state.get('Status')=='exited'
                    and type(state.get('ExitCode')) is int and -(1<<63)<=state['ExitCode']<(1<<63)):
                started=timestamp(state.get('StartedAt'));finished=timestamp(state.get('FinishedAt'))
                if timestamp(binding['at'])<=started<=finished<=self.clock():
                    exit_status=state['ExitCode'];ended=finished.isoformat()
            if self.evidence is None:raise RecordError('durable root evidence required before immutable-ID removal')
            before=self.evidence.append(binding,'observed',{'observed_at':self.clock().isoformat(),
                'exit_status':exit_status,'ended_at':ended})
            self.commands.remove(container)
            if self.commands.absent(container) is not True:
                raise RecordError('successful exact immutable-ID absence query required')
            if not _empty_frozen(self.files.state(parent)):
                raise RecordError('independent empty frozen retained parent required')
            after=self.evidence.append(binding,'removed',{'observed_at':self.clock().isoformat(),
                'verified_empty':True,'immutable_absent':True})
            return {'host_id':binding['host_id'],'container_id':container,'guard_id':binding['guard_id'],
                'parent_cgroup':parent,'deadline_at':binding['deadline_at'],
                'observed_at':self.clock().isoformat(),'exit_status':exit_status,'ended_at':ended,
                'verified_empty':True,'immutable_absent':True,'evidence':[before,after]}
        except BaseException as exc:
            # A daemon failure may race a late child into the frozen parent.
            # Try kernel kill AGAIN even if the renewed freeze request fails.
            try:
                try:self.files.freeze(parent)
                finally:self.files.kill(parent)
            except BaseException as retry_error:
                raise RecordError('guard uncertain; repeated kernel stop failed, parent retained') from retry_error
            raise RecordError('guard incomplete; repeated kernel stop attempted, parent retained') from exc


class IndependentGuardRelease:
    def __init__(self,files,commands,*,host_identity,clock):
        self.files,self.commands=files,commands
        self.host_identity,self.clock=host_identity,clock

    def release(self,binding):
        """Fresh outside queries only; no guard receipt/boolean input is accepted.

        Production must run this observer outside the workload and independently
        of the guard's observations. This helper cannot prove that deployment.
        It neither releases a DB slot nor removes/thaws the retained parent.
        """
        _identity(binding,self.host_identity)
        try:
            if (not _empty_frozen(self.files.state(binding['parent_cgroup']))
                    or self.commands.absent(binding['container_id']) is not True):
                raise RecordError('original parent empty/frozen AND immutable-ID absence required')
            _identity(binding,self.host_identity)
            self.commands.disarm(binding['guard_id'])
        except Exception as exc:
            raise RecordError('independent guard release unconfirmed') from exc
        return {'host_id':binding['host_id'],'container_id':binding['container_id'],
                'guard_id':binding['guard_id'],'observed_at':self.clock().isoformat(),'guard_disarmed':True}
