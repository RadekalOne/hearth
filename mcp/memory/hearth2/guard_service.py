"""Inactive SERVICE-ONLY evidence; no execution, provisioning or launch authority.

Numeric User/Group describe configured identity, not observed runtime UID. Native
policy bytes are pinned here; applying them inside a worker remains a driver gate.
"""
import hashlib
import os
import re
import stat
import time
from .creation import _digest
from .root_guard import _identity
from .root_layout import _path
from .store import RecordError,safe_payload,timestamp
from .timer_readback import SystemdTimerProperties,_SERVICE,_UNIT,_typed,_json


_EXEC='a(sasasttttuii)'
_OTHER=['ExecConditionEx','ExecStartPreEx','ExecStartPostEx','ExecReloadEx','ExecStopEx','ExecStopPostEx']
_SERVICE_FIELDS=[('User','s'),('Group','s'),('DynamicUser','b'),('Type','s'),('Restart','s'),
    ('RemainAfterExit','b'),('RootDirectory','s'),('RootImage','s'),('WorkingDirectory','s'),
    ('MainPID','u'),('Result','s'),('Slice','s'),('ExecStartEx',_EXEC)]+[(k,_EXEC) for k in _OTHER]


def _service_typed(kind,value):
    if kind=='u':return type(value) is int and 0<=value<(1<<32)
    if kind!=_EXEC:return _typed(kind,value)
    def strings(v):
        return isinstance(v,list) and len(v)<=32 and all(isinstance(s,str) and len(s)<=8192 for s in v)
    return (isinstance(value,list) and len(value)<=16 and all(
        isinstance(row,list) and len(row)==10 and _typed('s',row[0]) and strings(row[1]) and strings(row[2])
        and all(_typed('t',v) for v in row[3:7]) and _service_typed('u',row[7])
        and all(type(v) is int and -(1<<31)<=v<(1<<31) for v in row[8:]) for row in value))


class SystemdGuardServiceProperties(SystemdTimerProperties):
    def snapshot(self,guard):
        if not isinstance(guard,str) or re.fullmatch(r'hearth2-deadline-[a-f0-9]{64}',guard) is None:
            raise RecordError('sealed original guard identity required')
        path=self._lookup(guard+'.service')
        return {'service_path':path,'unit':self._properties(path,_SERVICE+'.Unit',_UNIT),
                'service':self._properties(path,_SERVICE+'.Service',_SERVICE_FIELDS,validator=_service_typed)}


class RootGuardArtifacts:
    def __init__(self,repository):self.repository=repository

    def _artifact(self,root,digest):
        if not _digest(digest):raise RecordError('exact artifact digest required')
        fd=os.open(digest+'.json',os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=root)
        try:
            info=os.fstat(fd)
            if (not stat.S_ISREG(info.st_mode) or info.st_uid!=os.geteuid()
                    or stat.S_IMODE(info.st_mode)!=0o400 or not 0<info.st_size<=65536):
                raise RecordError('immutable private artifact required')
            raw=os.read(fd,65537)
            if len(raw)>65536 or hashlib.sha256(raw).hexdigest()!=digest:
                raise RecordError('artifact digest or size differs')
            value=_json(raw)
            if not isinstance(value,dict) or (safe_payload(value)+'\n').encode()!=raw:
                raise RecordError('canonical object artifact required')
            return value
        finally:os.close(fd)

    def read(self,policy):
        root=None;executable=None
        try:
            root=os.open(self.repository,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
            info=os.fstat(root)
            if info.st_uid!=os.geteuid() or stat.S_IMODE(info.st_mode)!=0o700:
                raise RecordError('private owned artifact repository required')
            guard=self._artifact(root,policy.guard_sha256)
            if (set(guard)!={'version','abi','executable','executable_sha256'}
                    or type(guard['version']) is not int or guard['version']!=1
                    or guard['abi']!='hearth2-root-guard-v1' or not _digest(guard['executable_sha256'])):
                raise RecordError('unsupported root guard artifact ABI')
            _path(guard['executable'],root=True)
            self._artifact(root,policy.native_policy_sha256)  # Hash pin, NOT native policy enforcement.
            executable=os.open(guard['executable'],os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
            info=os.fstat(executable)
            if (not stat.S_ISREG(info.st_mode) or info.st_uid!=os.geteuid()
                    or stat.S_IMODE(info.st_mode)!=0o500 or not 0<info.st_size<=8*1024*1024):
                raise RecordError('immutable owned executable required')
            digest=hashlib.sha256();total=0
            while True:
                chunk=os.read(executable,65536)
                if not chunk:break
                total+=len(chunk)
                if total>8*1024*1024:raise RecordError('guard executable exceeds bound')
                digest.update(chunk)
            if digest.hexdigest()!=guard['executable_sha256']:
                raise RecordError('guard executable digest differs')
            return {**guard,'guard_sha256':policy.guard_sha256,'native_policy_sha256':policy.native_policy_sha256}
        except OSError as exc:raise RecordError('guard artifacts unavailable') from exc
        finally:
            if executable is not None:os.close(executable)
            if root is not None:os.close(root)


class RootGuardServiceReadback:
    def __init__(self,properties,artifacts,policy,*,host_identity,clock,monotonic=time.monotonic):
        self.properties,self.artifacts,self.policy=properties,artifacts,policy
        self.host_identity,self.clock,self.monotonic=host_identity,clock,monotonic

    def _check(self,snapshot,binding,artifact):
        if (not isinstance(snapshot,dict) or set(snapshot)!={'service_path','unit','service'}
                or not isinstance(snapshot['service_path'],str)
                or re.fullmatch(r'/org/freedesktop/systemd1/unit/[A-Za-z0-9_]{1,512}',snapshot['service_path']) is None):
            raise RecordError('exact original service snapshot required')
        unit=snapshot['unit'];service=snapshot['service']
        if (not isinstance(unit,dict) or set(unit)!={k for k,_ in _UNIT}
                or not isinstance(service,dict) or set(service)!={k for k,_ in _SERVICE_FIELDS}
                or any(not _typed(kind,unit[name]) for name,kind in _UNIT)
                or any(not _service_typed(kind,service[name]) for name,kind in _SERVICE_FIELDS)):
            raise RecordError('selected service property type or shape differs')
        expected_unit={'Id':binding['guard_id']+'.service','LoadState':'loaded','ActiveState':'inactive',
            'SubState':'dead','Transient':True,'InvocationID':unit['InvocationID']}
        if unit!=expected_unit or unit['InvocationID'] not in ([],[0]*16):
            raise RecordError('original service not transient inactive unused')
        executable=artifact['executable'];argv=[executable,'--binding-json',safe_payload(binding)]
        expected={'User':'0','Group':'0','DynamicUser':False,'Type':'oneshot','Restart':'no',
            'RemainAfterExit':False,'RootDirectory':'','RootImage':'','WorkingDirectory':'/',
            'MainPID':0,'Result':'success','Slice':'system.slice',
            'ExecStartEx':[[executable,argv,['no-env-expand'],0,0,0,0,0,0,0]],**{k:[] for k in _OTHER}}
        if service!=expected:raise RecordError('sealed service executable/root configuration differs')

    def inspect(self,binding):
        try:return self._inspect(binding)
        except RecordError:raise
        except Exception:raise RecordError('original service readback unavailable') from None

    def _inspect(self,binding):
        original=safe_payload(binding);start=self.clock();began=self.monotonic()
        _identity(binding,self.host_identity);self.policy.resolve(binding,host_identity=self.host_identity)
        deadline=timestamp(binding['deadline_at'])
        if start>=deadline:raise RecordError('original deadline elapsed')
        artifact=self.artifacts.read(self.policy)
        first=self.properties.snapshot(binding['guard_id']);self._check(first,binding,artifact)
        second=self.properties.snapshot(binding['guard_id']);self._check(second,binding,artifact)
        after=self.artifacts.read(self.policy)
        _identity(binding,self.host_identity);self.policy.resolve(binding,host_identity=self.host_identity)
        finish=self.clock();elapsed=self.monotonic()-began
        if (safe_payload(binding)!=original or safe_payload(first)!=safe_payload(second)
                or safe_payload(artifact)!=safe_payload(after) or not start<=finish<deadline
                or (finish-start).total_seconds()>60 or not 0<=elapsed<=60):
            raise RecordError('service/artifact/host context changed, expired or stale')
        reference=hashlib.sha256(safe_payload({'snapshot':first,'artifact':artifact,'binding':binding}).encode()).hexdigest()
        return {'service_state':'matched','host_id':binding['host_id'],'guard_id':binding['guard_id'],
                'deadline_at':binding['deadline_at'],'observed_at':start.isoformat(),
                'guard_sha256':self.policy.guard_sha256,'native_policy_sha256':self.policy.native_policy_sha256,
                'references':['root-service:'+reference]}
