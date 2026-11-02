"""Private fake executables ONLY; no Docker/systemd/worker activation."""
import importlib
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
from hearth2.store import RecordError


class RootCommandTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='hearth2-private-command-');self.addCleanup(self.tmp.cleanup)
        self.directory=Path(self.tmp.name)
        self.assertIsNotNone(importlib.util.find_spec('hearth2.root_commands'),'bounded root daemon port missing')
        self.module=importlib.import_module('hearth2.root_commands')

    def run_script(self,code,*,timeout=.5,limit=4096):
        script=self.directory/'helper.py';script.write_text(code)
        runner=self.module.BoundedCommand(sys.executable,timeout_seconds=timeout,max_output=limit)
        return runner.run([str(script)])

    def test_helper_environment_strips_secrets_and_daemon_routing(self):
        names=['HEARTH_MEMORY_TOKEN','OPENAI_API_KEY','SSH_AUTH_SOCK','DOCKER_HOST','DOCKER_CONTEXT','DBUS_SYSTEM_BUS_ADDRESS']
        with patch.dict(os.environ,{name:'fake-never-forward' for name in names}):
            output=self.run_script('import os,json;print(json.dumps({k:k in os.environ for k in '+repr(names)+'}))')
        self.assertEqual(json.loads(output),{name:False for name in names})

    def test_stdout_is_returned_but_stderr_never_becomes_result(self):
        result=self.run_script('import sys;print("selected");print("private-error",file=sys.stderr)')
        self.assertEqual(result,b'selected\n')

    def test_failed_helper_exposes_no_stderr_or_stdout_contents(self):
        with self.assertRaises(RecordError) as error:
            self.run_script('import sys;print("fake-secret");print("fake-secret",file=sys.stderr);sys.exit(2)')
        self.assertNotIn('fake-secret',str(error.exception))

    def test_stdout_overflow_is_refused_before_unbounded_capture(self):
        start=time.monotonic()
        with self.assertRaises(RecordError):self.run_script('import os\nwhile True:os.write(1,b"x"*4096)')
        self.assertLess(time.monotonic()-start,2)

    def test_stderr_counts_toward_the_same_output_bound(self):
        with self.assertRaises(RecordError):self.run_script('import os;os.write(2,b"x"*8192)')

    def test_sleeping_helper_hits_absolute_time_bound(self):
        start=time.monotonic()
        with self.assertRaises(RecordError):self.run_script('import time;time.sleep(10)',timeout=.15)
        self.assertLess(time.monotonic()-start,1.5)

    def test_successful_parent_cannot_leave_a_same_group_helper_running(self):
        marker=self.directory/'child-pid'
        code='import subprocess,sys\np=subprocess.Popen([sys.executable,"-c","import time;time.sleep(10)"],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)\nopen('+repr(str(marker))+',"w").write(str(p.pid))\nprint("ok")'
        self.assertEqual(self.run_script(code),b'ok\n')
        child=int(marker.read_text());deadline=time.monotonic()+1
        while time.monotonic()<deadline:
            try:status=Path('/proc',str(child),'stat').read_text().split()[2]
            except (FileNotFoundError,ProcessLookupError):break
            if status=='Z':break
            time.sleep(.01)
        else:self.fail('root helper descendant still running after parent success')

    def test_timeout_also_kills_descendant_holding_output_pipe(self):
        marker=self.directory/'child-pid'
        code='import subprocess,sys,time\np=subprocess.Popen([sys.executable,"-c","import time;time.sleep(10)"])\nopen('+repr(str(marker))+',"w").write(str(p.pid))\ntime.sleep(10)'
        with self.assertRaises(RecordError):self.run_script(code,timeout=.15)
        child=int(marker.read_text());deadline=time.monotonic()+1
        while time.monotonic()<deadline:
            try:status=Path('/proc',str(child),'stat').read_text().split()[2]
            except (FileNotFoundError,ProcessLookupError):break
            if status=='Z':break
            time.sleep(.01)
        else:self.fail('root helper descendant survived timeout')

    def test_relative_executable_or_unbounded_limits_are_refused(self):
        for args in [('docker',.5,4096),(sys.executable,0,4096),(sys.executable,True,4096),
                     (sys.executable,float('inf'),4096),(sys.executable,.5,0)]:
            with self.subTest(args=args),self.assertRaises(RecordError):
                self.module.BoundedCommand(args[0],timeout_seconds=args[1],max_output=args[2])

    def ports(self):
        state=self.directory/'state.json';log=self.directory/'calls.jsonl'
        selected={'Id':'b'*64,'Config':{'Labels':{'hearth2.run':'run_'+'a'*32,
            'hearth2.creation_epoch':'epoch-original','hearth2.policy_sha256':'c'*64,
            'hearth2.workload':'hearth2-'+'a'*32}},'HostConfig':{'CgroupParent':'hearth2-'+'d'*64},
            'State':{'Running':False,'Pid':0,'Status':'exited','ExitCode':137,
                     'StartedAt':'2026-11-01T00:00:00Z','FinishedAt':'2026-11-01T00:00:01Z'}}
        state.write_text(json.dumps({'inspect':selected,'list':'','active':'','exit':0}))
        script=self.directory/'private-daemon'
        script.write_text('#!'+sys.executable+'\nimport json,sys\nfrom pathlib import Path\nstate=Path('+repr(str(state))+');data=json.loads(state.read_text())\nwith open('+repr(str(log))+',"a") as out:out.write(json.dumps(sys.argv[1:])+"\\n")\nif "inspect" in sys.argv:print(json.dumps(data["inspect"]))\nelif "ls" in sys.argv:print(data["list"])\nelif "list-units" in sys.argv:print(data["active"])\nsys.exit(data["exit"])\n')
        script.chmod(0o700)
        runner=self.module.BoundedCommand(script,timeout_seconds=.5,max_output=8192)
        port=self.module.DockerSystemdCommands(runner,runner)
        self.state,self.calls=state,log
        return port,selected

    def change(self,**fields):
        value=json.loads(self.state.read_text());value.update(fields);self.state.write_text(json.dumps(value))

    def test_inspect_requests_only_selected_fields_and_returns_exact_projection(self):
        port,selected=self.ports();self.assertEqual(port.inspect('b'*64),selected)
        call=json.loads(self.calls.read_text().splitlines()[0])
        self.assertEqual(call[:2],['--host','unix:///var/run/docker.sock'])
        template=call[call.index('--format')+1]
        self.assertNotIn('.Config.Env',template);self.assertNotIn('.Args',template);self.assertNotIn('.Mounts',template)
        self.assertEqual(call[-1],'b'*64)

    def test_unexpected_inspect_fields_cannot_escape_projection(self):
        port,selected=self.ports();selected['Config']['Env']=['fake-secret'];self.change(inspect=selected)
        with self.assertRaises(RecordError):port.inspect('b'*64)

    def test_only_successful_empty_exact_inventory_means_absence(self):
        port,_=self.ports();self.assertTrue(port.absent('b'*64))
        self.change(list='b'*64);self.assertFalse(port.absent('b'*64))
        self.change(list='c'*64)
        with self.assertRaises(RecordError):port.absent('b'*64)

    def test_failed_inventory_is_not_absence(self):
        port,_=self.ports();self.change(exit=2)
        with self.assertRaises(RecordError):port.absent('b'*64)

    def test_invalid_container_id_cannot_run_inspect_remove_or_inventory(self):
        port,_=self.ports()
        for method in [port.inspect,port.remove,port.absent]:
            for identity in ['-a','../other','b'*12,'b'*65]:
                with self.subTest(identity=identity),self.assertRaises(RecordError):method(identity)
        self.assertFalse(self.calls.exists())

    def test_remove_targets_only_exact_original_id_without_shell(self):
        port,_=self.ports();port.remove('b'*64)
        args=json.loads(self.calls.read_text().splitlines()[0])
        self.assertEqual(args,['--host','unix:///var/run/docker.sock','container','rm','--force','--','b'*64])

    def test_disarm_stops_only_guard_units_then_requires_successful_inactive_inventory(self):
        port,_=self.ports();guard='hearth2-deadline-'+'a'*64;port.disarm(guard)
        calls=[json.loads(line) for line in self.calls.read_text().splitlines()]
        self.assertEqual(calls[0][-2:],[guard+'.timer',guard+'.service'])
        self.assertIn('stop',calls[0]);self.assertIn('list-units',calls[1])
        self.assertTrue(all('slice' not in str(call) for call in calls))
        self.change(active=guard+'.timer active')
        with self.assertRaises(RecordError):port.disarm(guard)

    def test_invalid_guard_name_never_stops_any_unit(self):
        port,_=self.ports()
        for guard in ['docker','--all','hearth2-parent.slice','hearth2-deadline-'+ 'a'*63]:
            with self.subTest(guard=guard),self.assertRaises(RecordError):port.disarm(guard)
        self.assertFalse(self.calls.exists())


if __name__=='__main__':unittest.main()
