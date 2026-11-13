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
        self.assertTrue(result['latch_confirmed'])

    def test_ambiguous_records_keep_committed_latch_and_require_manual_followup(self):
        with self.state.tx() as db:
            db.execute('DROP INDEX one_active')
            db.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,NULL)',('e'*32,'second',1,'held',0,json.dumps({'kind':'windows'})))
        result=self.pause.pause(self.root,self.ports)
        self.assertTrue(result['latch_confirmed']);self.assertFalse(result['identities_validated'])
        self.assertEqual(result['state'],'paused_pending_stop');self.assertEqual(self.calls,[('disable',)])

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
            self.pause,'RecoveryPorts',return_value=self.ports),patch.object(sys,'argv',['pause']),patch.object(self.pause,'show_result',create=True,return_value=True),patch('builtins.print'):
            self.assertEqual(self.pause.main(),0)
        self.assertEqual(self.state.jobs()[0]['state'],'paused')

    def main_fixture(self,args,*,host=False):
        import contextlib,io
        output=io.StringIO()
        with patch.object(self.pause,'installed_root',return_value=self.root),patch.object(self.pause,'host_identity',return_value=host),patch.object(
            self.pause,'RecoveryPorts',return_value=self.ports),patch.object(sys,'argv',['pause']+args),contextlib.redirect_stdout(output):
            code=self.pause.main()
        return code,json.loads(output.getvalue())

    def test_renamed_host_still_latches_and_stops_local_work(self):
        code,result=self.main_fixture(['--json'],host=False)
        self.assertEqual(code,0);self.assertEqual(result['state'],'paused')
        self.assertEqual(self.state.jobs()[0]['state'],'paused');self.assertIn(('disable',),self.calls)

    def test_unexpected_arguments_never_prevent_local_latch(self):
        code,result=self.main_fixture(['--json','--unexpected'],host=True)
        self.assertTrue(result['latch_confirmed']);self.assertEqual(result['state'],'paused')
        self.assertTrue(result['unexpected_arguments'])

    def test_host_mismatch_blocks_only_trial_ssh(self):
        import types
        ports=self.pause.RecoveryPorts(self.root)
        with patch.object(self.pause,'host_identity',return_value=False),patch.object(self.pause,'system_directory',return_value=Path('system')),patch.object(
            self.pause,'known_folder',return_value=self.root),patch.object(self.pause.subprocess,'run',return_value=types.SimpleNamespace(
            stdout=json.dumps({'job':'a'*32,'confirmed_empty':True}).encode())) as run:
            self.assertFalse(ports.stop({'id':'a'*32,'kind':'trial'}));run.assert_not_called()

    def test_default_button_presents_pending_and_persists_readable_outcome(self):
        self.ports.stop=lambda job:False
        with patch.object(self.pause,'show_result',create=True,return_value=True) as show:
            code,result=self.main_fixture([],host=True)
        self.assertEqual(code,2);self.assertEqual(result['state'],'paused_pending_stop')
        self.assertEqual(show.call_count,1);self.assertEqual(show.call_args.args[0]['state'],'paused_pending_stop')
        saved=json.loads((self.root/'pause-result.json').read_text(encoding='utf-8'))
        self.assertEqual(saved['state'],'paused_pending_stop');self.assertIn('completed_at',saved)

    def test_unavailable_root_reports_visible_refusal(self):
        import contextlib,io
        out=io.StringIO()
        with patch.object(self.pause,'installed_root',side_effect=OSError('private detail')),patch.object(sys,'argv',['pause']),patch.object(
            self.pause,'show_result',create=True,return_value=True) as show,contextlib.redirect_stdout(out):
            code=self.pause.main()
        result=json.loads(out.getvalue());self.assertEqual(code,3);self.assertEqual(result['state'],'refused')
        self.assertEqual(show.call_args.args[0]['state'],'refused');self.assertNotIn('private detail',out.getvalue())

    def test_recovery_status_reads_current_control_despite_damaged_stage(self):
        self.pause.pause(self.root,self.ports)
        (self.root/'manifest.json').mkdir()
        with self.state.tx() as db:db.execute("UPDATE control SET status='paused_pending_stop'")
        epoch=self.state.control()['epoch']
        with patch.object(self.pause,'pause',side_effect=AssertionError('read only')):
            code,result=self.main_fixture(['--status','--json'],host=False)
        self.assertEqual(code,2);self.assertEqual(result['state'],'paused_pending_stop')
        self.assertEqual(self.state.control()['epoch'],epoch)

    def test_closing_older_dialog_does_not_overwrite_newer_pending_result(self):
        def newer_pause(result):
            with self.state.tx() as db:
                db.execute("UPDATE jobs SET state='active' WHERE id=?",(self.job['id'],))
                db.execute("UPDATE control SET status='paused_pending_stop'")
            self.ports.stop=lambda job:False
            code,newer=self.main_fixture(['--json'],host=True)
            self.assertEqual(newer['state'],'paused_pending_stop')
            return True
        with patch.object(self.pause,'show_result',side_effect=newer_pause):
            self.main_fixture([],host=True)
        saved=json.loads((self.root/'pause-result.json').read_text(encoding='utf-8'))
        self.assertEqual(saved['state'],'paused_pending_stop')

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
