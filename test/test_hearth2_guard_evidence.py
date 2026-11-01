"""Private durable files/faults/synthetic guard, never real OS workloads."""
from datetime import timedelta
import importlib
import hashlib
import json
import multiprocessing
import os
from pathlib import Path
import unittest
from unittest.mock import patch
import test_hearth2_root_guard as fixtures
from hearth2.store import RecordError


def write_race(root,binding,observation,barrier,queue):
    from hearth2.guard_evidence import GuardEvidenceStore
    try:
        barrier.wait(timeout=10)
        GuardEvidenceStore(root).append(binding,'observed',observation)
        queue.put('written')
    except RecordError:queue.put('refused')
    except BaseException as exc:queue.put(type(exc).__name__)


class GuardEvidenceTests(unittest.TestCase):
    def setUp(self):
        fixtures.RootGuardTests.setUp(self)
        self.assertIsNotNone(importlib.util.find_spec('hearth2.guard_evidence'),'durable root evidence missing')
        self.evidence_module=importlib.import_module('hearth2.guard_evidence')
        self.root=Path(self.tmp.name)/'durable-evidence';self.root.mkdir(mode=0o700)
        self.evidence=self.evidence_module.GuardEvidenceStore(self.root,clock=lambda:self.time)
        self.guard=self.module.RootKernelGuard(self.kernel,self.daemon,
            host_identity=lambda:self.host,clock=lambda:self.time,evidence=self.evidence)

    def observation(self,**changes):
        return {'observed_at':self.time.isoformat(),'exit_status':137,'ended_at':self.time.isoformat(),**changes}

    def append(self,**changes):
        return self.evidence.append(self.binding,'observed',self.observation(**changes))

    def test_exact_append_survives_fresh_process_object_and_is_idempotent(self):
        receipt=self.append()
        fresh=self.evidence_module.GuardEvidenceStore(self.root,clock=lambda:self.time)
        self.assertEqual(fresh.append(self.binding,'observed',self.observation()),receipt)
        records=fresh.read(self.binding)
        self.assertEqual(len(records),1);self.assertEqual(records[0]['observation']['exit_status'],137)
        files=list(self.root.glob('*.json'));self.assertEqual(len(files),1)
        self.assertEqual(files[0].stat().st_mode & 0o777,0o400)

    def test_observed_exit_is_durable_before_external_container_removal(self):
        original=self.daemon.remove
        def remove(container):
            records=self.evidence_module.GuardEvidenceStore(self.root).read(self.binding)
            self.assertEqual([record['stage'] for record in records],['observed'])
            self.assertEqual(records[0]['observation']['exit_status'],137)
            original(container)
        with patch.object(self.daemon,'remove',side_effect=remove):result=self.guard.enforce(self.binding)
        self.assertEqual({record['stage'] for record in self.evidence.read(self.binding)},{'observed','removed'})
        self.assertEqual(len(result['evidence']),2);self.assertFalse(self.daemon.disarmed)

    def test_no_evidence_store_still_kills_but_cannot_remove_id(self):
        guard=self.module.RootKernelGuard(self.kernel,self.daemon,
            host_identity=lambda:self.host,clock=lambda:self.time)
        with self.assertRaises(RecordError):guard.enforce(self.binding)
        self.assertTrue(self.daemon.present);self.assertGreaterEqual(self.kernel.kills,2)
        self.assertTrue(self.kernel.frozen);self.assertFalse(self.daemon.disarmed)

    def test_file_fsync_failure_refuses_ack_and_prevents_id_removal(self):
        with patch.object(self.evidence_module.os,'fsync',side_effect=OSError('disk error')):
            with self.assertRaises(RecordError):self.guard.enforce(self.binding)
        self.assertTrue(self.daemon.present);self.assertGreaterEqual(self.kernel.kills,2)
        self.assertFalse(self.daemon.disarmed)

    def test_directory_fsync_failure_refuses_ack_even_if_final_name_exists(self):
        original=self.evidence_module.os.fsync;calls=[]
        def fail_directory(fd):
            calls.append(fd)
            if len(calls)==2:raise OSError('directory sync failure')
            return original(fd)
        with patch.object(self.evidence_module.os,'fsync',side_effect=fail_directory):
            with self.assertRaises(RecordError):self.guard.enforce(self.binding)
        self.assertTrue(self.daemon.present);self.assertFalse(self.daemon.disarmed)
        # Retry exact content re-confirms both file and directory durability.
        self.assertEqual(len(self.evidence.read(self.binding)),1)

    def test_post_remove_receipt_failure_keeps_pre_remove_exit_and_no_success_result(self):
        append=self.evidence.append
        def fail(binding,stage,observation):
            if stage=='removed':raise RecordError('post-remove evidence unavailable')
            return append(binding,stage,observation)
        with patch.object(self.evidence,'append',side_effect=fail),self.assertRaises(RecordError):self.guard.enforce(self.binding)
        self.assertFalse(self.daemon.present);self.assertTrue(self.kernel.frozen)
        self.assertGreaterEqual(self.kernel.kills,2);self.assertFalse(self.daemon.disarmed)
        records=self.evidence.read(self.binding)
        self.assertEqual(len(records),1);self.assertEqual(records[0]['observation']['exit_status'],137)

    def test_conflicting_known_exit_or_end_never_overwrites_history(self):
        self.append();before={path.name:path.read_bytes() for path in self.root.iterdir()}
        for changes in [{'exit_status':1},{'ended_at':(self.time+timedelta(seconds=1)).isoformat()}]:
            with self.subTest(changes=changes),self.assertRaises(RecordError):self.append(**changes)
        self.assertEqual({path.name:path.read_bytes() for path in self.root.iterdir()},before)

    def test_unknown_then_known_exit_is_preserved_as_separate_immutable_records(self):
        self.append(exit_status=None,ended_at=None);self.time+=timedelta(seconds=1);self.append()
        records=self.evidence.read(self.binding)
        self.assertEqual(len(records),2)
        self.assertEqual({record['observation']['exit_status'] for record in records},{None,137})

    def test_no_worker_closeout_usage_or_secret_fields_can_be_persisted(self):
        for changes in [{'closeout':{'status':'done'}},{'token':'fake'},{'usage':{'tokens':1}}]:
            with self.subTest(changes=changes),self.assertRaises(RecordError):self.append(**changes)
        with self.assertRaises(RecordError):
            self.evidence.append({**self.binding,'credential':'fake'},'observed',self.observation())
        self.assertEqual(list(self.root.iterdir()),[])

    def test_world_readable_or_symlinked_root_cannot_store_evidence(self):
        self.root.chmod(0o755)
        with self.assertRaises(RecordError):self.append()
        self.root.chmod(0o700);link=Path(self.tmp.name)/'alias';link.symlink_to(self.root,target_is_directory=True)
        with self.assertRaises(RecordError):self.evidence_module.GuardEvidenceStore(link).append(self.binding,'observed',self.observation())

    def test_corrupted_or_symlinked_receipt_cannot_be_read_as_evidence(self):
        self.append();path=next(self.root.glob('*.json'));path.chmod(0o600);path.write_text('{}');path.chmod(0o400)
        with self.assertRaises(RecordError):self.evidence.read(self.binding)
        path.unlink();outside=Path(self.tmp.name)/'outside';outside.write_text('{}')
        path.symlink_to(outside)
        with self.assertRaises(RecordError):self.evidence.read(self.binding)

    def test_same_root_supports_two_bindings_without_cross_reading(self):
        self.append();other={**self.binding,'host_id':'2'*64}
        self.evidence.append(other,'observed',self.observation())
        self.assertEqual(len(self.evidence.read(self.binding)),1)
        self.assertEqual(self.evidence.read(other)[0]['binding']['host_id'],'2'*64)

    def test_conflicting_independent_writers_preserve_one_known_exit(self):
        ctx=multiprocessing.get_context('fork');barrier=ctx.Barrier(2);queue=ctx.Queue()
        processes=[ctx.Process(target=write_race,args=(self.root,self.binding,self.observation(exit_status=code),barrier,queue)) for code in [137,1]]
        for process in processes:process.start()
        results=[queue.get(timeout=15) for _ in processes]
        for process in processes:process.join(10);self.assertEqual(process.exitcode,0)
        self.assertEqual(sorted(results),['refused','written'])
        self.assertEqual(len(self.evidence.read(self.binding)),1)

    def test_read_reconfirms_file_and_directory_durability_before_returning(self):
        self.append()
        with patch.object(self.evidence_module.os,'fsync',side_effect=OSError('read durability unavailable')):
            with self.assertRaises(RecordError):self.evidence.read(self.binding)

    def test_read_does_not_ack_a_receipt_while_writer_has_not_finished(self):
        self.append();fd=os.open(self.root,os.O_RDONLY|os.O_DIRECTORY)
        try:
            self.evidence_module.fcntl.flock(fd,self.evidence_module.fcntl.LOCK_EX|self.evidence_module.fcntl.LOCK_NB)
            with self.assertRaises(RecordError):self.evidence.read(self.binding)
        finally:os.close(fd)

    def seed_history(self,count):
        receipt=self.append();template=json.loads((self.root/receipt['reference']).read_text())
        key=receipt['reference'].split('-observed-')[0];initial=self.time
        self.time+=timedelta(seconds=count)
        for index in range(1,count):
            template['observation']['observed_at']=(initial+timedelta(seconds=index)).isoformat()
            raw=json.dumps(template,sort_keys=True,separators=(',',':')).encode()+b'\n'
            name=key+'-observed-'+hashlib.sha256(raw).hexdigest()+'.json'
            path=self.root/name;path.write_bytes(raw);path.chmod(0o400)
        self.assertEqual(len(self.evidence.read(self.binding)),count)
        return receipt

    def test_prospective_history_capacity_cannot_ack_an_unreadable_guard_result(self):
        receipt=self.seed_history(255)
        with self.assertRaises(RecordError):self.guard.enforce(self.binding)
        self.assertEqual(len(self.evidence.read(self.binding)),256)
        self.assertFalse(self.daemon.present);self.assertFalse(self.daemon.disarmed)
        # The full store still permits an exact acknowledged retry, not new data.
        original=json.loads((self.root/receipt['reference']).read_text())['observation']
        self.assertEqual(self.evidence.append(self.binding,'observed',original),receipt)

    def test_prospective_directory_capacity_preserves_readability_and_existing_files(self):
        for index in range(4095):(self.root/('.retained-'+str(index))).write_bytes(b'prior')
        # Publication briefly needs BOTH staging and final names, even if a crash
        # leaves the staging link. Reserve that peak rather than only final size.
        with self.assertRaises(RecordError):self.append()
        self.assertEqual(len(list(self.root.iterdir())),4095)
        (self.root/'.retained-4095').write_bytes(b'prior')
        with self.assertRaises(RecordError):self.append()
        self.assertEqual(len(list(self.root.iterdir())),4096)
        self.assertEqual(self.evidence.read(self.binding),[])

    def test_failed_exclusive_staging_creation_never_deletes_an_existing_orphan(self):
        name='.stage-'+'a'*32;path=self.root/name;path.write_bytes(b'prior-orphan')
        with patch.object(self.evidence_module.secrets,'token_hex',return_value='a'*32):
            with self.assertRaises(RecordError):self.append()
        self.assertEqual(path.read_bytes(),b'prior-orphan')


if __name__=='__main__':unittest.main()
