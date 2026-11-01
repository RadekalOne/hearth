"""Private immutable root observations, separate from the restorable work DB.

Checksums detect corruption, not a malicious root. Filesystem ownership, real
fsync/crash semantics and root-only deployment remain independent OS gates.
"""
from contextlib import contextmanager
from datetime import datetime,timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import stat
from .creation import _digest,_names
from .store import RecordError,safe_payload,timestamp


_BINDING={'run_id','claim_id','creation_epoch','generation','registration_seq','workload_id',
          'host_id','container_id','guard_id','parent_cgroup','deadline_at','policy_sha256',
          'seq','at','controller'}
_MAX=16384


class GuardEvidenceStore:
    def __init__(self,root,*,clock=None):
        self.root=Path(root).absolute()
        self.clock=clock or (lambda:datetime.now(timezone.utc))

    def _binding(self,binding):
        if (not isinstance(binding,dict) or set(binding)!=_BINDING
                or any(type(binding[k]) is not int or binding[k]<1 for k in ['generation','registration_seq','seq'])
                or any(not isinstance(v,str) or not 1<=len(v)<=512
                       for k,v in binding.items() if k not in {'generation','registration_seq','seq'})
                or re.fullmatch(r'run_[a-f0-9]{32}',binding['run_id']) is None
                or any(not _digest(binding[k]) for k in ['host_id','container_id','policy_sha256'])
                or binding['workload_id']!='hearth2-'+binding['run_id'][4:]):
            raise RecordError('exact credential-free original binding required')
        names=_names({'run_id':binding['run_id'],'restore_epoch':binding['creation_epoch']})
        if any(binding[k]!=v for k,v in names.items()):raise RecordError('original guard identity changed')
        timestamp(binding['deadline_at']);timestamp(binding['at'])
        return hashlib.sha256(safe_payload(binding).encode()).hexdigest()

    def _validate(self,binding,stage,observation):
        if stage not in {'observed','removed'} or not isinstance(observation,dict):
            raise RecordError('exact guard observation stage required')
        fields={'observed_at','exit_status','ended_at'} if stage=='observed' else {'observed_at','verified_empty','immutable_absent'}
        if set(observation)!=fields:raise RecordError('guard evidence fields differ from contract')
        observed=timestamp(observation['observed_at'])
        if not timestamp(binding['at'])<=observed<=self.clock():
            raise RecordError('guard evidence time impossible')
        if stage=='removed':
            if observation['verified_empty'] is not True or observation['immutable_absent'] is not True:
                raise RecordError('successful removal/empty observation required')
        else:
            code=observation['exit_status'];ended=observation['ended_at']
            if code is None:
                if ended is not None:raise RecordError('unknown exit cannot invent an end')
            elif (type(code) is not int or not -(1<<63)<=code<(1<<63) or ended is None
                    or not timestamp(binding['at'])<=timestamp(ended)<=observed):
                raise RecordError('known guard exit/end invalid')

    @contextmanager
    def _directory(self,*,write=False):
        fd=None
        try:
            fd=os.open(self.root,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
            info=os.fstat(fd)
            if info.st_uid!=os.geteuid() or stat.S_IMODE(info.st_mode)!=0o700:
                raise RecordError('guard evidence directory must be private and service-owned')
            fcntl.flock(fd,(fcntl.LOCK_EX if write else fcntl.LOCK_SH)|fcntl.LOCK_NB)
            yield fd
        except OSError as exc:
            raise RecordError('guard evidence storage unavailable or busy') from None
        finally:
            if fd is not None:os.close(fd)

    @contextmanager
    def _file(self,directory,name):
        fd=None
        try:
            fd=os.open(name,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=directory)
            info=os.fstat(fd)
            if (not stat.S_ISREG(info.st_mode) or info.st_uid!=os.geteuid()
                    or stat.S_IMODE(info.st_mode)!=0o400 or info.st_size>_MAX):
                raise RecordError('guard evidence file ownership/type/bound invalid')
            yield fd
        except OSError:
            raise RecordError('guard evidence file unavailable') from None
        finally:
            if fd is not None:os.close(fd)

    def _records(self,directory,binding,key):
        names=[];count=0
        with os.scandir(directory) as entries:
            for entry in entries:
                count+=1
                if count>4096:raise RecordError('guard evidence directory capacity exceeded')
                if entry.name.startswith(key+'-') and entry.name.endswith('.json'):
                    names.append(entry.name)
                    if len(names)>256:raise RecordError('guard evidence history capacity exceeded')
        records=[]
        for name in sorted(names):
            match=re.fullmatch(re.escape(key)+r'-(observed|removed)-([a-f0-9]{64})[.]json',name)
            if match is None:raise RecordError('guard evidence filename invalid')
            with self._file(directory,name) as fd:raw=os.read(fd,_MAX+1)
            if len(raw)>_MAX or hashlib.sha256(raw).hexdigest()!=match[2]:
                raise RecordError('guard evidence checksum mismatch')
            try:record=json.loads(raw)
            except (ValueError,UnicodeError,RecursionError):raise RecordError('guard evidence encoding invalid') from None
            if (not isinstance(record,dict) or set(record)!={'version','binding','stage','observation'}
                    or type(record['version']) is not int or record['version']!=1
                    or safe_payload(record['binding'])!=safe_payload(binding) or record['stage']!=match[1]
                    or safe_payload(record).encode()+b'\n'!=raw):
                raise RecordError('guard evidence record identity invalid')
            self._validate(binding,record['stage'],record['observation'])
            records.append({**record,'reference':name,'sha256':match[2]})
        return records,count

    def read(self,binding):
        key=self._binding(binding)
        with self._directory() as directory:
            records,_=self._records(directory,binding,key)
            for item in records:
                with self._file(directory,item['reference']) as fd:os.fsync(fd)
            os.fsync(directory)
            return records

    def append(self,binding,stage,observation):
        key=self._binding(binding);self._validate(binding,stage,observation)
        record={'version':1,'binding':binding,'stage':stage,'observation':observation}
        raw=safe_payload(record).encode()+b'\n'
        if len(raw)>_MAX:raise RecordError('guard evidence exceeds bound')
        digest=hashlib.sha256(raw).hexdigest();name=key+'-'+stage+'-'+digest+'.json'
        with self._directory(write=True) as directory:
            previous,count=self._records(directory,binding,key)
            if stage=='observed' and observation['exit_status'] is not None:
                for item in previous:
                    old=item['observation']
                    if (item['stage']=='observed' and old['exit_status'] is not None
                            and (old['exit_status']!=observation['exit_status'] or old['ended_at']!=observation['ended_at'])):
                        raise RecordError('known original exit/end cannot be replaced')
            if any(item['reference']==name for item in previous):
                with self._file(directory,name) as fd:os.fsync(fd)
                os.fsync(directory)
                return {'reference':name,'sha256':digest}
            # Reserve staging AND final names so a publication interruption
            # retaining the staging link cannot exceed the readable scan bound.
            if len(previous)>=256 or count>=4095:
                raise RecordError('guard evidence prospective capacity exceeded')
            temporary='.stage-'+secrets.token_hex(16);fd=None;created=False
            try:
                fd=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=directory)
                created=True
                remaining=memoryview(raw)
                while remaining:
                    written=os.write(fd,remaining)
                    if written<=0:raise RecordError('guard evidence write incomplete')
                    remaining=remaining[written:]
                os.fchmod(fd,0o400);os.fsync(fd);os.close(fd);fd=None
                os.link(temporary,name,src_dir_fd=directory,dst_dir_fd=directory,follow_symlinks=False)
                os.unlink(temporary,dir_fd=directory);temporary=None
                os.fsync(directory)
            finally:
                if fd is not None:os.close(fd)
                if temporary is not None and created:
                    try:os.unlink(temporary,dir_fd=directory)
                    except FileNotFoundError:pass
            return {'reference':name,'sha256':digest}
