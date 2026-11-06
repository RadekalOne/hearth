"""Conditional single-root policy pin, NOT independently authenticated enrollment.

Pure construction seals declared view/map/parser metadata. Execution requires a
separate supplied expected digest and still performs the actual bounded reads.
No discovery, policy repository, host authentication or physical scanner wiring.
"""
from dataclasses import asdict,dataclass
from datetime import datetime,timezone
import hashlib
import json
import time

from .creation import _digest
from .credential_coverage import _scope
from .data_dir_accounting import DirectorySourceCapture,_source_bindings
from .data_dir_metadata import RootDirectoryView
from .store import RecordError


def _refuse():raise RecordError('unsupported conditional directory scope') from None


def _document(view,requirements,manifest,max_entries,max_bytes,timeout_seconds):
    limits=_source_bindings(requirements,manifest)
    if type(view) is not RootDirectoryView:_refuse()
    _scope(view.scope)
    if view.scope!=requirements.scope:_refuse()
    path=view.root_path
    if (type(path) is not str or not 1<len(path)<=4096 or not path.startswith('/')
            or any(not 33<=ord(c)<=126 or c=='\\' for c in path)
            or any(part in ('','.','..') for part in path.split('/')[1:])
            or len(path.split('/'))>64):_refuse()
    if any(type(value) is not int or not minimum<=value<(1<<64) for value,minimum in
           ((view.device,1),(view.inode,1),(view.ctime_ns,0),(view.uid,0),(view.gid,0))):_refuse()
    if (type(max_entries) is not int or not 1<=max_entries<=256
            or type(max_bytes) is not int or not 1<=max_bytes<=min(1048576,limits['bytes'])
            or type(timeout_seconds) is not int or not 1<=timeout_seconds<=min(10,limits['seconds'])):_refuse()
    # Batch/round are fresh request identities, not persistent root enrollment.
    # Every other acquisition, grouping, interpretation and limit input is pinned.
    value=dict(version=1,kind='hearth2-conditional-directory-scope-v1',
        source_map='conditional-mcode-four-role-v1',
        view=(view.scope.root_id,view.scope.root_mount_id,path,view.device,view.inode,
              view.ctime_ns,view.uid,view.gid),
        manifest=asdict(manifest),
        sources=tuple((s.source_id,s.kind,s.path) for s in requirements.sources),
        groups=requirements.groups,source_limit=requirements.source_limit,
        work_limit=requirements.work_limit,
        limits=(max_entries,max_bytes,timeout_seconds))
    raw=json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode('ascii')
    if len(raw)>=32768:_refuse()
    return raw


@dataclass(frozen=True,slots=True,repr=False)
class DirectoryScopePolicy:
    sha256:str
    document:bytes
    max_entries:int
    max_bytes:int
    timeout_seconds:int

    @classmethod
    def create(cls,view,requirements,manifest,*,max_entries,max_bytes,timeout_seconds):
        try:
            raw=_document(view,requirements,manifest,max_entries,max_bytes,timeout_seconds)
            return cls(hashlib.sha256(raw).hexdigest(),raw,max_entries,max_bytes,timeout_seconds)
        except (RecordError,TypeError,ValueError,AttributeError,OverflowError):_refuse()


class ScopedDirectoryCapture:
    def __init__(self,policy=None,*,expected_sha256=None,
                 clock=lambda:datetime.now(timezone.utc),monotonic=time.monotonic):
        self.policy=policy;self.expected_sha256=expected_sha256
        self.clock=clock;self.monotonic=monotonic

    def capture(self,view,requirements,manifest,*,begin):
        try:
            policy=self.policy
            if (type(policy) is not DirectoryScopePolicy or type(self.expected_sha256) is not str
                    or not _digest(self.expected_sha256) or type(policy.sha256) is not str
                    or policy.sha256!=self.expected_sha256 or type(policy.document) is not bytes
                    or not len(policy.document)<32768
                    or hashlib.sha256(policy.document).hexdigest()!=self.expected_sha256):_refuse()
            raw=_document(view,requirements,manifest,policy.max_entries,policy.max_bytes,policy.timeout_seconds)
            if raw!=policy.document:_refuse()
            return DirectorySourceCapture(view,clock=self.clock,monotonic=self.monotonic,
                max_entries=policy.max_entries,max_bytes=policy.max_bytes,
                timeout_seconds=policy.timeout_seconds).capture(requirements,manifest,begin=begin)
        except (RecordError,TypeError,ValueError,AttributeError,OverflowError):_refuse()
