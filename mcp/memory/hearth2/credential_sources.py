"""Bounded synthetic source accounting. Never a physical inventory/absence port.

No I/O, discovery, credential resolution, collector success schema or start
authority. All physical coverage families remain unresolved in EVERY result.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
import math
import re
import time

from .credential_policy import CredentialAuditRequirements
from .creation import _digest
from .mcode_config import MCodeConfigParser, SelectionHypothesis, _SOURCES, _yaml, _schema
from .mcode_oauth import MCodeOAuthParser, _OAUTH, _PROJECTION
from .minimax_consumer import MiniMaxConsumerParser, _CORE, _load
from .root_commands import _container
from .store import RecordError


SOURCE_KINDS=('pi-auth','oauth-store','oauth-state','projection-namespaced',
    'projection-legacy','projection-shared','lease-capability','account-identity',
    'shared-selector','scope-marker','legacy-scope-marker','region-selector',
    'legacy-encrypted','mcode-config','host-model-ref','mcp-consumers','environment')
_OAUTH_KINDS=('oauth-store','oauth-state')+tuple(k for k in SOURCE_KINDS if k.startswith('projection-'))
_CONFIG_KINDS=('mcode-config','host-model-ref')
_MATERIAL=('literal_fields','empty_fields','environment_fields','command_fields',
    'environment_references','oauth_records','access_tokens','refresh_tokens',
    'identity_fields','authorization_fields','configured_key_fields','stored_header_fields',
    'host_key_fields','unknown_records','unknown_sections','unparsed_config_fields','unparsed_model_ref_fields',
    'primary_metadata_unknown','expiry_mismatches','scope_alerts','projection_mismatches','conditional_sources')
_ID=re.compile(r'[A-Za-z0-9_-]{1,64}',re.ASCII)


def _refuse():
    raise RecordError('unsupported credential source accounting packet') from None


def _opaque(value):
    return type(value) is str and _ID.fullmatch(value) is not None


def _reference(value):
    return type(value) is str and 0<len(value)<=1024 and all(32<=ord(c)<=126 for c in value) and bool(value.strip())


def _instant(value):
    # Validate the nested object BEFORE invoking caller-controlled tzinfo code.
    if type(value) is not datetime or type(value.tzinfo) is not timezone:_refuse()
    return value


@dataclass(frozen=True,slots=True,repr=False)
class SourceContext:
    image_id:str
    container_id:str|None
    assembly_sha256:str
    policy_sha256:str


@dataclass(frozen=True,slots=True,repr=False)
class SourceRequirement:
    source_id:str
    kind:str
    family:str
    group_id:str|None=None
    primary_group_id:str|None=None


@dataclass(frozen=True,slots=True,repr=False)
class OAuthSourceGroup:
    group_id:str
    data_directory_id:str
    build_env:str
    region:str
    account:str


@dataclass(frozen=True,slots=True,repr=False)
class SelectionSourceGroup:
    group_id:str
    hypothesis:SelectionHypothesis


@dataclass(frozen=True,slots=True,repr=False)
class SourceManifest:
    context:SourceContext
    audit:CredentialAuditRequirements
    entries:tuple
    oauth_groups:tuple=()
    selection_groups:tuple=()


@dataclass(frozen=True,slots=True,repr=False)
class SourceObservation:
    context:SourceContext
    source_id:str
    kind:str
    status:str
    observed_at:datetime
    reference:str
    raw:bytes|None=None


@dataclass(frozen=True,slots=True)
class SourceAccountingSummary:
    required_sources:int
    observed_sources:int
    parsed_sources:int
    absent_sources:int
    unscanned_sources:int
    unreadable_sources:int
    unsupported_sources:int
    material_counts:tuple
    unaccounted_by_family:tuple
    unresolved_coverage_families:tuple


def _context(context):
    if (type(context) is not SourceContext or type(context.image_id) is not str
            or not context.image_id.startswith('sha256:') or not _digest(context.image_id[7:])
            or type(context.assembly_sha256) is not str or not _digest(context.assembly_sha256)
            or type(context.policy_sha256) is not str or not _digest(context.policy_sha256)):_refuse()
    if context.container_id is not None:
        if type(context.container_id) is not str:_refuse()
        _container(context.container_id)


def _manifest(manifest):
    if type(manifest) is not SourceManifest or type(manifest.audit) is not CredentialAuditRequirements:_refuse()
    _context(manifest.context)
    audit=manifest.audit
    if (any(type(getattr(audit,k)) is not str for k in ('sha256','image_id','native_profile_sha256',
            'rootfs_audit_manifest_sha256','consumer_audit_manifest_sha256','parser_closure_sha256',
            'audit_authority_reference')) or type(audit.limits) is not tuple or len(audit.limits)!=4
            or any(type(p) is not tuple or len(p)!=2 or type(p[0]) is not str or type(p[1]) is not int
                   for p in audit.limits)):_refuse()
    audit.__post_init__()  # Revalidate even explicitly constructed policy objects.
    families=audit.require_scope(manifest.context.image_id,manifest.context.container_id,
        manifest.context.assembly_sha256,manifest.context.policy_sha256)
    limits=dict(audit.limits)
    if (type(manifest.entries) is not tuple or not 0<len(manifest.entries)<min(256,limits['sources'])
            or type(manifest.oauth_groups) is not tuple or type(manifest.selection_groups) is not tuple
            or len(manifest.entries)+len(manifest.oauth_groups)+len(manifest.selection_groups)
                >=min(64,limits['consumers'])):_refuse()
    oauth={};selection={}
    for g in manifest.oauth_groups:
        if (type(g) is not OAuthSourceGroup or not _opaque(g.group_id) or g.group_id in oauth
                or not _opaque(g.data_directory_id) or type(g.build_env) is not str
                or g.build_env not in ('dev','test','staging','prod') or type(g.region) is not str
                or g.region not in ('cn','en') or type(g.account) is not str
                or re.fullmatch(r'[A-Za-z0-9_-]{43}',g.account,re.ASCII) is None):_refuse()
        oauth[g.group_id]=g
    for g in manifest.selection_groups:
        if (type(g) is not SelectionSourceGroup or not _opaque(g.group_id) or g.group_id in selection
                or g.group_id in oauth or type(g.hypothesis) is not SelectionHypothesis):_refuse()
        g.hypothesis.__post_init__()
        selection[g.group_id]=g
    entries={};roles={}
    for e in manifest.entries:
        if (type(e) is not SourceRequirement or not _opaque(e.source_id) or e.source_id in entries
                or type(e.kind) is not str or e.kind not in SOURCE_KINDS
                or type(e.family) is not str or e.family not in families):_refuse()
        if e.kind in _OAUTH_KINDS+_CONFIG_KINDS:
            groups=oauth if e.kind in _OAUTH_KINDS else selection
            if not _opaque(e.group_id) or e.group_id not in groups or (e.group_id,e.kind) in roles:_refuse()
            roles[e.group_id,e.kind]=e.source_id
        elif e.group_id is not None:_refuse()
        if e.kind.startswith('projection-'):
            if e.primary_group_id is not None and (not _opaque(e.primary_group_id) or e.primary_group_id!=e.group_id):_refuse()
        elif e.primary_group_id is not None:_refuse()
        entries[e.source_id]=e
    if {e.kind for e in manifest.entries}!=set(SOURCE_KINDS):_refuse()
    return families,limits,entries,roles,oauth,selection


def _observations(observations,context,entries,begin,now,byte_limit):
    if type(observations) is not tuple or len(observations)>len(entries):_refuse()
    result={};size=0
    for o in observations:
        if (type(o) is not SourceObservation or not _opaque(o.source_id) or o.source_id in result
                or o.source_id not in entries or type(o.kind) is not str or o.kind!=entries[o.source_id].kind
                or type(o.status) is not str or o.status not in ('present','absent','unreadable','unscanned')
                or not _reference(o.reference)):_refuse()
        _context(o.context)
        if o.context!=context:_refuse()
        observed=_instant(o.observed_at)
        if not begin<=observed<=now or (now-observed).total_seconds()>60:_refuse()
        if o.status=='present':
            if type(o.raw) is not bytes or not 0<len(o.raw)<65536:_refuse()
            size+=len(o.raw)
            if size>=byte_limit:_refuse()
        elif o.raw is not None:_refuse()
        result[o.source_id]=o
    return result


class CredentialSourceAccounting:
    def __init__(self,*,clock,monotonic=time.monotonic):
        self.clock=clock
        self.monotonic=monotonic

    def account(self,manifest,observations,*,begin):
        try:
            return self._account(manifest,observations,begin)
        except (RecordError,TypeError,ValueError,AttributeError,OverflowError):
            _refuse()

    def _account(self,manifest,observations,begin):
        start=self.monotonic()
        begin=_instant(begin);now=_instant(self.clock())
        if not begin<=now or (now-begin).total_seconds()>60:_refuse()
        families,limits,entries,roles,oauth,selection=_manifest(manifest)
        acquired=_observations(observations,manifest.context,entries,begin,now,min(1048576,limits['bytes']))
        status={key:('unsupported' if acquired[key].status=='present' else acquired[key].status)
                if key in acquired else 'unscanned' for key in entries}
        material=dict.fromkeys(_MATERIAL,0)
        syntax=MiniMaxConsumerParser('0.4.1',_CORE)
        oauth_parser=MCodeOAuthParser('0.4.1',_OAUTH,_PROJECTION)
        config_parser=MCodeConfigParser(*_SOURCES)

        def data(source_id):
            packet=acquired.get(source_id)
            return packet.raw if packet is not None and packet.status=='present' else None

        def add(value,names):
            for name in names:material[name]+=getattr(value,name)

        for key,e in entries.items():
            value=data(key)
            if value is None:continue
            # Raw syntax counts do not depend on selection/partner availability.
            # Keep them even when joint effective-selection analysis must refuse.
            if e.kind=='mcode-config':
                try:counts,unknown=_schema(_yaml(value))
                except RecordError:continue
                material['configured_key_fields']+=counts[0]
                material['stored_header_fields']+=counts[1]
                material['unparsed_config_fields']+=counts[2]
                material['unknown_sections']+=unknown
                continue
            if e.kind=='host-model-ref':
                try:ref=_load(value)
                except RecordError:continue
                material['host_key_fields']+=int(type(ref.get('api_key')) is str)
                material['unparsed_model_ref_fields']+=len(ref.keys()-{'provider','model_id','api_key','base_url'})
                continue
            if e.kind not in ('pi-auth','environment'):continue
            try:
                summary=syntax.pi_auth_json(value) if e.kind=='pi-auth' else syntax.environment_json(value)
            except RecordError:continue
            add(summary,('literal_fields','empty_fields','environment_fields','command_fields',
                'environment_references','oauth_records','access_tokens','refresh_tokens','unknown_records'))
            if summary.unknown_records==0:status[key]='parsed'

        def oauth_alerts(summary):
            material['expiry_mismatches']+=int(summary.expiry_mismatch is True)
            material['scope_alerts']+=int(summary.record_missing_required_scope is True)+int(summary.state_scope_mismatch is True)
            material['scope_alerts']+=summary.extra_scope_fields or 0

        for group_id,group in oauth.items():
            store=roles.get((group_id,'oauth-store'));state=roles.get((group_id,'oauth-state'))
            auth_raw=data(store);state_raw=data(state)
            primary=None
            options=dict(build_env=group.build_env,region=group.region,account=group.account,
                         now_ms=int(now.timestamp()*1000))
            if auth_raw is not None and state_raw is not None:
                try:primary=oauth_parser.store_json(auth_raw,state_raw,**options)
                except RecordError:pass
                else:
                    status[store]=status[state]='parsed'
                    add(primary,('access_tokens','refresh_tokens','identity_fields','authorization_fields'))
                    oauth_alerts(primary)
            for kind in _OAUTH_KINDS[2:]:
                key=roles.get((group_id,kind));value=data(key)
                if value is None:continue
                e=entries[key]
                try:projection=oauth_parser.projection_json(value,source_kind=kind.split('-',1)[1])
                except RecordError:continue
                add(projection,('access_tokens','refresh_tokens','identity_fields','authorization_fields'))
                if primary is not None and e.primary_group_id==group_id:
                    try:compared=oauth_parser.compare_projection(auth_raw,state_raw,value,
                        source_kind=kind.split('-',1)[1],**options)
                    except RecordError:material['primary_metadata_unknown']+=1
                    else:
                        material['projection_mismatches']+=int(compared.matches_primary is False)
                        oauth_alerts(compared)
                        if compared.matches_primary is True and compared.expiry_mismatch is not None:status[key]='parsed'
                        else:material['primary_metadata_unknown']+=int(compared.expiry_mismatch is None)
                else:material['primary_metadata_unknown']+=1

        for group_id,group in selection.items():
            key=roles.get((group_id,'mcode-config'));host=roles.get((group_id,'host-model-ref'))
            config_raw=data(key);host_raw=data(host)
            if config_raw is None:continue
            use_host=group.hypothesis.selection_source=='host-model-ref'
            if use_host and host_raw is None:continue
            try:summary=config_parser.analyze(config_raw,group.hypothesis,host_raw if use_host else None)
            except RecordError:continue
            material['conditional_sources']+=1+int(use_host)
            # Conditional source analysis is always unsupported for complete
            # consumer accounting: no actual resolver/account/HTTP provenance.

        end=self.monotonic();finished=_instant(self.clock())
        if (type(start) not in (int,float) or type(end) not in (int,float)
                or not math.isfinite(start) or not math.isfinite(end)
                or not 0<=end-start<limits['seconds'] or finished<now
                or (finished-begin).total_seconds()>60):_refuse()
        return SourceAccountingSummary(len(entries),len(acquired),
            *(sum(v==name for v in status.values()) for name in ('parsed','absent','unscanned','unreadable','unsupported')),
            tuple(material.items()),tuple((family,sum(status[k] in ('unscanned','unreadable','unsupported')
                for k,e in entries.items() if e.family==family)) for family in families),tuple(families))
