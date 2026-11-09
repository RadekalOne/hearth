"""Pure declared enrollment contracts. Pins are not authenticated enrollment.

No filesystem, discovery, native execution or runtime authority. A helper receives
one bounded root slice, never the complete policy or configured-source universe.
"""
from dataclasses import asdict,dataclass
import hashlib
import json

from .credential_sources import SourceContext,_context,_opaque,_reference
from .creation import _digest
from .store import RecordError


def _refuse():raise RecordError('unsupported data directory enrollment') from None


def _hash(value):
    if type(value) is not str or not _digest(value):_refuse()


def _path(value):
    if (type(value) is not str or not 1<len(value)<=4096 or not value.startswith('/')
            or any(not 33<=ord(c)<=126 or c=='\\' for c in value)
            or any(p in ('','.','..') for p in value.split('/')[1:])
            or len(value.split('/'))>64):_refuse()


def _number(value,low=0,high=(1<<64)-1):
    if type(value) is not int or not low<=value<=high:_refuse()


def _raw(value):return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode('ascii')


@dataclass(frozen=True,slots=True,repr=False)
class NamespaceEnrollment:
    build_env:str
    region:str
    account:str|None


@dataclass(frozen=True,slots=True,repr=False)
class RootEnrollment:
    root_id:str
    path:str
    mount_id:int
    device:int|None
    inode:int|None
    ctime_ns:int|None
    uid:int
    gid:int
    namespaces:tuple
    parent_device:int
    parent_inode:int
    absent:bool=False


def _root(root):
    if type(root) is not RootEnrollment:_refuse()
    if not _opaque(root.root_id):_refuse()
    _path(root.path)
    for value in (root.mount_id,root.parent_device,root.parent_inode):_number(value,1)
    for value in (root.uid,root.gid):_number(value)
    if type(root.absent) is not bool:_refuse()
    if root.absent:
        if any(v is not None for v in (root.device,root.inode,root.ctime_ns)):_refuse()
    else:
        _number(root.device,1);_number(root.inode,1);_number(root.ctime_ns)
    if type(root.namespaces) is not tuple or len(root.namespaces)>8:_refuse()
    seen=set()
    for ns in root.namespaces:
        if (type(ns) is not NamespaceEnrollment or type(ns.build_env) is not str
                or ns.build_env not in ('dev','test','staging','prod') or type(ns.region) is not str
                or ns.region not in ('cn','en')):_refuse()
        if ns.account is not None:
            if (type(ns.account) is not str or len(ns.account)!=43
                    or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-' for c in ns.account)):_refuse()
        key=(ns.build_env,ns.region)
        if key in seen:_refuse()
        seen.add(key)


_LIMITS=(('discovery_to_composition_seconds',120),('round_seconds',10),
         ('max_entries',256),('max_bytes',1048576),('max_candidates',64),('logical_source_limit',256))


def _fields(context,roots,configured_sources,authority_reference,helper_sha256,parser_sha256,limits):
    from .mcode_source_map import MAP_SHA256
    _context(context)
    if type(roots) is not tuple or not 1<=len(roots)<=8:_refuse()
    ids=set();paths=[]
    for root in roots:
        _root(root)
        if root.root_id in ids:_refuse()
        ids.add(root.root_id)
        path=root.path.lower()
        if any(path==p or path.startswith(p+'/') or p.startswith(path+'/') for p in paths):_refuse()
        paths.append(path)
    if type(configured_sources) is not tuple or not 1<=len(configured_sources)<=32:_refuse()
    seen=set()
    for item in configured_sources:
        if type(item) is not tuple or len(item)!=2 or not _opaque(item[0]) or item[0] in seen:_refuse()
        _hash(item[1]);seen.add(item[0])
    if not _reference(authority_reference):_refuse()
    _hash(helper_sha256);_hash(parser_sha256)
    if type(limits) is not tuple or len(limits)!=len(_LIMITS):_refuse()
    for value,(_,maximum) in zip(limits,_LIMITS):_number(value,1,maximum)
    return dict(version=1,kind='hearth2-declared-data-directory-policy-v1',context=asdict(context),
        roots=[asdict(root) for root in roots],configured_sources=configured_sources,
        authority_reference=authority_reference,helper_sha256=helper_sha256,parser_sha256=parser_sha256,
        source_map_sha256=MAP_SHA256,limits=dict(zip((x[0] for x in _LIMITS),limits)))


@dataclass(frozen=True,slots=True,repr=False)
class RootPolicySlice:
    context:SourceContext
    policy_sha256:str
    source_map_sha256:str
    helper_sha256:str
    parser_sha256:str
    root:RootEnrollment
    limits:tuple
    binding_sha256:str

    def encode(self):
        try:
            from .mcode_source_map import MAP_SHA256
            _context(self.context);_root(self.root)
            for v in (self.policy_sha256,self.source_map_sha256,self.helper_sha256,self.parser_sha256,self.binding_sha256):_hash(v)
            if self.source_map_sha256!=MAP_SHA256 or type(self.limits) is not tuple or len(self.limits)!=6:_refuse()
            for v,(_,maximum) in zip(self.limits,_LIMITS):_number(v,1,maximum)
            value=asdict(self);del value['binding_sha256']
            raw=_raw(value)
            if len(raw)>=16384 or hashlib.sha256(raw).hexdigest()!=self.binding_sha256:_refuse()
            return raw
        except (RecordError,TypeError,ValueError,AttributeError,OverflowError):_refuse()


@dataclass(frozen=True,slots=True,repr=False)
class DataDirectoryPolicy:
    context:SourceContext
    roots:tuple
    configured_sources:tuple
    authority_reference:str
    helper_sha256:str
    parser_sha256:str
    discovery_to_composition_seconds:int
    round_seconds:int
    max_entries:int
    max_bytes:int
    max_candidates:int
    logical_source_limit:int
    document:bytes
    sha256:str

    @classmethod
    def create(cls,*,context,roots,configured_sources,authority_reference,helper_sha256,parser_sha256,
               discovery_to_composition_seconds,round_seconds,max_entries,max_bytes,max_candidates,logical_source_limit):
        try:
            limits=(discovery_to_composition_seconds,round_seconds,max_entries,max_bytes,max_candidates,logical_source_limit)
            raw=_raw(_fields(context,roots,configured_sources,authority_reference,helper_sha256,parser_sha256,limits))
            if len(raw)>=65536:_refuse()
            return cls(context,roots,configured_sources,authority_reference,helper_sha256,parser_sha256,
                *limits,raw,hashlib.sha256(raw).hexdigest())
        except (RecordError,TypeError,ValueError,AttributeError,OverflowError):_refuse()

    @classmethod
    def decode(cls,document,*,expected_sha256):
        try:
            _hash(expected_sha256)
            if (type(document) is not bytes or not 0<len(document)<65536
                    or hashlib.sha256(document).hexdigest()!=expected_sha256):_refuse()
            value=json.loads(document)
            if type(value) is not dict:_refuse()
            ctx=SourceContext(**value['context'])
            roots=[]
            for item in value['roots']:
                item=dict(item);item['namespaces']=tuple(NamespaceEnrollment(**ns) for ns in item['namespaces'])
                roots.append(RootEnrollment(**item))
            policy=cls.create(context=ctx,roots=tuple(roots),configured_sources=tuple(tuple(x) for x in value['configured_sources']),
                authority_reference=value['authority_reference'],helper_sha256=value['helper_sha256'],
                parser_sha256=value['parser_sha256'],**value['limits'])
            # Exact canonical equality rejects duplicate JSON keys, unknown fields,
            # changed versions/map, coercions and alternate encodings.
            if policy.document!=document:_refuse()
            return policy
        except (RecordError,TypeError,ValueError,AttributeError,OverflowError,KeyError,RecursionError):_refuse()

    def root_slice(self,root_id,*,expected_sha256,context):
        try:
            _context(context);_hash(expected_sha256)
            if not _opaque(root_id):_refuse()
            values={k:getattr(self,k) for k in ('context','roots','configured_sources','authority_reference',
                'helper_sha256','parser_sha256',*(x[0] for x in _LIMITS))}
            checked=self.create(**values)
            if (type(self.document) is not bytes or type(self.sha256) is not str
                    or checked.document!=self.document or checked.sha256!=self.sha256
                    or self.sha256!=expected_sha256 or self.context!=context):_refuse()
            root=next((r for r in self.roots if r.root_id==root_id),None)
            if root is None:_refuse()
            from .mcode_source_map import MAP_SHA256
            limits=tuple(getattr(self,k) for k,_ in _LIMITS)
            fields=dict(context=self.context,policy_sha256=self.sha256,source_map_sha256=MAP_SHA256,
                helper_sha256=self.helper_sha256,parser_sha256=self.parser_sha256,root=root,limits=limits)
            binding=hashlib.sha256(_raw({k:asdict(v) if k in ('context','root') else v for k,v in fields.items()})).hexdigest()
            return RootPolicySlice(**fields,binding_sha256=binding)
        except (RecordError,TypeError,ValueError,AttributeError,OverflowError):_refuse()
