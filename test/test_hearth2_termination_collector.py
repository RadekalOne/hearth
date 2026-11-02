"""Historical root exit + fresh read-only synthetic OS queries, real SQLite."""
from datetime import timedelta
import copy
import hashlib
import importlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch
import test_hearth2_root_guard as fixtures
import test_hearth2_creation_binding as creation
from hearth2.store import Store,RecordError
from hearth2.dispatch import DispatchRegistry
from hearth2.launch import LaunchCoordinator
from hearth2.backup import export_record,restore_record


class TerminationCollectorTests(unittest.TestCase):
    def setUp(self):
        fixtures.RootGuardTests.setUp(self)
        self.registration=self.bindings.consume_armed(self.claim,self.binding,
            proof=creation.CreationBindingTests.arm_proof(self,self.binding))
        self.guard.enforce(self.binding)
        self.time+=timedelta(seconds=901);self.kernel.steps=[]
        self.assertIsNotNone(importlib.util.find_spec('hearth2.termination_collector'),'outside collector missing')
        self.collector_type=importlib.import_module('hearth2.termination_collector').RootTerminationCollector
        self.collector=self.make()

    def make(self,refs=None):
        return self.collector_type(self.kernel,self.daemon,self.evidence_store,
            host_identity=lambda:self.host,clock=lambda:self.time,
            classification_evidence=['root:explicit-recovery-classification'] if refs is None else refs)

    def collect(self):return self.collector.inspect_termination(self.binding)

    def launcher(self,store=None):
        return LaunchCoordinator(DispatchRegistry(store or self.store,self.controller),self.collector)

    def test_historical_exit_uses_new_query_times_and_does_not_repeat_guard_actions(self):
        known=self.evidence_store.read(self.binding)[0]['observation']['observed_at']
        kills=self.kernel.kills;before=self.store.snapshot();packet=self.collect()
        self.assertEqual(packet['observation']['exit_status'],137)
        self.assertEqual(packet['observation']['ended_at'],self.binding['at'])
        self.assertGreater(packet['observation']['observed_at'],known)
        self.assertEqual(packet['observation']['observed_at'],self.time.isoformat())
        self.assertEqual(self.kernel.steps,['absent','state'])
        self.assertEqual(self.kernel.kills,kills);self.assertFalse(self.daemon.disarmed)
        self.assertEqual(self.store.snapshot(),before)
        self.assertNotEqual(self.collect()['recovery_id'],packet['recovery_id'])

    def test_strict_launch_recovery_releases_known_failed_attempt_once(self):
        result=self.launcher().recover(self.claim['run_id'],outcome='failed')
        self.assertEqual(result['registration']['phase'],'released')
        self.assertEqual(result['run']['exit_status'],137)
        self.assertEqual(result['task']['state'],'ready');self.assertEqual(result['task']['attempts'],1)
        self.assertFalse(self.daemon.disarmed)
        steps=list(self.kernel.steps)
        with self.assertRaises(RecordError):self.launcher().recover(self.claim['run_id'],outcome='failed')
        self.assertEqual(self.kernel.steps,steps)

    def test_historical_removed_receipt_cannot_replace_current_id_absence(self):
        self.daemon.present=True;before=self.store.snapshot()
        with self.assertRaises(RecordError):self.launcher().recover(self.claim['run_id'],outcome='failed')
        self.assertEqual(self.store.snapshot(),before)

    def test_historical_empty_receipt_cannot_replace_current_empty_parent(self):
        self.kernel.populated=True
        with self.assertRaises(RecordError):self.collect()
        self.assertFalse(self.daemon.disarmed)

    def test_thawed_parent_is_not_independently_quiescent(self):
        self.kernel.frozen=False
        with self.assertRaises(RecordError):self.collect()

    def test_new_host_cannot_collect_or_release_original_host(self):
        self.host='2'*64;before=self.store.snapshot()
        with self.assertRaises(RecordError):self.launcher().recover(self.claim['run_id'],outcome='failed')
        self.assertEqual(self.kernel.steps,[]);self.assertEqual(self.store.snapshot(),before)

    def test_host_change_during_absence_query_refuses_packet(self):
        absent=self.daemon.absent
        def changed(container):
            value=absent(container);self.host='2'*64;return value
        with patch.object(self.daemon,'absent',side_effect=changed),self.assertRaises(RecordError):self.collect()

    def test_failed_absence_query_is_unknown_not_success(self):
        self.daemon.fail='absent'
        with self.assertRaises(RecordError):self.collect()

    def test_parent_populated_during_absence_query_cannot_release_using_earlier_empty(self):
        absent=self.daemon.absent;before=self.store.snapshot()
        def late_child(container):
            value=absent(container);self.kernel.populated=True;return value
        with patch.object(self.daemon,'absent',side_effect=late_child),self.assertRaises(RecordError):
            self.launcher().recover(self.claim['run_id'],outcome='failed')
        self.assertEqual(self.store.snapshot(),before)

    def test_slow_collection_does_not_refresh_old_cgroup_query_time(self):
        state=self.kernel.state
        def slow(parent):
            value=state(parent);self.time+=timedelta(seconds=61);return value
        with patch.object(self.kernel,'state',side_effect=slow),self.assertRaises(RecordError):self.collect()

    def test_clock_rollback_during_collection_refuses_instead_of_clamping(self):
        state=self.kernel.state
        def backward(parent):
            value=state(parent);self.time-=timedelta(seconds=1);return value
        with patch.object(self.kernel,'state',side_effect=backward),self.assertRaises(RecordError):self.collect()

    def test_missing_exit_evidence_remains_unknown_and_strict_recovery_stays_held(self):
        root=Path(self.tmp.name)/'empty-evidence';root.mkdir(mode=0o700)
        self.collector.evidence=self.evidence_store.__class__(root,clock=lambda:self.time)
        packet=self.collect();self.assertIsNone(packet['observation']['exit_status'])
        self.assertIsNone(packet['observation']['ended_at']);before=self.store.snapshot()
        with self.assertRaises(RecordError):self.launcher().recover(self.claim['run_id'],outcome='failed')
        self.assertEqual(self.store.snapshot(),before)

    def test_later_unknown_observation_does_not_erase_durable_known_exit(self):
        self.evidence_store.append(self.binding,'observed',{'observed_at':self.time.isoformat(),
            'exit_status':None,'ended_at':None})
        self.assertEqual(self.collect()['observation']['exit_status'],137)

    def test_conflicting_historical_known_exits_refuse_even_if_files_are_valid(self):
        records=self.evidence_store.read(self.binding);observed=next(x for x in records if x['stage']=='observed')
        body={k:copy.deepcopy(observed[k]) for k in ['version','binding','stage','observation']}
        body['observation']['exit_status']=1
        raw=json.dumps(body,sort_keys=True,separators=(',',':')).encode()+b'\n'
        key=observed['reference'].split('-observed-')[0]
        path=self.evidence_store.root/(key+'-observed-'+hashlib.sha256(raw).hexdigest()+'.json')
        path.write_bytes(raw);path.chmod(0o400)
        self.assertEqual(len(self.evidence_store.read(self.binding)),3)
        with self.assertRaises(RecordError):self.collect()

    def test_mixed_original_binding_from_evidence_port_refuses_packet(self):
        records=self.evidence_store.read(self.binding)
        records[0]['binding']={**self.binding,'host_id':'2'*64}
        with patch.object(self.evidence_store,'read',return_value=records),self.assertRaises(RecordError):self.collect()

    def test_corrupt_receipt_refuses_before_os_queries(self):
        path=next(self.evidence_store.root.glob('*.json'));path.chmod(0o600);path.write_text('{}');path.chmod(0o400)
        with self.assertRaises(RecordError):self.collect()
        self.assertEqual(self.kernel.steps,[])

    def test_epoch_change_during_inspection_is_fenced_by_strict_recovery(self):
        absent=self.daemon.absent;after=[]
        def changed(container):
            value=absent(container)
            with self.store.transaction() as db:db.execute("UPDATE record_meta SET restore_epoch='new-epoch' WHERE id=1")
            after.append(self.store.snapshot());return value
        with patch.object(self.daemon,'absent',side_effect=changed),self.assertRaises(RecordError):
            self.launcher().recover(self.claim['run_id'],outcome='failed')
        self.assertEqual(self.store.snapshot(),after[0])

    def test_generation_change_during_inspection_is_fenced_by_strict_recovery(self):
        absent=self.daemon.absent;after=[]
        def changed(container):
            value=absent(container)
            with self.store.transaction() as db:
                db.execute('UPDATE claims SET generation=generation+1 WHERE id=?',(self.claim['id'],))
                db.execute('UPDATE tasks SET generation=generation+1 WHERE id=?',(self.task['id'],))
            after.append(self.store.snapshot());return value
        with patch.object(self.daemon,'absent',side_effect=changed),self.assertRaises(RecordError):
            self.launcher().recover(self.claim['run_id'],outcome='failed')
        self.assertEqual(self.store.snapshot(),after[0])

    def test_restore_still_requires_original_host_and_new_context_not_new_host_absence(self):
        bundle=Path(self.tmp.name)/'collector.json';target=Path(self.tmp.name)/'collector-restored.db'
        export_record(self.path,bundle);restore_record(bundle,target,controller_stopped=True)
        store=Store(target,clock=lambda:self.time);before=store.snapshot();self.host='2'*64
        with self.assertRaises(RecordError):self.launcher(store).recover(self.claim['run_id'],outcome='failed')
        self.assertEqual(store.snapshot(),before)
        self.host='1'*64;result=self.launcher(store).recover(self.claim['run_id'],outcome='failed')
        self.assertEqual(result['registration']['phase'],'released');self.assertEqual(result['task']['attempts'],1)

    def test_classification_context_is_bounded_copied_and_never_worker_closeout(self):
        for refs in [[],[{}],[''],['a'*4097]]:
            with self.subTest(refs=refs),self.assertRaises(RecordError):self.make(refs)
        refs=['root:decision'];collector=self.make(refs);refs.append('changed-later')
        self.assertEqual(collector.inspect_termination(self.binding)['classification_evidence'],['root:decision'])


if __name__=='__main__':unittest.main()
