"""Inactive stopped-CONFIGURATION readback, never full launch authority.

Version1 is deliberately network-none/no-extra-mounts. Native profile application,
credential projection and effective OS enforcement remain separate driver gates.
"""
from dataclasses import dataclass
import hashlib
import os
import stat
import time
from .creation import _digest
from .guard_service import RootGuardArtifacts
from .root_commands import BoundedCommand,_container,_LABELS
from .root_guard import _identity
from .store import RecordError,safe_payload,timestamp
from .timer_readback import _json


_HOST=['CgroupParent','Memory','MemorySwap','NanoCpus','PidsLimit','ReadonlyRootfs','Privileged',
       'CapAdd','CapDrop','NetworkMode','PidMode','IpcMode','UTSMode','UsernsMode','CgroupnsMode',
       'SecurityOpt','AutoRemove','RestartPolicy']
_STATE=['Status','Running','Paused','Restarting','Dead','Pid','ExitCode','StartedAt','FinishedAt']
_COUNTS={'binds':'.HostConfig.Binds','mounts':'.HostConfig.Mounts','resolved_mounts':'.Mounts',
    'volumes_from':'.HostConfig.VolumesFrom','devices':'.HostConfig.Devices',
    'device_requests':'.HostConfig.DeviceRequests','device_rules':'.HostConfig.DeviceCgroupRules',
    'tmpfs':'.HostConfig.Tmpfs','extra_hosts':'.HostConfig.ExtraHosts','links':'.HostConfig.Links',
    'port_bindings':'.HostConfig.PortBindings','config_volumes':'.Config.Volumes'}
_INSPECT=('{"Id":{{json .Id}},"Image":{{json .Image}},"Config":{"User":{{json .Config.User}},"Labels":{'+
    ','.join('"'+k+'":{{json (index .Config.Labels "'+k+'")}}' for k in _LABELS)+
    '}},"HostConfig":{'+','.join('"'+k+'":{{json .HostConfig.'+k+'}}' for k in _HOST)+
    '},"State":{'+','.join('"'+k+'":{{json .State.'+k+'}}' for k in _STATE)+
    '},"Counts":{'+','.join('"'+k+'":{{len '+v+'}}' for k,v in _COUNTS.items())+'}}')


@dataclass(frozen=True)
class NativeContainerPolicy:
    sha256:str
    image_id:str
    native_profile_sha256:str
    memory_bytes:int
    nano_cpus:int
    pids_limit:int
    network_mode:str

    def manifest(self):
        return {**{k:v for k,v in vars(self).items() if k!='sha256'},'version':1,
                'kind':'hearth2-memory-only-container-v1','user':'1000:1000','tools':['memory_search','memory_get']}

    def __post_init__(self):
        if hashlib.sha256(self.encode(self.manifest())).hexdigest()!=self.sha256:
            raise RecordError('native policy object must match immutable digest')

    @staticmethod
    def encode(value):
        fields={'version','kind','image_id','native_profile_sha256','user','tools',
                'memory_bytes','nano_cpus','pids_limit','network_mode'}
        if (not isinstance(value,dict) or set(value)!=fields or type(value['version']) is not int
                or value['version']!=1 or value['kind']!='hearth2-memory-only-container-v1'
                or not isinstance(value['image_id'],str) or not value['image_id'].startswith('sha256:')
                or not _digest(value['image_id'][7:]) or not _digest(value['native_profile_sha256'])
                or value['user']!='1000:1000' or value['tools']!=['memory_search','memory_get']
                or value['network_mode']!='none'
                or type(value['memory_bytes']) is not int or not 64*1024**2<=value['memory_bytes']<=16*1024**3
                or type(value['nano_cpus']) is not int or not 10**8<=value['nano_cpus']<=4*10**9
                or type(value['pids_limit']) is not int or not 16<=value['pids_limit']<=512):
            raise RecordError('unsupported bounded memory-only native container policy')
        return (safe_payload(value)+'\n').encode()

    @classmethod
    def load(cls,repository,digest):
        root=None
        try:
            root=os.open(repository,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
            info=os.fstat(root)
            if info.st_uid!=os.geteuid() or stat.S_IMODE(info.st_mode)!=0o700:
                raise RecordError('private owned native policy repository required')
            value=RootGuardArtifacts(repository)._artifact(root,digest)
            cls.encode(value)
            return cls(digest,**{k:value[k] for k in ['image_id','native_profile_sha256',
                'memory_bytes','nano_cpus','pids_limit','network_mode']})
        except OSError as exc:raise RecordError('native container policy unavailable') from exc
        finally:
            if root is not None:os.close(root)


def _projection(value):
    if (not isinstance(value,dict) or set(value)!={'Id','Image','Config','HostConfig','State','Counts'}
            or not isinstance(value['Config'],dict) or set(value['Config'])!={'User','Labels'}
            or not isinstance(value['Config']['Labels'],dict) or set(value['Config']['Labels'])!=set(_LABELS)
            or not isinstance(value['HostConfig'],dict) or set(value['HostConfig'])!=set(_HOST)
            or not isinstance(value['State'],dict) or set(value['State'])!=set(_STATE)
            or not isinstance(value['Counts'],dict) or set(value['Counts'])!=set(_COUNTS)):
        raise RecordError('selected stopped-container projection differs')
    _container(value['Id'])
    if (not isinstance(value['Image'],str) or len(value['Image'])>128
            or not isinstance(value['Config']['User'],str) or len(value['Config']['User'])>128
            or any(not isinstance(v,str) or len(v)>256 for v in value['Config']['Labels'].values())
            or any(type(v) is not int or not 0<=v<=1000000 for v in value['Counts'].values())):
        raise RecordError('stopped-container projection types differ')
    safe_payload(value)
    return value


class DockerStoppedContainerProperties:
    def __init__(self,docker=None):self.docker=docker if docker is not None else BoundedCommand('/usr/bin/docker')

    def inspect(self,container):
        _container(container)
        raw=self.docker.run(['--host','unix:///var/run/docker.sock','container','inspect','--format',_INSPECT,'--',container])
        value=_projection(_json(raw))
        if value['Id']!=container:raise RecordError('different immutable container returned')
        return value


class RootStoppedContainerReadback:
    def __init__(self,properties,layout,repository,*,host_identity,clock,monotonic=time.monotonic):
        self.properties,self.layout,self.repository=properties,layout,repository
        self.host_identity,self.clock,self.monotonic=host_identity,clock,monotonic

    def _check(self,value,context,container,policy,mapping):
        _projection(value)
        expected={'Id':container,'Image':policy.image_id,
            'Config':{'User':'1000:1000','Labels':{'hearth2.run':context['run_id'],
                'hearth2.creation_epoch':context['creation_epoch'],'hearth2.policy_sha256':context['policy_sha256'],
                'hearth2.workload':context['workload_id']}},
            'HostConfig':{'CgroupParent':mapping['daemon_parent'],'Memory':policy.memory_bytes,
                'MemorySwap':policy.memory_bytes,'NanoCpus':policy.nano_cpus,'PidsLimit':policy.pids_limit,
                'ReadonlyRootfs':True,'Privileged':False,'CapAdd':None,'CapDrop':['ALL'],
                'NetworkMode':policy.network_mode,'PidMode':'','IpcMode':'private','UTSMode':'','UsernsMode':'',
                'CgroupnsMode':'private','SecurityOpt':['no-new-privileges:true'],'AutoRemove':False,
                'RestartPolicy':{'Name':'no','MaximumRetryCount':0}},
            'State':{'Status':'created','Running':False,'Paused':False,'Restarting':False,'Dead':False,'Pid':0,
                'ExitCode':0,'StartedAt':'0001-01-01T00:00:00Z','FinishedAt':'0001-01-01T00:00:00Z'},
            'Counts':{k:0 for k in _COUNTS}}
        # Empty optional CapAdd slice may be null or [] in Go JSON. No other
        # unknown/default value is silently converted into a positive assertion.
        if value['HostConfig']['CapAdd']==[]:expected['HostConfig']['CapAdd']=[]
        if safe_payload(value)!=safe_payload(expected):
            raise RecordError('original stopped container resource/security configuration differs')

    def inspect(self,context,container):
        try:return self._inspect(context,container)
        except RecordError:raise
        except Exception:raise RecordError('original stopped-container readback unavailable') from None

    def _inspect(self,context,container):
        _container(container);original=safe_payload(context);start=self.clock();began=self.monotonic()
        if not isinstance(context,dict) or context.get('container_id',container)!=container:
            raise RecordError('original immutable container identity differs')
        _identity({**context,'container_id':container},self.host_identity)
        mapping=self.layout.resolve(context,host_identity=self.host_identity)
        deadline=timestamp(context['deadline_at'])
        if start>=deadline:raise RecordError('original container deadline elapsed')
        policy=NativeContainerPolicy.load(self.repository,self.layout.native_policy_sha256)
        first=self.properties.inspect(container);self._check(first,context,container,policy,mapping)
        second=self.properties.inspect(container);self._check(second,context,container,policy,mapping)
        after=NativeContainerPolicy.load(self.repository,self.layout.native_policy_sha256)
        _identity({**context,'container_id':container},self.host_identity)
        self.layout.resolve(context,host_identity=self.host_identity)
        finish=self.clock();elapsed=self.monotonic()-began
        if (safe_payload(context)!=original or safe_payload(first)!=safe_payload(second) or policy!=after
                or not start<=finish<deadline or (finish-start).total_seconds()>60 or not 0<=elapsed<=60):
            raise RecordError('stopped container/policy/context changed, expired or stale')
        reference=hashlib.sha256(safe_payload({'context':context,'snapshot':first,'native_policy':policy.sha256}).encode()).hexdigest()
        return {'container_config_state':'matched','host_id':context['host_id'],'container_id':container,
                'policy_sha256':context['policy_sha256'],'native_policy_sha256':policy.sha256,
                'native_profile_sha256':policy.native_profile_sha256,'observed_at':start.isoformat(),
                'references':['root-container-config:'+reference]}
