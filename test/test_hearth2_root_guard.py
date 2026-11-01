"""Kernel lifecycle against synthetic inventory and PRIVATE regular files only."""
from datetime import timedelta
import importlib
from pathlib import Path
import unittest
import test_hearth2_creation_binding as fixtures
from hearth2.store import RecordError


class KernelInventory:
    def __init__(self):
        self.frozen=False;self.populated=True;self.kills=0;self.steps=[]
    def freeze(self,parent):self.steps.append('freeze');self.frozen=True
    def kill(self,parent):
        if not self.frozen:raise AssertionError('kill without freeze')
        self.steps.append('kill');self.kills+=1;self.populated=False
    def state(self,parent):
        self.steps.append('state')
        return {'frozen':int(self.frozen),'populated':int(self.populated)}


class DaemonInventory:
    def __init__(self,binding,kernel):
        self.binding=binding;self.kernel=kernel;self.present=True;self.disarmed=False
        self.fail=None;self.late_spawn=False;self.wrong_parent=False;self.wrong_id=False
        self.known_exit=True
        self.never_started=False;self.interrupt=False
    def inspect(self,container):
        if self.kernel.kills<1:raise AssertionError('daemon called before kernel kill')
        self.kernel.steps.append('inspect')
        if self.late_spawn:self.kernel.populated=True
        if self.interrupt:raise KeyboardInterrupt('root guard interrupted after first kill')
        if self.fail=='inspect':raise RuntimeError('daemon unavailable')
        return {'Id':'c'*64 if self.wrong_id else container,
            'Config':{'Labels':{'hearth2.run':self.binding['run_id'],
                'hearth2.creation_epoch':self.binding['creation_epoch'],
                'hearth2.policy_sha256':self.binding['policy_sha256'],
                'hearth2.workload':self.binding['workload_id']}},
            'HostConfig':{'CgroupParent':'wrong' if self.wrong_parent else self.binding['parent_cgroup']},
            'State':{'Running':not self.known_exit,'Pid':0 if self.known_exit else 123,
                'Status':'exited' if self.known_exit else 'running','ExitCode':137 if self.known_exit else 0,
                'StartedAt':'0001-01-01T00:00:00Z' if self.never_started else self.binding['at'],
                'FinishedAt':self.binding['at']}}
    def remove(self,container):
        self.kernel.steps.append('remove')
        if self.fail=='remove':raise RuntimeError('remove failed')
        self.present=False
    def absent(self,container):
        self.kernel.steps.append('absent')
        if self.fail=='absent':raise RuntimeError('inventory unavailable')
        return not self.present
    def disarm(self,guard):
        self.kernel.steps.append('disarm')
        if self.kernel.populated or self.present:raise AssertionError('disarm without independent empty+absence')
        self.disarmed=True


class RootGuardTests(unittest.TestCase):
    def setUp(self):
        fixtures.CreationBindingTests.setUp(self)
        self.binding=self.bindings.bind(self.registration,self.claim,host_id='1'*64,container_id='b'*64)
        self.assertIsNotNone(importlib.util.find_spec('hearth2.root_guard'),'root kernel guard missing')
        self.module=importlib.import_module('hearth2.root_guard')
        self.kernel=KernelInventory();self.daemon=DaemonInventory(self.binding,self.kernel)
        self.host='1'*64
        from hearth2.guard_evidence import GuardEvidenceStore
        evidence_root=Path(self.tmp.name)/'guard-evidence';evidence_root.mkdir(mode=0o700)
        self.evidence_store=GuardEvidenceStore(evidence_root,clock=lambda:self.time)
        self.guard=self.module.RootKernelGuard(self.kernel,self.daemon,
            host_identity=lambda:self.host,clock=lambda:self.time,evidence=self.evidence_store)
        self.observer=self.module.IndependentGuardRelease(self.kernel,self.daemon,
            host_identity=lambda:self.host,clock=lambda:self.time)

    def test_kernel_freeze_and_kill_precede_all_daemon_access_and_never_disarm(self):
        result=self.guard.enforce(self.binding)
        self.assertEqual(self.kernel.steps[:3],['freeze','kill','inspect'])
        self.assertEqual(result['container_id'],'b'*64)
        self.assertEqual(result['exit_status'],137)
        self.assertTrue(result['verified_empty']);self.assertTrue(result['immutable_absent'])
        self.assertTrue(self.kernel.frozen);self.assertFalse(self.daemon.disarmed)

    def test_post_kill_inspect_failure_repeats_kernel_kill_without_thaw_or_disarm(self):
        self.daemon.fail='inspect';self.daemon.late_spawn=True
        with self.assertRaises(RecordError):self.guard.enforce(self.binding)
        self.assertGreaterEqual(self.kernel.kills,2);self.assertFalse(self.kernel.populated)
        self.assertTrue(self.kernel.frozen);self.assertTrue(self.daemon.present);self.assertFalse(self.daemon.disarmed)

    def test_remove_failure_repeats_kernel_kill_and_retains_container_and_guard(self):
        self.daemon.fail='remove'
        with self.assertRaises(RecordError):self.guard.enforce(self.binding)
        self.assertGreaterEqual(self.kernel.kills,2);self.assertTrue(self.daemon.present)
        self.assertTrue(self.kernel.frozen);self.assertFalse(self.daemon.disarmed)

    def test_absence_query_failure_is_not_absence_and_repeats_kill(self):
        self.daemon.fail='absent'
        with self.assertRaises(RecordError):self.guard.enforce(self.binding)
        self.assertGreaterEqual(self.kernel.kills,2);self.assertFalse(self.daemon.disarmed)

    def test_wrong_container_or_parent_cannot_be_removed(self):
        self.daemon.wrong_id=True
        with self.assertRaises(RecordError):self.guard.enforce(self.binding)
        self.assertTrue(self.daemon.present);self.assertGreaterEqual(self.kernel.kills,2)
        self.daemon.wrong_id=False;self.daemon.wrong_parent=True
        with self.assertRaises(RecordError):self.guard.enforce(self.binding)
        self.assertTrue(self.daemon.present);self.assertFalse(self.daemon.disarmed)

    def test_running_docker_zero_field_never_becomes_observed_success(self):
        self.daemon.known_exit=False
        result=self.guard.enforce(self.binding)
        self.assertIsNone(result['exit_status']);self.assertIsNone(result['ended_at'])
        self.assertTrue(result['verified_empty']);self.assertFalse(self.daemon.disarmed)

    def test_exited_state_without_real_start_never_invents_an_exit(self):
        self.daemon.never_started=True
        result=self.guard.enforce(self.binding)
        self.assertIsNone(result['exit_status']);self.assertIsNone(result['ended_at'])
        self.assertTrue(result['immutable_absent'])

    def test_post_kill_interrupt_still_repeats_kernel_kill(self):
        self.daemon.interrupt=True;self.daemon.late_spawn=True
        try:
            with self.assertRaises(RecordError):self.guard.enforce(self.binding)
        except KeyboardInterrupt:
            self.fail('guard interruption skipped repeated kernel kill')
        self.assertGreaterEqual(self.kernel.kills,2);self.assertFalse(self.kernel.populated)
        self.assertTrue(self.kernel.frozen);self.assertFalse(self.daemon.disarmed)

    def test_original_host_mismatch_prevents_every_kernel_or_daemon_side_effect(self):
        self.host='2'*64
        with self.assertRaises(RecordError):self.guard.enforce(self.binding)
        with self.assertRaises(RecordError):self.observer.release(self.binding)
        self.assertEqual(self.kernel.steps,[])

    def test_changed_guard_identity_is_refused_before_side_effects(self):
        with self.assertRaises(RecordError):self.guard.enforce({**self.binding,'guard_id':'other'})
        self.assertEqual(self.kernel.steps,[])

    def test_independent_release_refuses_empty_parent_while_immutable_id_exists(self):
        self.kernel.frozen=True;self.kernel.populated=False
        with self.assertRaises(RecordError):self.observer.release(self.binding)
        self.assertFalse(self.daemon.disarmed)

    def test_independent_release_refuses_absent_id_while_parent_populated_or_thawed(self):
        self.daemon.present=False
        with self.assertRaises(RecordError):self.observer.release(self.binding)
        self.kernel.populated=False
        with self.assertRaises(RecordError):self.observer.release(self.binding)
        self.assertFalse(self.daemon.disarmed)

    def test_separate_fresh_empty_and_absence_queries_allow_disarm_without_parent_deletion(self):
        self.guard.enforce(self.binding);self.kernel.steps=[]
        result=self.observer.release(self.binding)
        self.assertEqual(self.kernel.steps,['state','absent','disarm'])
        self.assertTrue(self.daemon.disarmed);self.assertTrue(self.kernel.frozen)
        self.assertTrue(result['guard_disarmed'])

    def test_release_query_failure_retains_guard(self):
        self.kernel.frozen=True;self.kernel.populated=False;self.daemon.fail='absent'
        with self.assertRaises(RecordError):self.observer.release(self.binding)
        self.assertFalse(self.daemon.disarmed)

    def files(self):
        root=Path(self.tmp.name)/'private-cgroup';root.mkdir()
        group=root/self.binding['parent_cgroup'];group.mkdir()
        for name,value in [('cgroup.freeze','0'),('cgroup.kill','0'),('cgroup.events','populated 0\nfrozen 1\n')]:
            (group/name).write_text(value)
        return root,group,self.module.CgroupFiles(root)

    def test_concrete_cgroup_operations_touch_only_exact_private_parent(self):
        root,group,fs=self.files();parent=self.binding['parent_cgroup']
        fs.freeze(parent);fs.kill(parent)
        self.assertEqual((group/'cgroup.freeze').read_text(),'1')
        self.assertEqual((group/'cgroup.kill').read_text(),'1')
        self.assertEqual(fs.state(parent),{'populated':0,'frozen':1})
        self.assertTrue(group.exists())

    def test_cgroup_traversal_and_symlinked_control_file_are_refused(self):
        root,group,fs=self.files();outside=Path(self.tmp.name)/'outside';outside.write_text('untouched')
        for parent in ['../outside','/sys/fs/cgroup','hearth2-other']:
            with self.subTest(parent=parent),self.assertRaises(RecordError):fs.freeze(parent)
        (group/'cgroup.kill').unlink();(group/'cgroup.kill').symlink_to(outside)
        with self.assertRaises(RecordError):fs.kill(self.binding['parent_cgroup'])
        self.assertEqual(outside.read_text(),'untouched')

    def test_symlinked_parent_is_refused_without_outside_writes(self):
        root=Path(self.tmp.name)/'root';root.mkdir();outside=Path(self.tmp.name)/'outside';outside.mkdir()
        (outside/'cgroup.freeze').write_text('0')
        (root/self.binding['parent_cgroup']).symlink_to(outside,target_is_directory=True)
        fs=self.module.CgroupFiles(root)
        with self.assertRaises(RecordError):fs.freeze(self.binding['parent_cgroup'])
        self.assertEqual((outside/'cgroup.freeze').read_text(),'0')

    def test_missing_or_ambiguous_cgroup_events_are_not_empty(self):
        root,group,fs=self.files()
        for text in ['populated 0\n','populated 0\nfrozen 1\npopulated 1\n','populated bad\nfrozen 1\n']:
            (group/'cgroup.events').write_text(text)
            with self.subTest(text=text),self.assertRaises(RecordError):fs.state(self.binding['parent_cgroup'])


if __name__=='__main__':unittest.main()
