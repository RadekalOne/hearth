"""Inactive conditional directory-metadata capture; no credential-body reads.

The supplied view binds a caller's expected fixture/root identity, NOT physical
host/image enrollment. This lower acquisition layer keeps every physical family
unresolved. No default view, discovery of homes, native parser or worker wiring.
"""
from dataclasses import dataclass
from datetime import datetime,timezone
import hashlib
import math
import os
from pathlib import PurePosixPath
import stat
import time

from .credential_coverage import (CoverageScope,CoverageRequirements,CoverageSummary,
    CoverageObservation,CoverageNode,DirectorySnapshot,DirectoryEntry,AbsenceEvidence,
    CoverageAccounting,_scope,_body,_path,_branch)
from .credential_sources import _instant
from .store import RecordError


def _refuse():raise RecordError('unsupported directory metadata request') from None


class _Failed(Exception):
    def __init__(self,reason):self.reason=reason


def _mount_id(fd):
    with open('/proc/self/fdinfo/'+str(fd),'rb') as stream:raw=stream.read(8193)
    if len(raw)>8192:raise _Failed('unavailable')
    values=[line.split(b':',1)[1].strip() for line in raw.splitlines() if line.startswith(b'mnt_id:')]
    if len(values)!=1 or not values[0].isdigit() or int(values[0])<=0:raise _Failed('unavailable')
    return int(values[0])


def _signature(value):
    return tuple(getattr(value,k) for k in ('st_dev','st_ino','st_mode','st_uid','st_gid',
        'st_nlink','st_size','st_mtime_ns','st_ctime_ns'))


def _mapped(path):
    if not path:return True
    if path in (('auth',),('cli-auth',),('run',),('preferences',)):return True
    if path[0] not in ('auth','cli-auth') or len(path) not in (2,3,4):return False
    if path[1] not in ('dev','test','staging','prod'):return False
    if len(path)>=3 and path[2] not in ('cn','en'):return False
    return len(path)<4 or path[0]=='auth' and path[3]=='mcode-public'


@dataclass(frozen=True,slots=True,repr=False)
class RootDirectoryView:
    scope:CoverageScope
    root_path:str
    device:int
    inode:int
    ctime_ns:int
    uid:int
    gid:int


@dataclass(frozen=True,slots=True)
class DirectoryMetadataResult:
    state:str
    reason:str|None
    summary:CoverageSummary|None
    metadata_work:int


class _Work:
    def __init__(self,limit,seconds,monotonic):
        self.limit=limit;self.seconds=seconds;self.monotonic=monotonic;self.count=0
        self.start=self.monotonic()
        if type(self.start) not in (int,float) or not math.isfinite(self.start):_refuse()

    def tick(self,amount=0):
        self.count+=amount
        now=self.monotonic()
        if (type(now) not in (int,float) or not math.isfinite(now) or not 0<=now-self.start<self.seconds
                or self.count>=self.limit):raise _Failed('budget-acquisition')


class DirectoryMetadataCapture:
    def __init__(self,view=None,*,clock=lambda:datetime.now(timezone.utc),monotonic=time.monotonic,
                 max_entries=256,timeout_seconds=5):
        self.view=view;self.clock=clock;self.monotonic=monotonic
        self.max_entries=max_entries;self.timeout_seconds=timeout_seconds

    def _candidate(self,parent,name,expected,work):
        """Metadata-only by default; private extension never changes this API."""
        return 'present',None

    def _validate(self,requirements,begin):
        if os.name!='posix' or not hasattr(os,'O_PATH') or type(self.view) is not RootDirectoryView:_refuse()
        v=self.view;_scope(v.scope)
        if (type(v.root_path) is not str or not 0<len(v.root_path)<=4096 or '\x00' in v.root_path
                or any(ord(c)<32 for c in v.root_path) or not v.root_path.startswith('/')
                or str(PurePosixPath(v.root_path))!=v.root_path
                or len(PurePosixPath(v.root_path).parts)>64):_refuse()
        if any(type(x) is not int or not minimum<=x<(1<<64) for x,minimum in
               ((v.device,1),(v.inode,1),(v.ctime_ns,0),(v.uid,0),(v.gid,0))):_refuse()
        if (type(self.max_entries) is not int or not 1<=self.max_entries<=256
                or type(self.timeout_seconds) is not int or not 1<=self.timeout_seconds<=10
                or type(requirements) is not CoverageRequirements):_refuse()
        raw=_body(requirements.scope,requirements.sources,requirements.groups,
            requirements.source_limit,requirements.work_limit)
        if requirements.scope!=v.scope:_refuse()
        if type(requirements.sha256) is not str or hashlib.sha256(raw).hexdigest()!=requirements.sha256:_refuse()
        now=_instant(self.clock());begin=_instant(begin)
        if not begin<=now or (now-begin).total_seconds()>60:_refuse()
        return now

    def _root(self):
        flags=os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC|os.O_NONBLOCK
        fd=os.open('/',flags)
        try:
            for name in PurePosixPath(self.view.root_path).parts[1:]:
                new=os.open(name,flags,dir_fd=fd);os.close(fd);fd=new
            st=os.fstat(fd);v=self.view
            if ((st.st_dev,st.st_ino,st.st_ctime_ns,st.st_uid,st.st_gid)!=(v.device,v.inode,v.ctime_ns,v.uid,v.gid)
                    or not stat.S_ISDIR(st.st_mode) or st.st_mode&0o022
                    or _mount_id(fd)!=v.scope.root_mount_id):raise _Failed('binding')
            return fd
        except BaseException:
            os.close(fd);raise

    def _pass(self,requirements,work):
        root=self._root();fds={():root};directories={};stats={};facts={};unknown=set();measurements={}
        scope=self.view.scope

        def directory(path):
            if path in directories:return directories[path]
            if path in unknown:return None
            fd=fds[path];before=os.fstat(fd);work.tick(1);entries=[]
            try:
                with os.scandir(fd) as listing:
                    for named in listing:
                        work.tick(1)
                        target=os.open(named.name,os.O_PATH|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=fd)
                        try:
                            value=os.fstat(target);mount=_mount_id(target)
                            mode=value.st_mode
                            kind=('regular' if stat.S_ISREG(mode) else 'directory' if stat.S_ISDIR(mode)
                                  else 'symlink' if stat.S_ISLNK(mode) else 'socket' if stat.S_ISSOCK(mode)
                                  else 'fifo' if stat.S_ISFIFO(mode) else 'device')
                            if mount!=scope.root_mount_id:kind='unknown'
                            entries.append(DirectoryEntry(named.name,kind,value.st_nlink))
                            stats[path+(named.name,)]=_signature(value)
                            if _signature(os.stat(named.name,dir_fd=fd,follow_symlinks=False))!=_signature(value):
                                raise _Failed('changed')
                        finally:os.close(target)
                if _signature(os.fstat(fd))!=_signature(before):raise _Failed('changed')
            except OSError:
                unknown.add(path);return None
            entries=tuple(sorted(entries,key=lambda e:e.name))
            result=DirectorySnapshot(scope,path,scope.root_mount_id,before.st_dev,before.st_ino,
                before.st_mode,before.st_uid,before.st_gid,before.st_nlink,
                before.st_mtime_ns,before.st_ctime_ns,_instant(self.clock()),entries)
            directories[path]=result;stats[path]=_signature(before)
            return result

        def parent(path):
            current=()
            for name in path:
                value=directory(current)
                if value is None:return None,None
                if not any(e.name==name for e in value.entries):return 'absent',current
                child=current+(name,)
                if child not in fds:
                    fd=fds[current]
                    try:
                        target=os.open(name,os.O_PATH|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=fd)
                        try:
                            st=os.fstat(target)
                            if (not stat.S_ISDIR(st.st_mode) or st.st_uid!=self.view.uid or st.st_gid!=self.view.gid
                                    or st.st_mode&0o022 or _mount_id(target)!=scope.root_mount_id):return None,None
                            opened=None
                            try:
                                opened=os.open('/proc/self/fd/'+str(target),
                                    os.O_RDONLY|os.O_DIRECTORY|os.O_NONBLOCK|os.O_CLOEXEC)
                                if (_signature(os.fstat(opened))!=_signature(st)
                                        or _mount_id(opened)!=scope.root_mount_id):raise _Failed('changed')
                                fds[child]=opened;opened=None
                            finally:
                                if opened is not None:os.close(opened)
                        finally:os.close(target)
                    except OSError:return None,None
                current=child
            return 'directory',current

        try:
            directory(())
            for source in requirements.sources:
                work.tick()
                if source.path is None or not _mapped(source.path[:-1]):
                    facts[source.source_id]=('unscanned',None);continue
                state,path=parent(source.path[:-1])
                if state is None:facts[source.source_id]=('unscanned',None);continue
                value=directory(path)
                if value is None:facts[source.source_id]=('unscanned',None);continue
                if state=='absent':facts[source.source_id]=('absent',path);continue
                entry=next((e for e in value.entries if e.name==source.path[-1]),None)
                if entry is None:facts[source.source_id]=('absent',path)
                elif entry.kind=='regular' and entry.links==1:
                    state,measurement=self._candidate(fds[path],source.path[-1],stats[source.path],work)
                    facts[source.source_id]=(state,None)
                    measurements[source.source_id]=measurement
                else:facts[source.source_id]=('unsupported',None)
            for path,fd in fds.items():
                if path in stats and _signature(os.fstat(fd))!=stats[path]:raise _Failed('changed')
                if path:
                    if _signature(os.stat(path[-1],dir_fd=fds[path[:-1]],follow_symlinks=False))!=_signature(os.fstat(fd)):
                        raise _Failed('changed')
            for source in requirements.sources:
                if measurements.get(source.source_id) is not None:
                    work.tick(1)
                    parent_fd=fds[source.path[:-1]]
                    target=os.open(source.path[-1],os.O_PATH|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=parent_fd)
                    try:
                        if (_signature(os.fstat(target))!=stats[source.path]
                                or _mount_id(target)!=scope.root_mount_id
                                or _signature(os.stat(source.path[-1],dir_fd=parent_fd,follow_symlinks=False))!=stats[source.path]):
                            raise _Failed('changed')
                    finally:os.close(target)
            check=self._root()
            try:
                if _signature(os.fstat(check))!=_signature(os.fstat(root)):raise _Failed('changed')
            finally:os.close(check)
            return directories,stats,facts,measurements
        finally:
            for fd in reversed(tuple(fds.values())):os.close(fd)

    @staticmethod
    def _safe(snapshot,path):
        try:
            names=[]
            for entry in snapshot.entries:
                _path((entry.name,),empty=False);names.append(entry.name.casefold())
                if entry.kind not in ('regular','directory') or entry.kind=='regular' and entry.links!=1:return False
            if len(names)!=len(set(names)) or len(snapshot.path)>=len(path):return False
            return path[len(snapshot.path)].casefold() not in names
        except RecordError:return False

    def _summarize(self,requirements,a,b,begin,work):
        da,sa,fa,ma=a;db,sb,fb,mb=b
        def snapshot_key(d):
            return {p:(v.mount_id,v.device,v.inode,v.mode,v.uid,v.gid,v.links,v.mtime_ns,v.ctime_ns,v.entries)
                    for p,v in d.items()}
        if sa!=sb or fa!=fb or ma!=mb or snapshot_key(da)!=snapshot_key(db):raise _Failed('changed')
        observed=_instant(self.clock());observations={};nodes=[];covered=set()
        for source in requirements.sources:
            state,parent=fa[source.source_id];evidence=None
            if state=='absent':
                if not self._safe(da[parent],source.path) or not self._safe(db[parent],source.path):state='unscanned'
                else:evidence=AbsenceEvidence(da[parent],db[parent])
            observations[source.source_id]=CoverageObservation(requirements.scope,source.source_id,state,observed,evidence)
        branches=sorted({s.path[:-1] for s in requirements.sources if s.path is not None},
                        key=lambda path:(len(path),path))
        for branch in branches:
            try:_branch(branch)
            except RecordError:continue
            allowed=('oauth-store','oauth-state') if branch[0]=='auth' else ('projection-namespaced','scope-marker','account-identity')
            members=[s for s in requirements.sources if s.path is not None and len(s.path)>len(branch)
                     and s.path[:len(branch)]==branch]
            if (not members or any(s.source_id in covered or s.kind not in allowed
                                   or observations[s.source_id].status!='absent' for s in members)
                    or len({fa[s.source_id][1] for s in members})!=1):continue
            nodes.append(CoverageNode(requirements.scope,branch,observed,observations[members[0].source_id].absence_evidence))
            covered.update(s.source_id for s in members)
        cost=len(requirements.sources)-len(covered)+len(nodes)
        cost+=sum(any(s not in covered for s in members) for _,members in requirements.groups)
        if cost>=requirements.work_limit:raise _Failed('budget-accounting')
        remaining=tuple(v for key,v in observations.items() if key not in covered)
        work.tick()
        try:return CoverageAccounting(clock=self.clock).account(requirements,remaining,tuple(nodes),begin=begin)
        except RecordError:raise _Failed('changed') from None

    def capture(self,requirements,*,begin):
        try:
            self._validate(requirements,begin)
            work=_Work(self.max_entries,self.timeout_seconds,self.monotonic)
        except (RecordError,TypeError,ValueError,AttributeError,OverflowError):_refuse()
        try:
            a=self._pass(requirements,work);b=self._pass(requirements,work)
            summary=self._summarize(requirements,a,b,begin,work)
            work.tick()
            return DirectoryMetadataResult('metadata-observed',None,summary,work.count)
        except _Failed as exc:return DirectoryMetadataResult('unscanned',exc.reason,None,work.count)
        except OSError:return DirectoryMetadataResult('unscanned','unavailable',None,work.count)
        except (RecordError,ValueError,TypeError,AttributeError,OverflowError):_refuse()
