"""Inactive assembly facts collector; no default file/runtime trust backends.

Enrollment and independent measurement provenance are deployment gates. Fixture
facts exercise validation; they do not establish physical host/namespace proof.
"""
from dataclasses import dataclass
import hashlib
import json
import os
import time
import uuid
from .creation import _digest
from .guard_service import RootGuardArtifacts
from .root_commands import BoundedCommand,_container,_LABELS
from .root_guard import _identity
from .root_lifecycle import NativeAssemblySpec,NativeContainerPolicy,ASSEMBLY_STATES,_shape
from .stopped_container import _COUNTS
from .store import RecordError,safe_payload,timestamp
from .timer_readback import _json


_SAFE_ENV=['PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin',
           'LANG=C.UTF-8','LC_ALL=C.UTF-8','TZ=UTC','HOME=/nonexistent','PYTHONDONTWRITEBYTECODE=1']
_ENV='[{{range $i,$v := .Config.Env}}{{if $i}},{{end}}{{or '+ ' '.join('(eq $v '+json.dumps(v)+')' for v in _SAFE_ENV)+'}}{{end}}]'
_HEALTH='{{if .Config.Healthcheck}}{{eq (json .Config.Healthcheck.Test) "[\\\"NONE\\\"]"}}{{else}}true{{end}}'
_COMMON=('"UserMatch":{{eq .Config.User "1000:1000"}},"EnvironmentSafe":'+_ENV+
         ',"HealthcheckDisabled":'+_HEALTH+',"ArgumentCount":{{len .Config.Cmd}}')
_IMAGE='{"Id":{{json .Id}},"Os":{{json .Os}},"Architecture":{{json .Architecture}},'+_COMMON+',"VolumesCount":{{len .Config.Volumes}},"OnBuildCount":{{len .Config.OnBuild}}}'
_CONTAINER=('{"Id":{{json .Id}},"Image":{{json .Image}},'+_COMMON+
    ',"NetworkMode":{{json .HostConfig.NetworkMode}},"Privileged":{{json .HostConfig.Privileged}},"ReadonlyRootfs":{{json .HostConfig.ReadonlyRootfs}},"Labels":{'+
    ','.join(json.dumps(k)+':{{json (index .Config.Labels '+json.dumps(k)+')}}' for k in _LABELS)+
    '},"Counts":{'+','.join(json.dumps(k)+':{{len '+v+'}}' for k,v in _COUNTS.items())+'},"State":{'+
    ','.join(json.dumps(k)+':{{json .State.'+k+'}}' for k in ['Status','Running','Pid','StartedAt','FinishedAt'])+'}}')


@dataclass(frozen=True)
class RootAssemblyAnchor:
    host_id:str
    boot_id:str
    namespaces:tuple
    assembly_sha256:str
    guard_executable_sha256:str
    dependency_sha256:str
    bootstrap_sha256:str
    credential_policy_sha256:str
    authority_reference:str

    def __post_init__(self):
        try:
            valid=(all(_digest(v) for v in [self.host_id,self.assembly_sha256,self.guard_executable_sha256,
                                          self.dependency_sha256,self.bootstrap_sha256,self.credential_policy_sha256])
                and str(uuid.UUID(self.boot_id))==self.boot_id and type(self.namespaces) is tuple
                and len(self.namespaces)==4 and all(type(pair) is tuple and len(pair)==2 for pair in self.namespaces)
                and {k for k,v in self.namespaces}=={'user','pid','mnt','cgroup'}
                and all(type(v) is int and 0<v<(1<<64) for k,v in self.namespaces)
                and isinstance(self.authority_reference,str) and 1<=len(self.authority_reference)<=4096)
            if not valid:raise ValueError('invalid enrollment')
            safe_payload(vars(self))
        except (ValueError,TypeError,AttributeError):raise RecordError('explicit immutable root enrollment required') from None


class DockerAssemblyMetadata:
    """Fixed read-only inspect, emitting comparisons/counts, NEVER env/argv values."""
    def __init__(self,docker=None,*,clock):
        self.docker=docker if docker is not None else BoundedCommand('/usr/bin/docker')
        self.clock=clock

    def _query(self,kind,target,template):
        args=['--host','unix:///var/run/docker.sock',kind,'inspect','--format',template,'--',target]
        BoundedCommand.validate_arguments(args)
        return _json(self.docker.run(args))

    def _match(self,kind,target,field,values):
        result=[]
        for index,value in enumerate(values):
            # One bounded comparison per argv element, rather than embedding all
            # accepted UTF8 arguments into one oversized --format parameter.
            quoted=json.dumps(value,ensure_ascii=False)
            template='{{if eq (len .Config.'+field+') '+str(len(values))+'}}{{eq (index .Config.'+field+' '+str(index)+') '+quoted+'}}{{else}}false{{end}}'
            match=self._query(kind,target,template)
            if type(match) is not bool:raise RecordError('typed command comparison unavailable')
            result.append(match)
        return result

    def _snapshot(self,kind,target,spec):
        NativeAssemblySpec.encode(spec.manifest());start=self.clock()
        value=self._query(kind,target,_IMAGE if kind=='image' else _CONTAINER)
        common={'UserMatch','EnvironmentSafe','HealthcheckDisabled','ArgumentCount'}
        fields=common|({'Id','Os','Architecture','VolumesCount','OnBuildCount'} if kind=='image' else
            {'Id','Image','NetworkMode','Privileged','ReadonlyRootfs','Labels','Counts','State'})
        if not isinstance(value,dict) or set(value)!=fields or value.get('Id')!=target:
            raise RecordError('selected immutable metadata projection differs')
        value['EntrypointMatch']=self._match(kind,target,'Entrypoint',[spec.entrypoint])==[True]
        value['ArgumentsMatch']=self._match(kind,target,'Cmd',spec.arguments)
        digest=hashlib.sha256(safe_payload(value).encode()).hexdigest()
        return {**value,'observed_at':start.isoformat(),'references':['docker-assembly:'+kind+':'+digest]}

    def image(self,spec):
        if not isinstance(spec.image_id,str) or not spec.image_id.startswith('sha256:') or not _digest(spec.image_id[7:]):
            raise RecordError('immutable image ID required')
        return self._snapshot('image',spec.image_id,spec)

    def container(self,container,spec):
        _container(container);return self._snapshot('container',container,spec)


class RootAssemblyCollector:
    def __init__(self,layout,repository,anchor,metadata=None,file_digests=None,runtime_facts=None,*,
                 host_identity,clock,credential_facts=None,euid=os.geteuid,monotonic=time.monotonic):
        self.layout,self.repository,self.anchor=layout,repository,anchor
        self.metadata,self.file_digests,self.runtime_facts=metadata,file_digests,runtime_facts
        self.credential_facts=credential_facts
        self.host_identity,self.clock,self.euid,self.monotonic=host_identity,clock,euid,monotonic

    def _fresh(self,packet,fields,begin):
        if (not isinstance(packet,dict) or set(packet)!=set(fields)|{'observed_at','references'}
                or not isinstance(packet['references'],list) or not 1<=len(packet['references'])<=100
                or any(not isinstance(v,str) or not v.strip() or len(v)>4096 for v in packet['references'])):
            raise RecordError('independent measurement fields/provenance missing')
        safe_payload(packet);observed=timestamp(packet['observed_at']);now=self.clock()
        if not begin<=observed<=now or (now-observed).total_seconds()>60:
            raise RecordError('measurement predates round, is future or stale')
        # Snapshot nested facts as values: a reused backend dictionary must not
        # retroactively change the first round when the second is acquired.
        return _json(safe_payload({k:packet[k] for k in fields})),list(packet['references'])

    def _equal(self,actual,expected):
        if safe_payload(actual)!=safe_payload(expected):raise RecordError('independent assembly measurement differs')

    def _environment(self,value):
        if not isinstance(value,list) or len(value)>16 or any(type(v) is not bool or not v for v in value):
            raise RecordError('unknown image/container environment refused')

    def _round(self,context,container,policy,spec,begin):
        refs=[];anchor=self.anchor
        runtime_fields={'host_id','boot_id','uid','euid','namespaces','guard_executable_sha256','dependency_closure_sha256','bootstrap_gate_sha256'}
        runtime,r=self._fresh(self.runtime_facts.observe(dict(context),container,spec),runtime_fields,begin);refs+=r
        self._equal(runtime,{'host_id':anchor.host_id,'boot_id':anchor.boot_id,'uid':0,'euid':0,
            'namespaces':dict(anchor.namespaces),'guard_executable_sha256':anchor.guard_executable_sha256,
            'dependency_closure_sha256':anchor.dependency_sha256,'bootstrap_gate_sha256':anchor.bootstrap_sha256})
        guard=RootGuardArtifacts(self.repository).read(self.layout)
        if guard['executable_sha256']!=anchor.guard_executable_sha256:raise RecordError('installed guard file differs from enrollment')
        fields={'image_id','container_id','native_profile_sha256','inventory_policy_sha256','scope','complete',
                'credential_entries','unknown_consumers','unreadable_sources','unscanned_sources'}
        credentials,r=self._fresh(self.credential_facts.observe(spec.image_id,container,spec),fields,begin);refs+=r
        # Config.Env and a handful of approved files cannot establish absence of
        # baked profiles/other consumer paths. Require a separate complete audit.
        self._equal(credentials,{'image_id':spec.image_id,'container_id':container,'native_profile_sha256':spec.sha256,
            'inventory_policy_sha256':anchor.credential_policy_sha256,
            'scope':'image-rootfs-env-native-consumers-v1' if container is None else 'image-container-rootfs-env-native-consumers-mounts-v1',
            'complete':True,'credential_entries':0,'unknown_consumers':0,'unreadable_sources':0,'unscanned_sources':0})
        fields={'Id','Os','Architecture','UserMatch','EnvironmentSafe','VolumesCount','OnBuildCount','HealthcheckDisabled',
                'ArgumentCount','EntrypointMatch','ArgumentsMatch'}
        image,r=self._fresh(self.metadata.image(spec),fields,begin);refs+=r;self._environment(image['EnvironmentSafe'])
        self._equal(image,{'Id':spec.image_id,'Os':'linux','Architecture':'amd64','UserMatch':True,
            'EnvironmentSafe':image['EnvironmentSafe'],'VolumesCount':0,'OnBuildCount':0,'HealthcheckDisabled':True,
            'ArgumentCount':len(spec.arguments),'EntrypointMatch':True,'ArgumentsMatch':[True]*len(spec.arguments)})
        actual_container=None
        if container is not None:
            fields={'Id','Image','UserMatch','EnvironmentSafe','HealthcheckDisabled','ArgumentCount','EntrypointMatch',
                    'ArgumentsMatch','NetworkMode','Privileged','ReadonlyRootfs','Counts','Labels','State'}
            actual_container,r=self._fresh(self.metadata.container(container,spec),fields,begin);refs+=r
            self._environment(actual_container['EnvironmentSafe'])
            self._equal(actual_container,{'Id':container,'Image':spec.image_id,'UserMatch':True,
                'EnvironmentSafe':actual_container['EnvironmentSafe'],'HealthcheckDisabled':True,
                'ArgumentCount':len(spec.arguments),'EntrypointMatch':True,'ArgumentsMatch':[True]*len(spec.arguments),
                'NetworkMode':'none','Privileged':False,'ReadonlyRootfs':True,'Counts':{k:0 for k in _COUNTS},
                'Labels':{'hearth2.run':context['run_id'],'hearth2.creation_epoch':context['creation_epoch'],
                    'hearth2.policy_sha256':context['policy_sha256'],'hearth2.workload':context['workload_id']},
                'State':{'Status':'created','Running':False,'Pid':0,'StartedAt':'0001-01-01T00:00:00Z','FinishedAt':'0001-01-01T00:00:00Z'}})
        files=[]
        for path,digest in spec.files:
            fields={'image_id','container_id','path','sha256','kind','uid','mode','size'}
            fact,r=self._fresh(self.file_digests.observe(spec.image_id,container,path),fields,begin);refs+=r
            bootstrap=path==spec.entrypoint;size=fact['size']
            if type(size) is not int or not 0<size<=(8*1024*1024 if bootstrap else 65536):
                raise RecordError('measured image file size unknown or exceeds bound')
            self._equal(fact,{'image_id':spec.image_id,'container_id':container,'path':path,'sha256':digest,
                'kind':'regular','uid':0,'mode':0o555 if bootstrap else 0o444,'size':size})
            files.append(fact)
        return {'runtime':runtime,'guard':guard,'credentials':credentials,'image':image,'container':actual_container,'files':files},refs

    def inspect(self,context,container,policy,spec):
        try:return self._inspect(context,container,policy,spec)
        except RecordError:raise
        except Exception:raise RecordError('independent assembly observation unavailable') from None

    def _inspect(self,context,container,policy,spec):
        uid=self.euid()
        if type(uid) is not int or uid!=0:raise RecordError('root assembly collector identity required')
        if (not isinstance(self.anchor,RootAssemblyAnchor) or self.metadata is None
                or self.file_digests is None or self.runtime_facts is None or self.credential_facts is None):
            raise RecordError('trusted enrollment and independent measurement backends required')
        _shape(context,'container_id' in context)
        if container is not None:_container(container)
        if 'container_id' in context and context['container_id']!=container:raise RecordError('different bound container')
        original=safe_payload(context);start=self.clock();began=self.monotonic()
        _identity({**context,'container_id':container or '0'*64},self.host_identity)
        self.layout.resolve(context,host_identity=self.host_identity)
        if (not isinstance(policy,NativeContainerPolicy) or not isinstance(spec,NativeAssemblySpec)
                or policy.sha256!=self.layout.native_policy_sha256 or spec.sha256!=policy.native_profile_sha256
                or spec.sha256!=self.anchor.assembly_sha256 or spec.image_id!=policy.image_id
                or self.anchor.host_id!=context['host_id'] or dict(spec.files).get(spec.entrypoint)!=self.anchor.bootstrap_sha256
                or not timestamp(context['at'])<=start<timestamp(context['deadline_at'])):
            raise RecordError('original approved assembly/bootstrap/policy/deadline required')
        first,refs=self._round(context,container,policy,spec,start)
        second_begin=self.clock();second,more=self._round(context,container,policy,spec,second_begin);refs+=more
        _identity({**context,'container_id':container or '0'*64},self.host_identity)
        self.layout.resolve(context,host_identity=self.host_identity)
        uid=self.euid();finish=self.clock();elapsed=self.monotonic()-began
        if (type(uid) is not int or uid!=0 or safe_payload(context)!=original or safe_payload(first)!=safe_payload(second)
                or not start<=second_begin<=finish<timestamp(context['deadline_at'])
                or (finish-start).total_seconds()>60 or not 0<=elapsed<=60):
            raise RecordError('assembly evidence changed, expired, stale or identity changed')
        refs=sorted(set(refs+[self.anchor.authority_reference]));digest=hashlib.sha256(safe_payload(first).encode()).hexdigest()
        refs+=['root-assembly:'+digest]
        if len(refs)>100:raise RecordError('assembly references exceed bound')
        return {'host_id':context['host_id'],'container_id':container,'run_id':context['run_id'],
            'creation_epoch':context['creation_epoch'],'policy_sha256':context['policy_sha256'],
            'native_profile_sha256':spec.sha256,'observed_at':start.isoformat(),
            'states':dict(ASSEMBLY_STATES),'references':refs}
