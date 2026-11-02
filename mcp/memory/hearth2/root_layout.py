"""Inactive immutable layout projection; no provisioning or OS authentication.

The authenticated host callback and independent observation are trusted ports.
An artifact digest binds expectations, never proves they exist on a live host.
"""
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import stat
from .creation import _digest, _names
from .root_guard import CgroupFiles, _identity
from .store import RecordError, safe_payload, timestamp


def _path(value, *, root=False):
    if (not isinstance(value,str) or not 1<=len(value)<=512 or not value.startswith('/')
            or any(ord(c)<33 or ord(c)>126 or c=='\\' for c in value)
            or (value!='/' and any(p in {'','.','..'} for p in value[1:].split('/')))
            or (root and value=='/')):
        raise RecordError('canonical absolute layout path required')
    return value


@dataclass(frozen=True)
class RootLayoutPolicy:
    sha256:str
    host_id:str
    backend:str
    cgroup_root:str
    control_group_prefix:str
    native_policy_sha256:str
    guard_sha256:str

    def __post_init__(self):
        manifest={k:v for k,v in vars(self).items() if k!='sha256'}
        manifest['version']=1
        if hashlib.sha256(self.encode(manifest)).hexdigest()!=self.sha256:
            raise RecordError('layout object must match immutable policy digest')

    @staticmethod
    def encode(manifest):
        fields={'version','host_id','backend','cgroup_root','control_group_prefix',
                'native_policy_sha256','guard_sha256'}
        if (not isinstance(manifest,dict) or set(manifest)!=fields
                or type(manifest['version']) is not int or manifest['version']!=1
                or any(not _digest(manifest[k]) for k in ['host_id','native_policy_sha256','guard_sha256'])
                or manifest['backend'] not in ('direct','systemd-root-slice')):
            raise RecordError('unsupported immutable root layout policy')
        _path(manifest['cgroup_root'],root=True);_path(manifest['control_group_prefix'])
        if manifest['backend']=='systemd-root-slice' and manifest['control_group_prefix']!='/':
            raise RecordError('only flat root systemd slice layout supported')
        return (safe_payload(manifest)+'\n').encode()

    @classmethod
    def load(cls,repository,digest):
        if not _digest(digest):raise RecordError('exact layout digest required')
        descriptors=[]
        try:
            root=os.open(Path(repository),os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
            descriptors.append(root);info=os.fstat(root)
            if info.st_uid!=os.geteuid() or stat.S_IMODE(info.st_mode)!=0o700:
                raise RecordError('private owned root policy repository required')
            fd=os.open(digest+'.json',os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=root)
            descriptors.append(fd);info=os.fstat(fd)
            if (not stat.S_ISREG(info.st_mode) or info.st_uid!=os.geteuid()
                    or stat.S_IMODE(info.st_mode)!=0o400 or info.st_size>8192):
                raise RecordError('immutable private owned policy file required')
            raw=os.read(fd,8193)
            if len(raw)>8192 or hashlib.sha256(raw).hexdigest()!=digest:
                raise RecordError('root policy checksum or size invalid')
            manifest=json.loads(raw)
            if cls.encode(manifest)!=raw:raise RecordError('canonical root policy required')
            return cls(digest,**{k:v for k,v in manifest.items() if k!='version'})
        except (OSError,ValueError,TypeError,RecursionError) as exc:
            raise RecordError('root policy unavailable or invalid') from exc
        finally:
            for fd in reversed(descriptors):os.close(fd)

    def resolve(self,context,*,host_identity):
        if (not isinstance(context,dict) or context.get('policy_sha256')!=self.sha256
                or context.get('host_id')!=self.host_id or host_identity()!=self.host_id
                or not isinstance(context.get('run_id'),str)
                or re.fullmatch(r'run_[a-f0-9]{32}',context['run_id']) is None
                or not isinstance(context.get('creation_epoch'),str)
                or not 1<=len(context['creation_epoch'])<=128
                or context.get('workload_id')!='hearth2-'+context['run_id'][4:]):
            raise RecordError('original host and immutable layout policy required')
        names=_names({'run_id':context['run_id'],'restore_epoch':context['creation_epoch']})
        if any(context.get(k)!=v for k,v in names.items()):
            raise RecordError('original logical layout identity changed')
        timestamp(context.get('deadline_at'))
        logical=context['parent_cgroup']
        actual=logical if self.backend=='direct' else 'hearth2'+logical.removeprefix('hearth2-')+'.slice'
        control=self.control_group_prefix.rstrip('/')+'/'+actual
        return {'logical_parent':logical,'relative_parent':actual,
                'daemon_parent':control if self.backend=='direct' else actual,'control_group':control}

    def verify_observation(self,binding,proof,*,host_identity,clock):
        mapping=self.resolve(binding,host_identity=host_identity)
        if (not isinstance(proof,dict) or set(proof)!={'host_id','daemon_parent','control_group','observed_at','references'}
                or proof['host_id']!=self.host_id or proof['daemon_parent']!=mapping['daemon_parent']
                or proof['control_group']!=mapping['control_group']
                or not isinstance(proof['references'],list) or not 1<=len(proof['references'])<=100
                or any(not isinstance(v,str) or not v.strip() or len(v)>4096 for v in proof['references'])):
            raise RecordError('independent exact original layout observation required')
        now=clock();observed=timestamp(proof['observed_at'])
        if not 0<=(now-observed).total_seconds()<=60:
            raise RecordError('layout observation stale or future')
        safe_payload(proof)
        if host_identity()!=self.host_id:raise RecordError('original host changed during observation')
        return {**mapping,'layout_state':'matched','observed_at':proof['observed_at'],
                'references':list(proof['references'])}


class MappedCgroupFiles(CgroupFiles):
    def __init__(self,policy,binding,*,host_identity):
        _identity(binding,host_identity)
        self.policy,self.host_identity=policy,host_identity
        self._binding=safe_payload(binding)
        policy.resolve(binding,host_identity=host_identity)
        super().__init__(policy.cgroup_root)

    def verify_binding(self,binding):
        if safe_payload(binding)!=self._binding:raise RecordError('mapped original binding changed')
        _identity(binding,self.host_identity)
        self.policy.resolve(binding,host_identity=self.host_identity)

    def _parent_name(self,parent):
        binding=json.loads(self._binding)
        self.verify_binding(binding)
        mapping=self.policy.resolve(binding,host_identity=self.host_identity)
        if parent!=mapping['logical_parent']:raise RecordError('different mapped logical parent refused')
        return mapping['relative_parent']

    def daemon_parent(self,parent):
        self._parent_name(parent)  # Same exact binding/host/parent fence as file IO.
        return self.policy.resolve(json.loads(self._binding),host_identity=self.host_identity)['daemon_parent']
