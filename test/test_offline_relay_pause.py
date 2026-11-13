"""Independent pause recovery regressions. Every scheduler/stop port is synthetic."""
import importlib,json,os
from pathlib import Path
import sqlite3,sys,tempfile,unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).parents[1]/'ops/hearth2'))
from offline_relay_state import State

class IndependentPauseTests(unittest.TestCase):
    def setUp(self):
        self.pause=importlib.import_module('offline_relay_pause')
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)/'Hearth/OfflineRelay';self.root.mkdir(parents=True)
        self.state=State(self.root/'relay.sqlite3')
        with self.state.tx() as db:db.execute('UPDATE control SET paused=0,enabled=1')
        self.job=self.state.claim({'work_id':'fixture','generation':1,'aliases':[],'kind':'windows'})
        self.calls=[];owner=self
        class Ports:
            def stop(self,job):
                owner.assertTrue(owner.state.control()['paused']);owner.assertFalse(owner.state.control()['enabled'])
                owner.calls.append(('stop',job['id']));return True
            def disable(self):owner.calls.append(('disable',));return True
        self.ports=Ports()

    def test_damaged_staged_files_do_not_block_active_claim_pause(self):
        (self.root/'program').mkdir();(self.root/'program/offline_relay.py').write_text('raise RuntimeError("changed stage must not execute")')
        result=self.pause.pause(self.root,self.ports)
        self.assertEqual(result['state'],'paused');self.assertEqual(self.state.control()['epoch'],1)
        self.assertEqual(self.state.jobs()[0]['state'],'paused');self.assertEqual(self.calls[0],('stop',self.job['id']))

    def test_unreadable_manifest_does_not_block_active_claim_pause(self):
        (self.root/'manifest.json').mkdir() # Guaranteed read failure on every OS.
        self.assertEqual(self.pause.pause(self.root,self.ports)['state'],'paused')
        self.assertIn(('stop',self.job['id']),self.calls)

    def test_changed_localappdata_uses_known_folder_not_environment(self):
        with patch.dict(os.environ,{'LOCALAPPDATA':str(Path(self.tmp.name)/'decoy')}),patch.object(
            self.pause,'known_folder',return_value=self.root.parents[1]) as folder:
            self.assertEqual(self.pause.installed_root(),self.root)
            self.assertEqual(self.pause.pause(self.pause.installed_root(),self.ports)['state'],'paused')
            folder.assert_called_with('local')
        self.assertFalse((Path(self.tmp.name)/'decoy').exists())

    def test_unconfirmed_stop_cannot_report_paused(self):
        self.ports.stop=lambda job:False
        result=self.pause.pause(self.root,self.ports)
        self.assertEqual(result['state'],'paused_pending_stop')
        self.assertEqual(self.state.jobs()[0]['state'],'claimed')
        self.assertIn(('disable',),self.calls)

    def test_stop_exception_still_disables_and_records_pending(self):
        self.ports.stop=lambda job:(_ for _ in ()).throw(OSError('sentinel must not leak'))
        result=self.pause.pause(self.root,self.ports)
        self.assertEqual(result['state'],'paused_pending_stop');self.assertNotIn('sentinel',json.dumps(result))
        self.assertIn(('disable',),self.calls)

    def test_missing_state_does_not_create_a_new_database_or_report_success(self):
        missing=self.root/'missing';result=self.pause.pause(missing,self.ports)
        self.assertEqual(result['state'],'paused_pending_stop');self.assertFalse(missing.exists())
        self.assertEqual(self.calls,[('disable',)])

    def test_invalid_recorded_identity_never_reaches_stop(self):
        with self.state.tx() as db:db.execute("UPDATE jobs SET id='../../elsewhere'")
        result=self.pause.pause(self.root,self.ports)
        self.assertEqual(result['state'],'paused_pending_stop');self.assertEqual(self.calls,[('disable',)])
        self.assertTrue(self.state.control()['paused'])

    def test_launch_verifier_refuses_changed_recovery_artifact(self):
        import hashlib,shutil,subprocess
        program=self.root/'program';program.mkdir();recovery=self.root/'recovery';recovery.mkdir()
        names=['offline_relay.py','offline_relay_state.py','offline_relay_ports.py','offline_relay_windows.py','pause-offline-relay.ps1']
        for n in names:shutil.copyfile(Path(__file__).parents[1]/'ops/hearth2'/n,program/n)
        shutil.copyfile(Path(__file__).parents[1]/'ops/hearth2/offline_relay_pause.py',recovery/'offline_relay_pause.py')
        manifest={'host':os.environ.get('COMPUTERNAME'),'task':'Hearth-Codex-Offline-Relay',
            'source_hashes':{n:hashlib.sha256((program/n).read_bytes()).hexdigest() for n in names},
            'recovery_hashes':{'offline_relay_pause.py':hashlib.sha256((recovery/'offline_relay_pause.py').read_bytes()).hexdigest()}}
        (self.root/'manifest.json').write_text(json.dumps(manifest))
        env={**os.environ,'LOCALAPPDATA':str(self.root.parents[1])}
        command=[sys.executable,'-I',str(program/'offline_relay.py'),'status','--state',str(self.state.path)]
        self.assertEqual(subprocess.run(command,env=env,capture_output=True,timeout=10).returncode,0)
        (recovery/'offline_relay_pause.py').write_text('changed recovery must block launch')
        self.assertNotEqual(subprocess.run(command,env=env,capture_output=True,timeout=10).returncode,0)

    def test_cli_uses_fixed_installed_root_no_manifest_or_launch_import(self):
        with patch.object(self.pause,'installed_root',return_value=self.root),patch.object(self.pause,'host_identity',return_value=True),patch.object(
            self.pause,'RecoveryPorts',return_value=self.ports),patch.object(sys,'argv',['pause']),patch('builtins.print'):
            self.assertEqual(self.pause.main(),0)
        self.assertEqual(self.state.jobs()[0]['state'],'paused')

    def test_scheduler_unit_port_is_mocked_and_exact_root_task_is_bound(self):
        import subprocess,types
        ports=self.pause.RecoveryPorts(self.root)
        with patch.object(self.pause,'system_directory',return_value=Path('C:/Windows/System32')),patch.object(
            self.pause.subprocess,'run',return_value=types.SimpleNamespace(returncode=0)) as run:
            self.assertTrue(ports.disable())
            script=run.call_args.args[0][-1]
            self.assertIn("-TaskPath '\\'",script);self.assertIn('Hearth-Codex-Offline-Relay',script)
            self.assertIn('WorkingDirectory',script);self.assertIn('offline_relay.py',script)
        with patch.object(self.pause,'system_directory',return_value=Path('C:/Windows/System32')),patch.object(
            self.pause.subprocess,'run',side_effect=subprocess.TimeoutExpired('scheduler',30)):
            self.assertFalse(ports.disable())

if __name__=='__main__':unittest.main()
