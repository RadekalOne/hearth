"""Inactive concrete root lifecycle. Trusted assembly observer is REQUIRED.

No factory/CLI installs this driver. Tests use private command/observation ports;
their declarations are not evidence of actual native/OS acceptance.
"""
from dataclasses import dataclass
import hashlib
import os
import re
import time
from .creation import _digest,_names
from .guard_evidence import GuardEvidenceStore,_BINDING,_MAX
from .guard_service import RootGuardArtifacts
from .root_commands import BoundedCommand,_container
from .root_guard import _identity
from .root_layout import _path
from .stopped_container import NativeContainerPolicy
from .store import RecordError,safe_payload,timestamp
from .timer_readback import _json,_deadline


ASSEMBLY_STATES={'root_host':'authenticated','namespace':'verified','native_profile':'image-files-verified',
    'bootstrap':'prompt-gate-verified','credentials':'none','mounts':'none','egress':'disabled',
    'dependencies':'pinned','guard_runtime':'installed-verified','account_gate':'required-before-prompt'}


@dataclass(frozen=True)
class NativeAssemblySpec:
    sha256:str
    image_id:str
    entrypoint:str
    arguments:tuple
    files:tuple

    def manifest(self):
        return {'version':1,'kind':'hearth2-memory-only-bootstrap-v1','image_id':self.image_id,
            'entrypoint':self.entrypoint,'arguments':list(self.arguments),'native_policy_files':dict(self.files)}

    def __post_init__(self):
        if (type(self.arguments) is not tuple or type(self.files) is not tuple
                or len(dict(self.files))!=len(self.files)
                or hashlib.sha256(self.encode(self.manifest())).hexdigest()!=self.sha256):
            raise RecordError('assembly object must match immutable digest')

    @staticmethod
    def encode(value):
        if (not isinstance(value,dict) or set(value)!={'version','kind','image_id','entrypoint','arguments','native_policy_files'}
                or type(value['version']) is not int or value['version']!=1
                or value['kind']!='hearth2-memory-only-bootstrap-v1'
                or not isinstance(value['image_id'],str) or not value['image_id'].startswith('sha256:')
                or not _digest(value['image_id'][7:]) or not isinstance(value['arguments'],list)
                or not 1<=len(value['arguments'])<=12
                or any(not isinstance(v,str) or '\0' in v or len(v)>1024 for v in value['arguments'])
                or not isinstance(value['native_policy_files'],dict) or not 1<=len(value['native_policy_files'])<=8
                or any(not _digest(v) for v in value['native_policy_files'].values())):
            raise RecordError('unsupported immutable native assembly contract')
        _path(value['entrypoint'],root=True)
        for path in value['native_policy_files']:_path(path,root=True)
        return (safe_payload(value)+'\n').encode()

    @classmethod
    def load(cls,repository,digest):
        with GuardEvidenceStore(repository)._directory() as directory:
            value=RootGuardArtifacts(repository)._artifact(directory,digest)
        cls.encode(value)
        return cls(digest,value['image_id'],value['entrypoint'],tuple(value['arguments']),
                   tuple(sorted(value['native_policy_files'].items())))


def _shape(context,bound):
    fields=_BINDING if bound else _BINDING-{'container_id'}
    if not isinstance(context,dict) or set(context)!=fields:raise RecordError('exact root lifecycle descriptor required')
    GuardEvidenceStore('/')._binding(context if bound else {**context,'container_id':'0'*64})


class RootLaunchAttempts(GuardEvidenceStore):
    """One-use durable attempts/known created ID; existing/corrupt means held."""
    def _name(self,stage,context):
        if stage not in {'create','created','arm','start'}:raise RecordError('unknown root stage')
        _shape(context,stage in {'arm','start'})
        return stage+'-'+context['guard_id']+'.json'

    def _read(self,directory,stage,context):
        with self._file(directory,self._name(stage,context)) as fd:
            raw=os.read(fd,_MAX+1);value=_json(raw)
            if (len(raw)>_MAX or not isinstance(value,dict)
                    or set(value)!={'version','stage','context','container_id','marked_at','sha256'}
                    or type(value['version']) is not int or value['version']!=1 or value['stage']!=stage):
                raise RecordError('root attempt record invalid')
            self._name(stage,value['context'])
            if stage=='create':
                if value['container_id'] is not None:raise RecordError('create attempt has invented ID')
            else:_container(value['container_id'])
            if stage in {'arm','start'} and value['container_id']!=value['context']['container_id']:
                raise RecordError('root attempt target changed')
            body={k:v for k,v in value.items() if k!='sha256'}
            if (value['sha256']!=hashlib.sha256(safe_payload(body).encode()).hexdigest()
                    or (safe_payload(value)+'\n').encode()!=raw
                    or not timestamp(value['context']['at'])<=timestamp(value['marked_at'])<timestamp(value['context']['deadline_at'])):
                raise RecordError('root attempt checksum or time invalid')
            os.fsync(fd)
        os.fsync(directory)
        return value

    def require(self,stage,context):
        with self._directory() as directory:value=self._read(directory,stage,context)
        if safe_payload(value['context'])!=safe_payload(context):raise RecordError('root attempt context differs')
        return value

    def _created(self,directory,context,container):
        # Lookup uses the original guard name; recorded context is the intent,
        # whereas a later binding has a different journal seq/at and adds ID.
        intent={k:v for k,v in context.items() if k!='container_id'}
        value=self._read(directory,'created',intent)
        common=_BINDING-{'seq','at','container_id'}
        if (value['container_id']!=container
                or any(value['context'][k]!=context[k] for k in common)
                or ('container_id' not in context and safe_payload(value['context'])!=safe_payload(context))):
            raise RecordError('created immutable ID does not match original intent')
        return value

    def require_created(self,context,container):
        _shape(context,'container_id' in context);_container(container)
        with self._directory() as directory:return self._created(directory,context,container)

    def mark(self,stage,context,container=None):
        name=self._name(stage,context);now=self.clock()
        if not timestamp(context['at'])<=now<timestamp(context['deadline_at']):raise RecordError('root attempt outside original deadline')
        if stage=='create':
            if container is not None:raise RecordError('uncreated ID forbidden')
        else:
            _container(container)
            if stage in {'arm','start'} and container!=context['container_id']:raise RecordError('different root attempt ID')
        body={'version':1,'stage':stage,'context':context,'container_id':container,'marked_at':now.isoformat()}
        raw=(safe_payload({**body,'sha256':hashlib.sha256(safe_payload(body).encode()).hexdigest()})+'\n').encode()
        if len(raw)>_MAX:raise RecordError('root attempt exceeds bound')
        with self._directory(write=True) as directory:
            if stage=='created':
                prior=self._read(directory,'create',context)
                if safe_payload(prior['context'])!=safe_payload(context):raise RecordError('different original create attempt')
            if stage=='arm':self._created(directory,context,container)
            if stage=='start':
                prior=self._read(directory,'arm',context)
                if safe_payload(prior['context'])!=safe_payload(context):raise RecordError('different original arm attempt')
            count=0
            with os.scandir(directory) as entries:
                for _ in entries:
                    count+=1
                    if count>=4096:raise RecordError('root attempt capacity exhausted')
            fd=None
            try:
                fd=os.open(name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o400,dir_fd=directory)
                os.fchmod(fd,0o400)
                if os.write(fd,raw)!=len(raw):raise RecordError('root attempt write incomplete')
                os.fsync(fd);os.fsync(directory)
            finally:
                if fd is not None:os.close(fd)
            # NEVER delete a failed/partial marker: no uncertain external replay.
        return name


class FixedLifecycleCommands:
    def __init__(self,docker=None,systemd_run=None):
        self.docker=docker if docker is not None else BoundedCommand('/usr/bin/docker')
        self.systemd_run=systemd_run if systemd_run is not None else BoundedCommand('/usr/bin/systemd-run')

    @staticmethod
    def create_arguments(intent,policy,mapping,spec):
        _shape(intent,False)
        if spec.sha256!=policy.native_profile_sha256 or spec.image_id!=policy.image_id:raise RecordError('assembly/image policy differs')
        whole,fraction=divmod(policy.nano_cpus,10**9)
        cpus=str(whole)+('.'+str(fraction).zfill(9).rstrip('0') if fraction else '')
        args=['--host','unix:///var/run/docker.sock','container','create','--pull=never','--name='+intent['workload_id'],
            '--restart=no','--network=none','--no-healthcheck','--read-only','--user=1000:1000','--cap-drop=ALL',
            '--security-opt=no-new-privileges:true','--cgroupns=private','--ipc=private','--log-driver=none',
            '--memory='+str(policy.memory_bytes),'--memory-swap='+str(policy.memory_bytes),'--cpus='+cpus,
            '--pids-limit='+str(policy.pids_limit),'--cgroup-parent='+mapping['daemon_parent'],'--entrypoint='+spec.entrypoint]
        for label,key in [('hearth2.run','run_id'),('hearth2.creation_epoch','creation_epoch'),
                          ('hearth2.policy_sha256','policy_sha256'),('hearth2.workload','workload_id')]:
            args+=['--label='+label+'='+intent[key]]
        args+=['--',policy.image_id,*spec.arguments]
        BoundedCommand.validate_arguments(args)
        return args

    def create(self,intent,policy,mapping,spec):
        raw=self.docker.run(self.create_arguments(intent,policy,mapping,spec))
        try:container=raw.decode('ascii').strip()
        except (UnicodeError,AttributeError):raise RecordError('immutable created ID unavailable') from None
        _container(container);return container

    @staticmethod
    def arm_arguments(binding,executable):
        _shape(binding,True);_path(executable,root=True);_,_,calendar=_deadline(binding)
        args=['--system','--no-ask-password','--quiet','--unit='+binding['guard_id'],
              '--on-calendar='+calendar,'--expand-environment=no']
        for prop in ['Type=oneshot','User=0','Group=0','DynamicUser=no','Restart=no','RemainAfterExit=no',
                     'WorkingDirectory=/','Slice=system.slice']:
            args+=['--property='+prop]
        for prop in ['AccuracySec=1ms','RandomizedDelaySec=0','Persistent=no','OnClockChange=no',
                     'OnTimezoneChange=no','RemainAfterElapse=yes']:
            args+=['--timer-property='+prop]
        args+=['--',executable,'--binding-json',safe_payload(binding)]
        BoundedCommand.validate_arguments(args)
        return args

    def arm(self,binding,executable):
        self.systemd_run.run(self.arm_arguments(binding,executable))

    @staticmethod
    def start_arguments(binding):
        _shape(binding,True)
        args=['--host','unix:///var/run/docker.sock','container','start','--',binding['container_id']]
        BoundedCommand.validate_arguments(args)
        return args

    def start(self,binding):self.docker.run(self.start_arguments(binding))


class RootLifecycleDriver:
    def __init__(self,layout,repository,seals,attempts,commands,*,config_reader,timer_reader,service_reader,
                 evidence_root,host_identity,clock,assembly_observer=None,euid=os.geteuid,
                 monotonic=time.monotonic,termination_collector=None):
        self.layout,self.repository,self.seals,self.attempts,self.commands=layout,repository,seals,attempts,commands
        self.config_reader,self.timer_reader,self.service_reader=config_reader,timer_reader,service_reader
        self.evidence_root,self.host_identity,self.clock=evidence_root,host_identity,clock
        self.assembly_observer,self.euid,self.monotonic=assembly_observer,euid,monotonic
        self.termination_collector=termination_collector

    def _uid(self):
        uid=self.euid()
        if type(uid) is not int or uid!=0:raise RecordError('authenticated root lifecycle runtime required')

    def _prepare(self,context,bound):
        self._uid();_shape(context,bound)
        if self.assembly_observer is None:raise RecordError('independent native assembly observer not configured')
        canonical=safe_payload(context);c=_json(canonical);start=self.clock();began=self.monotonic()
        _identity(c if bound else {**c,'container_id':'0'*64},self.host_identity)
        mapping=self.layout.resolve(c,host_identity=self.host_identity)
        if not timestamp(c['at'])<=start<timestamp(c['deadline_at']):raise RecordError('original lifecycle deadline elapsed')
        policy=NativeContainerPolicy.load(self.repository,self.layout.native_policy_sha256)
        spec=NativeAssemblySpec.load(self.repository,policy.native_profile_sha256)
        if spec.image_id!=policy.image_id:raise RecordError('native assembly image differs')
        guard=RootGuardArtifacts(self.repository).read(self.layout)
        return {'original':context,'c':c,'canonical':canonical,'start':start,'began':began,
                'policy':policy,'spec':spec,'guard':guard,'mapping':mapping}

    def _finish(self,w):
        self._uid();c=w['c']
        _identity(c if 'container_id' in c else {**c,'container_id':'0'*64},self.host_identity)
        self.layout.resolve(c,host_identity=self.host_identity);now=self.clock();elapsed=self.monotonic()-w['began']
        if (safe_payload(w['original'])!=w['canonical'] or safe_payload(c)!=w['canonical']
                or not w['start']<=now<timestamp(c['deadline_at']) or (now-w['start']).total_seconds()>60
                or not 0<=elapsed<=60):raise RecordError('lifecycle context/host changed or inspection expired')

    def _proof(self,w,proof,expected):
        if (not isinstance(proof,dict) or set(proof)!=set(expected)|{'observed_at','references'}
                or safe_payload({k:proof[k] for k in expected})!=safe_payload(expected)
                or not isinstance(proof['references'],list) or not 1<=len(proof['references'])<=100
                or any(not isinstance(v,str) or not v.strip() or len(v)>4096 for v in proof['references'])):
            raise RecordError('independent root lifecycle observation incomplete')
        observed=timestamp(proof['observed_at']);now=self.clock()
        if not timestamp(w['c']['at'])<=observed<=now or (now-observed).total_seconds()>60:
            raise RecordError('root lifecycle observation stale')
        return list(proof['references'])

    def _assembly(self,w,container):
        c=w['c'];packet=self.assembly_observer.inspect(dict(c),container,w['policy'],w['spec'])
        return self._proof(w,packet,{'host_id':c['host_id'],'container_id':container,'run_id':c['run_id'],
            'creation_epoch':c['creation_epoch'],'policy_sha256':c['policy_sha256'],
            'native_profile_sha256':w['spec'].sha256,'states':dict(ASSEMBLY_STATES)})

    def _config(self,w,container):
        c=w['c']
        return self._proof(w,self.config_reader.inspect(dict(c),container),{'container_config_state':'matched',
            'host_id':c['host_id'],'container_id':container,'policy_sha256':c['policy_sha256'],
            'native_policy_sha256':w['policy'].sha256,'native_profile_sha256':w['spec'].sha256})

    def _result(self,w,container,refs,armed=False):
        self._finish(w);refs=sorted(set(refs))
        if len(refs)>100:raise RecordError('root lifecycle reference count exceeds bound')
        result={k:w['c'][k] for k in ['host_id','workload_id','guard_id','parent_cgroup','deadline_at','policy_sha256']}
        result.update(container_id=container,container_state='created',observed_at=w['start'].isoformat(),references=refs)
        if armed:result['guard_state']='armed'
        return result

    def preflight(self,registration,claim,*,host_id):
        # Pure observations/planning BEFORE the controller commits one-use intent.
        # begin() subsequently revalidates the exact live claim/registration.
        if registration['claim_id']!=claim['id'] or registration['run_id']!=claim['run_id']:
            raise RecordError('preflight claim differs from registration')
        intent={k:registration[k] for k in ['run_id','claim_id','generation','workload_id','deadline_at','policy_sha256']}
        intent.update(creation_epoch=registration['restore_epoch'],registration_seq=registration['seq'],
            host_id=host_id,**_names(registration),seq=registration['seq'],at=registration['at'],controller=registration['controller'])
        w=self._prepare(intent,False);self._assembly(w,None)
        self.commands.create_arguments(w['c'],w['policy'],w['mapping'],w['spec'])
        self.commands.arm_arguments({**w['c'],'container_id':'0'*64},w['guard']['executable'])
        self._finish(w)

    def create_stopped(self,intent):
        w=self._prepare(intent,False);self._assembly(w,None)
        self.commands.create_arguments(w['c'],w['policy'],w['mapping'],w['spec'])
        self.attempts.mark('create',w['c']);self._finish(w)
        container=self.commands.create(w['c'],w['policy'],w['mapping'],w['spec'])
        _container(container);self._finish(w)
        self.attempts.mark('created',w['c'],container)
        return container

    def inspect_created(self,intent,container):
        w=self._prepare(intent,False);self.attempts.require_created(w['c'],container)
        refs=self._config(w,container)+self._assembly(w,container)
        return self._result(w,container,refs)

    def arm_guard(self,binding):
        w=self._prepare(binding,True);c=w['c'];self.attempts.require_created(c,c['container_id'])
        self._config(w,c['container_id']);self._assembly(w,c['container_id'])
        self.commands.arm_arguments(c,w['guard']['executable'])
        self.seals.seal(c,self.layout,self.evidence_root,host_identity=self.host_identity)
        self.attempts.mark('arm',c,c['container_id']);self._finish(w)
        self.commands.arm(c,w['guard']['executable']);self._finish(w)

    def inspect_armed(self,binding):
        w=self._prepare(binding,True);c=w['c'];self.seals.read(c,host_identity=self.host_identity)
        self.attempts.require_created(c,c['container_id']);self.attempts.require('arm',c)
        refs=self._config(w,c['container_id'])+self._assembly(w,c['container_id'])
        refs+=self._proof(w,self.service_reader.inspect(dict(c)),{'service_state':'matched','host_id':c['host_id'],
            'guard_id':c['guard_id'],'deadline_at':c['deadline_at'],'guard_sha256':self.layout.guard_sha256,
            'native_policy_sha256':w['policy'].sha256})
        timer=self.timer_reader.inspect(dict(c));invocation=timer.get('invocation_id') if isinstance(timer,dict) else None
        if not isinstance(invocation,str) or re.fullmatch(r'[a-f0-9]{32}',invocation) is None or invocation=='0'*32:
            raise RecordError('original timer invocation identity unknown')
        refs+=self._proof(w,timer,{'timer_state':'armed','host_id':c['host_id'],'guard_id':c['guard_id'],
            'deadline_at':c['deadline_at'],'service_id':c['guard_id']+'.service','invocation_id':invocation})
        return self._result(w,c['container_id'],refs,armed=True)

    def start(self,binding):
        w=self._prepare(binding,True);self.inspect_armed(w['c'])
        self.commands.start_arguments(w['c'])
        self.attempts.mark('start',w['c'],w['c']['container_id']);self._finish(w)
        self.commands.start(w['c']);self._finish(w)

    def inspect_termination(self,binding):
        self._uid();_shape(binding,True);_identity(binding,self.host_identity)
        self.seals.read(binding,host_identity=self.host_identity)
        if self.termination_collector is None:raise RecordError('independent outside collector not configured')
        result=self.termination_collector.inspect_termination(dict(binding))
        self._uid();_identity(binding,self.host_identity)
        return result
