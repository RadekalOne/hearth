"""Inactive audit REQUIREMENTS only; never a scan or credential absence proof.

The independently enrolled policy digest pins required audited manifests and
parser closure. Their actual provenance, exhaustive source acquisition, supported
consumer semantics and bounded scanner remain separate unimplemented gates.
"""
from dataclasses import dataclass
import hashlib

from .creation import _digest
from .guard_evidence import GuardEvidenceStore
from .guard_service import RootGuardArtifacts
from .root_commands import _container
from .store import RecordError, safe_payload


_IMAGE_SCOPE=('image-rootfs','image-environment','image-native-consumers')
_CONTAINER_SCOPE=_IMAGE_SCOPE+('container-rootfs','container-configuration',
                             'container-native-consumers','container-mount-sources')
_LIMITS={'sources':65536,'bytes':1073741824,'consumers':64,'seconds':10}
_HASHES=('native_profile_sha256','rootfs_audit_manifest_sha256',
         'consumer_audit_manifest_sha256','parser_closure_sha256')


@dataclass(frozen=True)
class CredentialAuditRequirements:
    sha256: str
    image_id: str
    native_profile_sha256: str
    rootfs_audit_manifest_sha256: str
    consumer_audit_manifest_sha256: str
    parser_closure_sha256: str
    audit_authority_reference: str
    limits: tuple

    def __post_init__(self):
        try:
            if (type(self.limits) is not tuple or len(self.limits)!=4
                    or any(type(pair) is not tuple or len(pair)!=2 for pair in self.limits)
                    or len(dict(self.limits))!=4 or not _digest(self.sha256)
                    or hashlib.sha256(self.encode(self.manifest())).hexdigest()!=self.sha256):
                raise ValueError('immutable requirements')
        except (TypeError,ValueError):raise RecordError('audit requirements must match immutable digest') from None

    def manifest(self):
        return {'version':1,'kind':'hearth2-credential-audit-requirements-v1','image_id':self.image_id,
                **{k:getattr(self,k) for k in _HASHES},'audit_authority_reference':self.audit_authority_reference,
                'limits':dict(self.limits)}

    @staticmethod
    def encode(value):
        fields={'version','kind','image_id','audit_authority_reference','limits',*_HASHES}
        if (type(value) is not dict or set(value)!=fields or type(value['version']) is not int or value['version']!=1
                or value['kind']!='hearth2-credential-audit-requirements-v1'
                or type(value['image_id']) is not str or not value['image_id'].startswith('sha256:') or not _digest(value['image_id'][7:])
                or any(not _digest(value[k]) for k in _HASHES)
                or type(value['audit_authority_reference']) is not str or not value['audit_authority_reference'].strip()
                or len(value['audit_authority_reference'])>4096
                or type(value['limits']) is not dict or set(value['limits'])!=set(_LIMITS)
                or any(type(value['limits'][k]) is not int or not 1<=value['limits'][k]<=maximum for k,maximum in _LIMITS.items())):
            raise RecordError('unsupported complete audit requirements schema')
        return (safe_payload(value)+'\n').encode()

    @classmethod
    def load(cls,repository,digest):
        with GuardEvidenceStore(repository)._directory() as directory:
            value=RootGuardArtifacts(repository)._artifact(directory,digest)
        cls.encode(value)
        return cls(digest,value['image_id'],*(value[k] for k in _HASHES),value['audit_authority_reference'],
                   tuple(sorted(value['limits'].items())))

    def require_scope(self,image_id,container_id,native_profile_sha256,enrolled_policy_sha256):
        # Matching hashes express required authority, never successful auditing.
        if (image_id!=self.image_id or native_profile_sha256!=self.native_profile_sha256
                or enrolled_policy_sha256!=self.sha256):
            raise RecordError('original image/profile/independently enrolled audit policy required')
        if container_id is not None:_container(container_id)
        return _IMAGE_SCOPE if container_id is None else _CONTAINER_SCOPE
