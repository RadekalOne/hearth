"""Inactive conditional body-read verification. No native parser or live wiring.

Only explicitly requested mapped fixture files are read, twice. Bytes are hashed
in the acquisition stack and discarded; no bytes/hashes/paths leave this port.
Supplied root bindings are not independent physical enrollment or custody proof.
"""
from dataclasses import dataclass
import hashlib
import os
import stat

from .data_dir_metadata import (DirectoryMetadataCapture,_Work,_Failed,_signature,
    _mount_id,_refuse)
from .credential_coverage import CoverageSummary
from .store import RecordError


@dataclass(frozen=True,slots=True)
class DirectoryFileResult:
    state:str
    reason:str|None
    summary:CoverageSummary|None
    metadata_work:int
    bytes_read:int
    read_attempts:int
    file_outcomes:tuple


class _FileWork(_Work):
    def __init__(self,limit,seconds,monotonic,max_bytes):
        super().__init__(limit,seconds,monotonic)
        self.max_bytes=max_bytes;self.bytes_read=0;self.read_attempts=0

    def read(self,fd,size):
        self.tick(1);self.read_attempts+=1
        raw=os.read(fd,min(size,self.max_bytes-self.bytes_read))
        self.bytes_read+=len(raw)
        if self.bytes_read>=self.max_bytes:raise _Failed('budget-acquisition')
        self.tick()
        return raw


class DirectoryFileCapture(DirectoryMetadataCapture):
    def __init__(self,view=None,*,max_bytes=1048576,**kwargs):
        super().__init__(view,**kwargs);self.max_bytes=max_bytes

    def _candidate(self,parent,name,expected,work):
        work.tick(1)
        target=opened=None
        try:
            target=os.open(name,os.O_PATH|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=parent)
            value=os.fstat(target)
            if _signature(value)!=expected:raise _Failed('changed')
            if (not stat.S_ISREG(value.st_mode) or value.st_nlink!=1
                    or value.st_uid!=self.view.uid or value.st_gid!=self.view.gid
                    or value.st_mode&0o022 or _mount_id(target)!=self.view.scope.root_mount_id):
                return 'unreadable',('type',None)
            opened=os.open('/proc/self/fd/'+str(target),os.O_RDONLY|os.O_NONBLOCK|os.O_CLOEXEC)
            if (_signature(os.fstat(opened))!=expected
                    or _mount_id(opened)!=self.view.scope.root_mount_id):raise _Failed('changed')
            digest=hashlib.sha256();length=0
            while length<65537:
                raw=work.read(opened,min(8192,65537-length))
                if not raw:break
                digest.update(raw);length+=len(raw)
            if (any(_signature(os.fstat(fd))!=expected for fd in (target,opened))
                    or _signature(os.stat(name,dir_fd=parent,follow_symlinks=False))!=expected
                    or any(_mount_id(fd)!=self.view.scope.root_mount_id for fd in (target,opened))):
                raise _Failed('changed')
            if length>=65536 or value.st_size>=65536:return 'unreadable',('oversize',None)
            if length!=value.st_size:return 'unreadable',('io',None)
            return 'present',(None,digest.digest())
        except PermissionError:return 'unreadable',('permission',None)
        except OSError:return 'unreadable',('io',None)
        finally:
            if opened is not None:os.close(opened)
            if target is not None:os.close(target)

    def capture(self,requirements,*,begin):
        try:
            if type(self.max_bytes) is not int or not 1<=self.max_bytes<=1048576:_refuse()
            self._validate(requirements,begin)
            work=_FileWork(self.max_entries,self.timeout_seconds,self.monotonic,self.max_bytes)
        except (RecordError,TypeError,ValueError,AttributeError,OverflowError):_refuse()
        try:
            a=self._pass(requirements,work);b=self._pass(requirements,work)
            summary=self._summarize(requirements,a,b,begin,work);work.tick()
            outcomes=tuple((i,summary.source_statuses[i][2],b[3].get(s.source_id,(None,))[0])
                           for i,s in enumerate(requirements.sources))
            return DirectoryFileResult('files-observed',None,summary,work.count,
                                       work.bytes_read,work.read_attempts,outcomes)
        except _Failed as exc:reason=exc.reason
        except OSError:reason='unavailable'
        except (RecordError,ValueError,TypeError,AttributeError,OverflowError):_refuse()
        return DirectoryFileResult('unscanned',reason,None,work.count,work.bytes_read,work.read_attempts,())
