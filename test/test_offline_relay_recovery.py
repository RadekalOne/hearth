"""Regression checks for fixture lifecycle crashes; all Docker/OS ports mocked."""
import importlib.util
from pathlib import Path
import sys,tempfile,types,unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).parents[1]/'ops/hearth2'))

class FixtureRecoveryTests(unittest.TestCase):
    def load_remote(self):
        spec=importlib.util.spec_from_file_location('relay_sandbox_fixture',Path(__file__).parent/'fixtures/offline_relay/sandbox_controller.py')
        mod=importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules,{'fcntl':types.SimpleNamespace(flock=lambda *a:None,LOCK_EX=1)}):spec.loader.exec_module(mod)
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);mod.ROOT=Path(tmp.name)
        return mod

    def test_created_container_cleanup_never_reads_pid_zero(self):
        mod=self.load_remote();ident='a'*32
        row={'State':{'Running':False,'Pid':0},'Id':'fixed'}
        for receipt in [None,{'phase':'created','container_id':'fixed'}]:
            if receipt:mod.write(mod.ROOT/(ident+'.json'),receipt)
            with patch.object(mod,'inspect',side_effect=[row,None]),patch.object(mod,'command',return_value='') as command,patch.object(mod,'cg',side_effect=AssertionError('PID0')):
                self.assertTrue(mod.action('stop',ident)['confirmed_empty'])
                self.assertIn(('docker','rm','fixed'),[c.args for c in command.call_args_list])

    def test_watchdog_spawn_failure_precedes_any_container_creation(self):
        mod=self.load_remote()
        with patch.object(mod.subprocess,'Popen',side_effect=OSError('fixture spawn')),patch.object(mod,'command',return_value='') as command:
            with self.assertRaises(OSError):mod.action('start','b'*32)
            command.assert_not_called()

    def test_pause_tombstone_does_not_end_supervision_before_cleanup(self):
        mod=self.load_remote();ident='c'*32;mod.write(mod.ROOT/(ident+'.paused'),{'paused':True})
        with patch.object(mod.time,'monotonic',side_effect=[0,0,16]),patch.object(mod.time,'sleep'),patch.object(mod,'action') as action:
            mod.watch(ident)
            action.assert_called_once_with('stop',ident)

    def test_windows_supervisor_failure_precedes_keeper_spawn(self):
        import offline_relay_windows as win
        with patch.object(win,'supervise',side_effect=OSError('fixture spawn'),create=True),patch.object(win.subprocess,'Popen') as popen:
            with self.assertRaises(OSError):win.start(types.SimpleNamespace(path=Path('fixture.db')),{'id':'d'*32})
            popen.assert_not_called()

if __name__=='__main__':unittest.main()
