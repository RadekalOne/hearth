"""Audit requirements only: no credential scan, native consumer or absence claim."""
from dataclasses import replace
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

from hearth2.store import RecordError, safe_payload


class CredentialPolicyTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('hearth2.credential_policy'),'credential policy missing')
        from hearth2 import credential_policy
        self.module=credential_policy
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.repo=Path(self.tmp.name);self.repo.chmod(0o700)
        self.value={'version':1,'kind':'hearth2-credential-audit-requirements-v1','image_id':'sha256:'+'a'*64,
            'native_profile_sha256':'b'*64,'rootfs_audit_manifest_sha256':'c'*64,
            'consumer_audit_manifest_sha256':'d'*64,'parser_closure_sha256':'e'*64,
            'audit_authority_reference':'private:independent-auditor',
            'limits':{'sources':4096,'bytes':67108864,'consumers':32,'seconds':5}}

    def artifact(self,value=None,raw=None):
        raw=raw if raw is not None else (safe_payload(value if value is not None else self.value)+'\n').encode()
        digest=hashlib.sha256(raw).hexdigest();path=self.repo/(digest+'.json')
        path.write_bytes(raw);path.chmod(0o400);return digest,path

    def load(self,value=None):
        digest,path=self.artifact(value)
        return self.module.CredentialAuditRequirements.load(self.repo,digest)

    def test_loads_exact_canonical_pinned_immutable_requirements(self):
        policy=self.load()
        self.assertEqual(policy.manifest(),self.value)
        self.assertEqual(policy.sha256,hashlib.sha256((safe_payload(self.value)+'\n').encode()).hexdigest())
        self.assertEqual(policy.require_scope(self.value['image_id'],None,'b'*64,policy.sha256),
            ('image-rootfs','image-environment','image-native-consumers'))

    def test_container_scope_adds_every_required_family_without_exemptions(self):
        policy=self.load()
        self.assertEqual(policy.require_scope(self.value['image_id'],'f'*64,'b'*64,policy.sha256),
            ('image-rootfs','image-environment','image-native-consumers','container-rootfs',
             'container-configuration','container-native-consumers','container-mount-sources'))

    def test_wrong_image_profile_enrollment_or_nonimmutable_container_refuses(self):
        policy=self.load()
        for image,cid,profile,enrolled in [('sha256:'+'f'*64,None,'b'*64,policy.sha256),
                (self.value['image_id'],'name','b'*64,policy.sha256),
                (self.value['image_id'],None,'f'*64,policy.sha256),
                (self.value['image_id'],None,'b'*64,'f'*64)]:
            with self.assertRaises(RecordError):policy.require_scope(image,cid,profile,enrolled)

    def test_missing_unknown_or_noncanonical_fields_are_refused(self):
        for field in self.value:
            value={**self.value};del value[field]
            with self.assertRaises(RecordError):self.load(value)
        for changes in [{'version':True},{'version':2},{'kind':'native-provider-auto-detect'},
                        {'image_id':'latest'},{'complete':True},{'credential_entries':0},
                        {'audit_authority_reference':'   '},{'parser_closure_sha256':'unknown'}]:
            with self.assertRaises(RecordError):self.load({**self.value,**changes})

    def test_limits_are_strict_typed_and_bounded_not_disable_switches(self):
        for field in ['sources','bytes','consumers','seconds']:
            for bad in [True,0,-1,1.5,10**20]:
                value={**self.value,'limits':{**self.value['limits'],field:bad}}
                with self.assertRaises(RecordError):self.load(value)
        with self.assertRaises(RecordError):self.load({**self.value,'limits':{**self.value['limits'],'ignore_unreadable':True}})

    def test_noncanonical_json_symlink_and_writable_artifacts_are_refused(self):
        digest,path=self.artifact(raw=json.dumps(self.value,indent=2).encode())
        with self.assertRaises(RecordError):self.module.CredentialAuditRequirements.load(self.repo,digest)
        digest,path=self.artifact();path.chmod(0o600)
        with self.assertRaises(RecordError):self.module.CredentialAuditRequirements.load(self.repo,digest)
        path.chmod(0o400);path.rename(self.repo/'target');path.symlink_to('target')
        with self.assertRaises(RecordError):self.module.CredentialAuditRequirements.load(self.repo,digest)

    def test_direct_object_rebinding_and_mutable_limits_are_refused(self):
        policy=self.load()
        with self.assertRaises(RecordError):replace(policy,image_id='sha256:'+'f'*64)
        with self.assertRaises(RecordError):replace(policy,limits=list(policy.limits))
        output=policy.manifest();output['limits']['seconds']=1
        self.assertEqual(policy.manifest(),self.value)

    def test_requirements_never_emit_inventory_or_absence_authority(self):
        policy=self.load()
        self.assertFalse(hasattr(policy,'observe'))
        self.assertFalse(hasattr(policy,'scan'))
        for field in ['complete','credential_entries','states','observed_at','references']:
            self.assertNotIn(field,policy.manifest())


if __name__=='__main__':unittest.main()
