from contextlib import closing
"""A11 graphs, corruption refusal and safe restore of active work."""
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import unittest
import threading
from unittest.mock import patch
from pathlib import Path
import test_hearth2_claims as fixtures
from hearth2.store import Store, Principal, RecordError
try:
    from hearth2.backup import export_record, restore_record
except ImportError:
    export_record=restore_record=None


class BackupTests(unittest.TestCase):
    def setUp(self):
        fixtures.ClaimTests.setUp(self)
        self.bundle=Path(self.tmp.name)/'backup.json'
        self.target=Path(self.tmp.name)/'restored.sqlite3'

    def export(self):
        self.assertIsNotNone(export_record,'versioned backup is not implemented')
        return export_record(self.path,self.bundle)

    def test_clean_process_restore_preserves_relationships_and_holds_active_work(self):
        claim=self.store.claim(self.controller,self.task['id'],expected_revision=1,request_id='active')
        before=self.store.snapshot();self.export()
        code='from hearth2.backup import restore_record;import sys;restore_record(sys.argv[1],sys.argv[2],controller_stopped=True)'
        env={**os.environ,'PYTHONPATH':str(Path(__file__).parents[1]/'mcp/memory')}
        done=subprocess.run([sys.executable,'-c',code,str(self.bundle),str(self.target)],env=env,capture_output=True,text=True)
        self.assertEqual(done.returncode,0,done.stderr)
        restored=Store(self.target,clock=lambda:self.time);after=restored.snapshot()
        for name in ['projects','plans','tasks','claims','runs','decisions','role_grants']:
            key='agent' if name=='role_grants' else 'id'
            self.assertEqual({r[key] for r in before[name]},{r[key] for r in after[name]})
        self.assertEqual(after['tasks'][0]['state'],'held')
        self.assertEqual(after['claims'][0]['state'],'held')
        self.assertEqual(after['runs'][0]['containment_state'],'unconfirmed')
        with self.assertRaises(RecordError):restored.renew(self.controller,claim,lease_until=claim['lease_until'])
        with self.assertRaises(RecordError):restored.claim(self.controller,self.task['id'],expected_revision=after['tasks'][0]['revision'],request_id='new')
        self.assertEqual(after['decisions'][0]['state'],'consumed')
        with closing(sqlite3.connect(self.target)) as db, db:self.assertEqual(db.execute('PRAGMA foreign_key_check').fetchall(),[])

    def test_pending_decision_is_held_and_approved_history_not_reactivated(self):
        draft=self.store.create_plan(self.rad,self.project['id'],{'content_ref':'new-pending-plan'})
        pending=self.store.create_decision(self.controller,draft['id'],intended_subject=self.rad.id,expires_at=(self.time+fixtures.timedelta(days=1)).isoformat())
        self.export();restore_record(self.bundle,self.target,controller_stopped=True)
        restored=Store(self.target,clock=lambda:self.time)
        d=next(d for d in restored.snapshot()['decisions'] if d['id']==pending['id'])
        self.assertEqual(d['state'],'held')
        with self.assertRaises(RecordError):restored.record_decision(self.rad,pending['id'],1,'approve','import-replay')

    def test_existing_target_and_running_controller_are_refused(self):
        self.export()
        with self.assertRaises(RecordError):restore_record(self.bundle,self.target,controller_stopped=False)
        self.target.write_bytes(b'keep-existing-data')
        with self.assertRaises((RecordError,FileExistsError)):restore_record(self.bundle,self.target,controller_stopped=True)
        self.assertEqual(self.target.read_bytes(),b'keep-existing-data')

    def test_corruption_unknown_version_and_duplicate_ids_never_publish(self):
        self.export();original=json.loads(self.bundle.read_text())
        variants=[]
        bad=json.loads(json.dumps(original));bad['manifest']['format_version']=99;variants.append(bad)
        bad=json.loads(json.dumps(original));bad['tables']['projects'][0]['title']='tampered';variants.append(bad)
        bad=json.loads(json.dumps(original));bad['tables']['projects'].append(bad['tables']['projects'][0]);self.rehash(bad);variants.append(bad)
        for n,value in enumerate(variants):
            bundle=self.bundle.with_name('bad'+str(n)+'.json');bundle.write_text(json.dumps(value))
            with self.subTest(n=n),self.assertRaises(RecordError):restore_record(bundle,self.target,controller_stopped=True)
            self.assertFalse(self.target.exists())

    @staticmethod
    def rehash(value):
        value['manifest']['counts']={k:len(v) for k,v in value['tables'].items()}
        raw=json.dumps(value['tables'],sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()
        value['manifest']['sha256']=hashlib.sha256(raw).hexdigest()

    def test_consistent_export_includes_all_records_and_refuses_overwrite(self):
        self.store.claim(self.controller,self.task['id'],expected_revision=1,request_id='active')
        manifest=self.export();value=json.loads(self.bundle.read_text())
        self.assertEqual(manifest['format_version'],1)
        self.assertEqual(len(value['tables']['tasks']),1)
        self.assertEqual(value['tables']['claims'][0]['run_id'],value['tables']['runs'][0]['id'])
        before=self.bundle.read_bytes()
        with self.assertRaises((RecordError,FileExistsError)):export_record(self.path,self.bundle)
        self.assertEqual(self.bundle.read_bytes(),before)

    def test_dangling_relationship_refused_even_with_valid_digest(self):
        self.export();value=json.loads(self.bundle.read_text())
        value['tables']['tasks'][0]['project_id']='missing-project';self.rehash(value)
        self.bundle.write_text(json.dumps(value))
        with self.assertRaises(RecordError):restore_record(self.bundle,self.target,controller_stopped=True)
        self.assertFalse(self.target.exists())

    def test_credential_field_in_legacy_raw_data_refuses_export(self):
        self.assertIsNotNone(export_record,'versioned backup is not implemented')
        with closing(sqlite3.connect(self.path)) as db, db:db.execute('UPDATE projects SET data=?',(json.dumps({'access_token':'not-for-backup'}),))
        with self.assertRaises(RecordError):export_record(self.path,self.bundle)
        self.assertFalse(self.bundle.exists())

    def test_empty_source_path_is_not_created(self):
        self.assertIsNotNone(export_record,'versioned backup is not implemented')
        missing=Path(self.tmp.name)/'absent.sqlite3'
        with self.assertRaises((RecordError,sqlite3.DatabaseError)):export_record(missing,self.bundle)
        self.assertFalse(missing.exists())

    def test_export_is_one_snapshot_while_wal_writer_commits_new_project(self):
        self.assertIsNotNone(export_record,'versioned backup is not implemented')
        import hearth2.backup as backup
        with closing(sqlite3.connect(self.path)) as db, db:db.execute('PRAGMA journal_mode=WAL')
        start=threading.Event();done=threading.Event();errors=[]
        def writer():
            try:
                if not start.wait(5):raise RuntimeError('export did not reach snapshot boundary')
                p=self.store.create_project(self.rad,{'title':'Concurrent'})
                plan=self.store.create_plan(self.rad,p['id'],{'content_ref':'new-plan','actions':self.action_manifest})
                self.store.create_task(self.rad,{**self.payload,'project_id':p['id'],'plan_id':plan['id']})
            except BaseException as e:errors.append(e)
            finally:done.set()
        original=sqlite3.connect
        def observed_connection(*args,**kwargs):
            db=original(*args,**kwargs)
            if args and '?mode=ro' in str(args[0]):
                def trace(sql):
                    if sql=='SELECT * FROM tasks':
                        start.set()
                        if not done.wait(5):errors.append(RuntimeError('concurrent writer timed out'))
                db.set_trace_callback(trace)
            return db
        thread=threading.Thread(target=writer);thread.start()
        try:
            with patch.object(backup.sqlite3,'connect',observed_connection):self.export()
        finally:
            start.set();thread.join(10)
        self.assertEqual(errors,[])
        value=json.loads(self.bundle.read_text())
        projects={r['id'] for r in value['tables']['projects']}
        plans={r['id'] for r in value['tables']['plans']}
        self.assertTrue(all(t['project_id'] in projects and t['plan_id'] in plans for t in value['tables']['tasks']))
        self.assertEqual(len(value['tables']['tasks']),1)
        self.assertEqual(len(self.store.snapshot()['tasks']),2)

    def test_interrupted_restore_leaves_no_published_or_staged_database(self):
        self.export()
        import hearth2.backup as backup
        with patch.object(backup,'publish',side_effect=RuntimeError('injected publication failure')):
            with self.assertRaises(RuntimeError):restore_record(self.bundle,self.target,controller_stopped=True)
        self.assertFalse(self.target.exists())
        self.assertEqual(list(self.target.parent.glob('.hearth2-restore-*')),[])

    def test_impossible_accepted_task_is_rejected_even_with_valid_checksum(self):
        self.export();value=json.loads(self.bundle.read_text())
        value['tables']['tasks'][0]['state']='accepted'
        self.rehash(value);self.bundle.write_text(json.dumps(value))
        with self.assertRaises(RecordError):restore_record(self.bundle,self.target,controller_stopped=True)
        self.assertFalse(self.target.exists())
