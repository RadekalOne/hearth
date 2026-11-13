"""Fixed controller ports. No live model or included-allowance adapter is presumed."""
import json
import os
from pathlib import Path
import re
import subprocess

TASK='Hearth-Codex-Offline-Relay'
REMOTE='/root/hearth-runner-trial/offline-relay-20261112/sandbox_controller.py'


class RemoteSandbox:
    """Credential-free physical acceptance only, with fixed trusted SSH routing."""
    def command(self,operation,ident):
        if operation not in {'start','stop','inspect'} or type(ident) is not str or not re.fullmatch('[0-9a-f]{32}',ident):
            raise ValueError('fixed operation and identity required')
        return ['ssh','-T','-o','BatchMode=yes','-o','IdentityAgent=none','-o','IdentitiesOnly=yes',
            '-o','StrictHostKeyChecking=yes','-o','ConnectTimeout=8','-i',str(Path.home()/'.ssh/hermes-key'),
            'root@179.236.82.242',f'python3 {REMOTE} {operation} {ident}']

    def call(self,operation,ident):
        try:
            value=subprocess.run(self.command(operation,ident),stdin=subprocess.DEVNULL,capture_output=True,timeout=25,check=True)
            if len(value.stdout)>32768:raise ValueError()
            result=json.loads(value.stdout)
            if type(result) is not dict or result.get('job')!=ident:raise ValueError()
            return result
        except Exception:raise RuntimeError('trial acceptance port unavailable') from None


class HostPorts:
    def __init__(self,state=None):self.state=state;self._live=None
    def host_identity(self):return os.name=='nt' and os.environ.get('COMPUTERNAME')=='RSLABINSKI-PC'
    def host_ok(self):
        if not self.host_identity():return False
        return subprocess.run(['tzutil','/g'],capture_output=True,text=True,timeout=5).stdout.strip()=='Eastern Standard Time'

    def live(self,*,diagnostic=False):
        if self._live is None:
            if self.state is None:raise RuntimeError('state_required')
            from relay_live import LivePorts
            self._live=LivePorts.installed(self.state,diagnostic=diagnostic)
        return self._live
    def poll(self):return self.live().poll()
    def ready_for_claim(self):return self.live().ready_for_claim()
    def poll_status(self):return self.live().poll_status()
    def base_commit(self):return self.live().base_commit()
    def verify(self,work):return self.live().verify(work)
    def allowance(self):
        try:return self.live().allowance()
        except Exception:return {'source':'unavailable','included_only':False,'fresh':False,'fallback':False}
    def launch(self,job):return self.live().launch(job)
    def post(self,room,thread,text):return self.live().post(room,thread,text)

    def disable(self):
        # No registration or enable path; this action affects the exact named task only.
        script=("try{$t=Get-ScheduledTask -TaskName '"+TASK+"' -ErrorAction Stop}catch{"
            "if($_.FullyQualifiedErrorId -like 'CmdletizationQuery_NotFound_TaskName*'){exit 0};exit 2}; "
            "if($t){if($t.Description -ne 'Hearth offline relay disabled candidate'){exit 2};"
            "$t|Disable-ScheduledTask|Out-Null; "
            "if((Get-ScheduledTask -TaskName '"+TASK+"').Settings.Enabled){exit 1}};exit 0")
        try:
            return subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',script],
                stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=30).returncode==0
        except (subprocess.TimeoutExpired,OSError):return False

    def stop(self,job):
        if job.get('kind')=='trial':return RemoteSandbox().call('stop',job['id']).get('confirmed_empty') is True
        if job.get('kind')=='windows' and self.state is not None:
            from offline_relay_windows import stop
            return stop(self.state,job)
        return False
