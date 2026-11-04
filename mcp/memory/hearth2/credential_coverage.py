"""Pure compact-absence core over SUPPLIED evidence, not an acquisition port.

Requirements and two-pass facts must later come from independently enrolled
acquisition. No filesystem, parser, credential resolution, complete universe or
physical authority is supplied here. Every physical family stays unresolved.
"""
from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
import stat

from .credential_sources import SourceContext, SOURCE_KINDS, _context, _instant, _opaque
from .store import RecordError


_NONFILE=('environment','host-model-ref','mcp-consumers')
_AUTH=('oauth-store','oauth-state')
_CLI=('projection-namespaced','scope-marker','account-identity')
_STATUSES=('present','absent','unreadable','unsupported','unscanned')
_ENTRY_KINDS=('regular','directory','symlink','socket','fifo','device','unknown')


def _refuse():
    raise RecordError('unsupported compact coverage input') from None


def _path(value,*,empty=True):
    if (type(value) is not tuple or not (0 if empty else 1)<=len(value)<=8
            or any(type(v) is not str or not 0<len(v)<=128 or v in ('.','..')
                   or any(not 33<=ord(c)<=126 or c in '/\\' for c in v) for v in value)):_refuse()


def _number(value,minimum=0):
    if type(value) is not int or not minimum<=value<(1<<64):_refuse()


@dataclass(frozen=True,slots=True,repr=False)
class CoverageScope:
    context:SourceContext
    root_id:str
    batch_id:str
    round_id:str
    root_mount_id:int


@dataclass(frozen=True,slots=True,repr=False)
class CoverageSource:
    source_id:str
    kind:str
    path:tuple|None


@dataclass(frozen=True,slots=True,repr=False)
class DirectoryEntry:
    name:str
    kind:str
    links:int=1


@dataclass(frozen=True,slots=True,repr=False)
class DirectorySnapshot:
    scope:CoverageScope
    path:tuple
    mount_id:int
    device:int
    inode:int
    mode:int
    uid:int
    gid:int
    links:int
    mtime_ns:int
    ctime_ns:int
    observed_at:datetime
    entries:tuple


@dataclass(frozen=True,slots=True,repr=False)
class AbsenceEvidence:
    first:DirectorySnapshot
    second:DirectorySnapshot


@dataclass(frozen=True,slots=True,repr=False)
class CoverageNode:
    scope:CoverageScope
    branch:tuple
    observed_at:datetime
    evidence:AbsenceEvidence


@dataclass(frozen=True,slots=True,repr=False)
class CoverageObservation:
    scope:CoverageScope
    source_id:str
    status:str
    observed_at:datetime
    absence_evidence:AbsenceEvidence|None=None


def _scope(value):
    if type(value) is not CoverageScope:_refuse()
    _context(value.context)
    if not all(_opaque(v) for v in (value.root_id,value.batch_id,value.round_id)):_refuse()
    _number(value.root_mount_id,1)


def _body(scope,sources,groups,source_limit,work_limit):
    _scope(scope)
    if (type(source_limit) is not int or not 1<=source_limit<=256
            or type(work_limit) is not int or not 1<=work_limit<=64
            or type(sources) is not tuple or not 0<len(sources)<source_limit
            or type(groups) is not tuple or len(groups)>=64):_refuse()
    ids=set();paths=set();rows=[]
    for source in sources:
        if (type(source) is not CoverageSource or not _opaque(source.source_id) or source.source_id in ids
                or type(source.kind) is not str or source.kind not in SOURCE_KINDS):_refuse()
        ids.add(source.source_id)
        if source.path is not None:
            _path(source.path,empty=False)
            if source.kind in _NONFILE or source.path in paths:_refuse()
            paths.add(source.path)
        rows.append((source.source_id,source.kind,source.path))
    group_ids=set();edges=0
    for group in groups:
        if (type(group) is not tuple or len(group)!=2 or not _opaque(group[0]) or group[0] in group_ids
                or type(group[1]) is not tuple or not 0<len(group[1])<256
                or any(not _opaque(v) or v not in ids for v in group[1])
                or len(set(group[1]))!=len(group[1])):_refuse()
        group_ids.add(group[0]);edges+=len(group[1])
        if edges>=512:_refuse()
    context=scope.context
    body=dict(version=1,kind='hearth2-supplied-coverage-requirements',
        context=(context.image_id,context.container_id,context.assembly_sha256,context.policy_sha256),
        scope=(scope.root_id,scope.batch_id,scope.round_id,scope.root_mount_id),sources=rows,
        groups=groups,source_limit=source_limit,work_limit=work_limit)
    encoded=json.dumps(body,sort_keys=True,separators=(',',':')).encode()
    if len(encoded)>=65536:_refuse()
    return encoded


@dataclass(frozen=True,slots=True,repr=False)
class CoverageRequirements:
    scope:CoverageScope
    sources:tuple
    groups:tuple
    source_limit:int
    work_limit:int
    sha256:str

    @classmethod
    def create(cls,scope,sources,groups=(),*,source_limit=256,work_limit=64):
        try:encoded=_body(scope,sources,groups,source_limit,work_limit)
        except (RecordError,TypeError,ValueError,AttributeError,OverflowError):_refuse()
        return cls(scope,sources,groups,source_limit,work_limit,hashlib.sha256(encoded).hexdigest())


@dataclass(frozen=True,slots=True)
class CoverageSummary:
    required_sources:int
    observed_sources:int
    present_sources:int
    absent_sources:int
    unreadable_sources:int
    unsupported_sources:int
    unscanned_sources:int
    physical_observations:int
    coverage_nodes:int
    covered_absent_sources:int
    accounting_work_units:int
    mixed_presence_groups:int
    source_statuses:tuple
    unresolved_coverage_families:tuple


def _fresh(moment,begin,now):
    value=_instant(moment)
    if not begin<=value<=now or (now-value).total_seconds()>60:_refuse()
    return value


def _snapshot(value,scope,begin,now):
    if type(value) is not DirectorySnapshot:_refuse()
    _scope(value.scope)
    if value.scope!=scope:_refuse()
    _path(value.path)
    for v in (value.mount_id,value.device,value.inode,value.links):_number(v,1)
    for v in (value.mode,value.uid,value.gid,value.mtime_ns,value.ctime_ns):_number(v)
    if value.mount_id!=scope.root_mount_id or value.mode>0o177777 or not stat.S_ISDIR(value.mode):_refuse()
    _fresh(value.observed_at,begin,now)
    if type(value.entries) is not tuple or len(value.entries)>=256:_refuse()
    names=[]
    for entry in value.entries:
        if type(entry) is not DirectoryEntry:_refuse()
        _path((entry.name,),empty=False)
        if type(entry.kind) is not str or entry.kind not in _ENTRY_KINDS:_refuse()
        _number(entry.links,1)
        if entry.kind not in ('regular','directory') or entry.kind=='regular' and entry.links!=1:_refuse()
        names.append(entry.name)
    if names!=sorted(names) or len({n.casefold() for n in names})!=len(names):_refuse()
    return (value.path,value.mount_id,value.device,value.inode,value.mode,value.uid,value.gid,
            value.links,value.mtime_ns,value.ctime_ns,value.entries)


def _proves(evidence,path,scope,begin,now,observed,witnesses):
    if type(evidence) is not AbsenceEvidence:_refuse()
    a,b=evidence.first,evidence.second
    facts=_snapshot(a,scope,begin,now)
    if facts!=_snapshot(b,scope,begin,now):_refuse()
    by_path,by_inode,missing_paths=witnesses
    identity=(a.mount_id,a.device,a.inode)
    if (a.path in by_path and by_path[a.path]!=facts
            or identity in by_inode and by_inode[identity]!=a.path):_refuse()
    by_path[a.path]=facts;by_inode[identity]=a.path
    # Bound the complete reconciliation graph, not just each directory tuple.
    # Charge two passes of each unique supplied directory's entries.
    if 2*sum(1+len(facts[-1]) for facts in by_path.values())>=256:_refuse()
    if not a.observed_at<=b.observed_at<=observed:_refuse()
    parent=a.path
    if len(parent)>=len(path) or path[:len(parent)]!=parent:_refuse()
    missing=path[len(parent)]
    if any(e.name.casefold()==missing.casefold() for e in a.entries):_refuse()
    missing_paths.add(parent+(missing,))


def _reconcile(witnesses,sources,status):
    by_path,_,missing_paths=witnesses
    exists={s.path for s in sources if s.path is not None
            and status[s.source_id] in ('present','unsupported','unreadable')}
    for path,facts in by_path.items():
        exists.add(path)
        exists.update(path+(entry.name,) for entry in facts[-1])
    # Match the same conservative case-fold rule as the individual proof check.
    exists={tuple(v.casefold() for v in path) for path in exists}
    for missing in missing_paths:
        prefix=tuple(v.casefold() for v in missing)
        if any(path[:len(prefix)]==prefix for path in exists):_refuse()
    # A full listing also excludes EVERY unlisted child, not just the child
    # selected to prove a particular leaf absent (e.g. an empty root vs cli-auth).
    for directory,facts in by_path.items():
        prefix=tuple(v.casefold() for v in directory)
        names={entry.name.casefold() for entry in facts[-1]}
        if any(len(path)>len(prefix) and path[:len(prefix)]==prefix
               and path[len(prefix)] not in names for path in exists):_refuse()


def _branch(value):
    _path(value,empty=False)
    if (len(value) not in (3,4) or value[0] not in ('auth','cli-auth')
            or value[1] not in ('dev','test','staging','prod') or value[2] not in ('cn','en')
            or len(value)==4 and (value[0]!='auth' or value[3]!='mcode-public')):_refuse()


class CoverageAccounting:
    def __init__(self,*,clock):self.clock=clock

    def account(self,requirements,observations,coverage_nodes,*,begin):
        try:return self._account(requirements,observations,coverage_nodes,begin)
        except (RecordError,TypeError,ValueError,AttributeError,OverflowError):_refuse()

    def _account(self,requirements,observations,coverage_nodes,begin):
        begin=_instant(begin);now=_instant(self.clock())
        if not begin<=now or (now-begin).total_seconds()>60:_refuse()
        if type(requirements) is not CoverageRequirements:_refuse()
        body=_body(requirements.scope,requirements.sources,requirements.groups,
                   requirements.source_limit,requirements.work_limit)
        if type(requirements.sha256) is not str or hashlib.sha256(body).hexdigest()!=requirements.sha256:_refuse()
        sources=requirements.sources;scope=requirements.scope
        if (type(observations) is not tuple or type(coverage_nodes) is not tuple
                or len(observations)>len(sources) or len(coverage_nodes)>len(sources)):_refuse()
        by_id={s.source_id:s for s in sources};status=dict.fromkeys(by_id,'unscanned');seen=set();covered=set()
        witnesses=({}, {}, set())
        for observation in observations:
            if type(observation) is not CoverageObservation:_refuse()
            _scope(observation.scope)
            if (observation.scope!=scope or not _opaque(observation.source_id)
                    or observation.source_id not in by_id or observation.source_id in seen
                    or type(observation.status) is not str or observation.status not in _STATUSES):_refuse()
            observed=_fresh(observation.observed_at,begin,now)
            if observation.status=='absent':
                path=by_id[observation.source_id].path
                if path is None:_refuse()
                _proves(observation.absence_evidence,path,scope,begin,now,observed,witnesses)
            elif observation.absence_evidence is not None:_refuse()
            seen.add(observation.source_id);status[observation.source_id]=observation.status
        for node in coverage_nodes:
            if type(node) is not CoverageNode:_refuse()
            _scope(node.scope)
            if node.scope!=scope:_refuse()
            _branch(node.branch);observed=_fresh(node.observed_at,begin,now)
            matches=[s for s in sources if s.path is not None and len(s.path)>len(node.branch)
                     and s.path[:len(node.branch)]==node.branch]
            allowed=_AUTH if node.branch[0]=='auth' else _CLI
            if not matches or any(s.kind not in allowed for s in matches):_refuse()
            for source in matches:
                if source.source_id in seen or source.source_id in covered:_refuse()
                _proves(node.evidence,source.path,scope,begin,now,observed,witnesses)
                covered.add(source.source_id);status[source.source_id]='absent'
        work=len(sources)-len(covered)+len(coverage_nodes)
        work+=sum(any(source not in covered for source in members) for _,members in requirements.groups)
        if work>=requirements.work_limit:_refuse()
        _reconcile(witnesses,sources,status)
        # Present acquisition facts have not been parsed here. A group with both
        # absence and retained presence remains mixed, never inferred empty.
        mixed=sum(any(status[v]=='absent' for v in members)
                  and any(status[v] in ('present','unsupported') for v in members)
                  for _,members in requirements.groups)
        families=('image-rootfs','image-environment','image-native-consumers')
        if scope.context.container_id is not None:
            families+=('container-rootfs','container-configuration','container-native-consumers','container-mount-sources')
        finish=_instant(self.clock())
        if finish<now or (finish-begin).total_seconds()>60:_refuse()
        return CoverageSummary(len(sources),len(seen)+len(covered),
            *(sum(v==kind for v in status.values()) for kind in _STATUSES),
            len(observations)+len(coverage_nodes),len(coverage_nodes),len(covered),work,mixed,
            tuple((i,s.kind,status[s.source_id]) for i,s in enumerate(sources)),families)
