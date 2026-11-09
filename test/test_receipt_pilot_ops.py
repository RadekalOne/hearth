import unittest,tempfile,pathlib,json,hashlib,tarfile,io,sys
sys.path.insert(0,str(pathlib.Path(__file__).parents[1]/'ops/hearth2'))
import receipt_pilot_ops as ops

class PilotOpsTests(unittest.TestCase):
    def test_scope_and_retirement_preserve_other_fields(self):
        cfg={'services':{'hub':{'image':'candidate','restart':'no','environment':{'OTHER':'keep','HEARTH2_ENABLED':'true','HEARTH2_NOTICE_SESSIONS':'{}'},'ports':['127.0.0.1:8010:8010']},'unrelated':{'image':'untouched'}}}
        out=ops.fallback_config(cfg,'hub','fallback')
        self.assertEqual(out['services']['unrelated'],cfg['services']['unrelated']);self.assertEqual(out['services']['hub']['environment']['OTHER'],'keep')
        self.assertEqual(out['services']['hub']['restart'],'unless-stopped');self.assertEqual(out['services']['hub']['environment']['HEARTH2_ENABLED'],'false')
        self.assertEqual(ops.immutable_config(out,'hub'),ops.immutable_config(cfg,'hub'))
        expected={'pilot':[ops.digest(b'secret')]}
        self.assertEqual(ops.retired_tokens({'pilot':'secret','other':'preserved'},expected),{'other':'preserved'})
        with self.assertRaises(ValueError):ops.retired_tokens({'pilot':'unexpected','other':'preserved'},expected)
    def test_backup_restore_guards_and_security_fence(self):
        with tempfile.TemporaryDirectory() as directory:
            root=pathlib.Path(directory);data=root/'data';data.mkdir();(data/'ordinary').write_bytes(b'fixture')
            (data/'notice-session-credentials.sqlite3').write_bytes(b'security-a');cfg=root/'compose.json';cfg.write_text('{}')
            archive=root/'backup.tar';manifest=ops.make_backup(data,cfg,archive,assert_quiescent=lambda:None)
            output=root/'restored';ops.restore_backup(archive,manifest['archive_sha256'],output,security_source=data)
            self.assertEqual((output/'data/ordinary').read_bytes(),b'fixture')
            with self.assertRaises(ValueError):ops.restore_backup(archive,'0'*64,root/'bad',security_source=data)
            with self.assertRaises(ValueError):ops.restore_backup(archive,manifest['archive_sha256'],output,security_source=data)
            (data/'notice-session-credentials.sqlite3').write_bytes(b'security-newer')
            with self.assertRaises(ValueError):ops.restore_backup(archive,manifest['archive_sha256'],root/'stale',security_source=data)
            self.assertFalse((root/'stale').exists())
    def test_traversal_refused_even_with_matching_archive_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            root=pathlib.Path(directory);archive=root/'bad.tar'
            with tarfile.open(archive,'w') as out:
                info=tarfile.TarInfo('../outside');info.size=1;out.addfile(info,io.BytesIO(b'x'))
            with self.assertRaises(ValueError):ops.restore_backup(archive,ops.file_digest(archive),root/'restored',security_source=root)
            self.assertFalse((root/'restored').exists())
    def test_rehearsal_plan_cannot_address_shared_service(self):
        import os,time
        with tempfile.TemporaryDirectory() as directory:
            root=pathlib.Path(directory);root.chmod(0o700);data=root/'data';data.mkdir();cfg=root/'compose.json';cfg.write_text('{}')
            p={'format':'receipt-pilot-v1','mode':'rehearsal','approval_ref':'fixture only','root':str(root),'config':str(cfg),'data':str(data),'project':'hearth-project-hub','service':'hub','container':'hearth-project-hub-hub-1','candidate_image':'sha256:'+'1'*64,'fallback_image':'sha256:'+'2'*64,'boot_id':pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'deadline_monotonic':time.monotonic()+10}
            plan=root/'plan.json';plan.write_text(json.dumps(p));plan.chmod(0o600)
            with self.assertRaises(ValueError):ops.load_plan(plan,ops.file_digest(plan))
    def test_symlink_member_and_duplicate_members_refused(self):
        for variant in ('symlink','duplicate'):
            with self.subTest(variant=variant),tempfile.TemporaryDirectory() as directory:
                root=pathlib.Path(directory);archive=root/'bad.tar'
                with tarfile.open(archive,'w') as out:
                    item=tarfile.TarInfo('data/file');item.size=1
                    if variant=='symlink':item.type=tarfile.SYMTYPE;item.linkname='/etc/passwd';item.size=0;out.addfile(item)
                    else:out.addfile(item,io.BytesIO(b'x'));out.addfile(item,io.BytesIO(b'y'))
                with self.assertRaises(ValueError):ops.restore_backup(archive,ops.file_digest(archive),root/'restore',security_source=root)
    def test_guard_drift_invokes_scoped_fail_closed_stop(self):
        import time
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as directory:
            root=pathlib.Path(directory);path=root/'plan.json';path.write_text('{}')
            p={'root':str(root),'deadline_monotonic':time.monotonic()+2}
            with patch.object(ops,'load_plan',return_value=p),patch.object(ops,'file_digest',return_value='changed'),patch.object(ops,'fail_closed_stop',create=True) as stop:
                with self.assertRaises(ValueError):ops.guard(path,'expected')
                stop.assert_called_once()
    def test_idempotence_cannot_return_success_after_reactivation(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as directory:
            root=pathlib.Path(directory);(root/'cutoff-result.json').write_text(json.dumps({'plan_sha256':'expected'}))
            p={'root':str(root),'data':str(root),'retire':{},'fallback_image':'fallback','service':'hub'}
            cfg={'services':{'hub':{'image':'candidate','environment':{'HEARTH2_ENABLED':'true'}}}}
            with patch.object(ops,'load_plan',return_value=p),patch.object(ops,'verify_target',return_value=({'Image':'candidate','State':{'Running':True}},cfg)),patch.object(ops,'fail_closed_stop',create=True):
                with self.assertRaises(ValueError):ops.cutoff(root/'plan.json','expected')
    def test_unknown_alias_of_pilot_secret_requires_maintenance(self):
        with self.assertRaises(ValueError):ops.retired_tokens({'pilot':'secret','unknown-alias':'secret'},{'pilot':[ops.digest(b'secret')]})
