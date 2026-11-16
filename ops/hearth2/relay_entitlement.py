"""Disabled, one-shot composed entitlement driver. Caller owns isolated workload.
No CLI, scheduler wiring, auth discovery or automatic execution. Uses reviewed native APIs.
"""
import hashlib,json,os,time
from datetime import datetime,timezone
from pathlib import Path
from relay_financial import check

TURN_SECONDS=45
WORKLOAD_SECONDS=70
OUTSIDE_SECONDS=90
THREAD={'model':'gpt-6.1-sol','cwd':'/scratch','approvalPolicy':'never','sandbox':'read-only','ephemeral':True}

class Journal:
    def __init__(self,path):self.file=open(path,'x',encoding='utf-8')
    def write(self,**row):
        self.file.write(json.dumps(row,sort_keys=True,allow_nan=False)+'\n');self.file.flush();os.fsync(self.file.fileno());return True
    def close(self):self.file.close()

def execute(package,*,enabled=False,approval=None,read_financial=None,workload=None,
            journal_path=None,clock=lambda:datetime.now(timezone.utc),monotonic=time.monotonic):
    """workload is root-owned containment/session/Broker composition, never a model callback.
    Outside supervisor must already cover workload; this function cannot arm its own failsafe.
    """
    if enabled is not True:raise ValueError('execution_disabled')
    if approval!=package.get('approval_event') or not approval:raise ValueError('scoped_approval_required')
    if workload is None or read_financial is None:raise ValueError('trusted_workload_required')
    if package.get('disabled') is not True:raise ValueError('review_package_required')
    if workload.outside_deadline_seconds!=OUTSIDE_SECONDS:raise ValueError('outside_supervisor_required')
    start=monotonic();journal=Journal(journal_path)
    state='not_sent';tid=None;empty=False
    def active():return monotonic()-start<WORKLOAD_SECONDS and workload.active() is True
    def financial():
        return check(read_financial(),clock(),workspace=package['workspace'],seat=package['seat'],supervised=True)
    def record(row):return journal.write(**row)
    try:
        before=financial()
        journal.write(kind='preflight',run_id=package['run_id'],financial=before,send_state=state)
        # Root-selected workload provides an already contained client with its Broker mounted privately.
        client=workload.client(turn_timeout_seconds=TURN_SECONDS)
        from hearth2.native_thread_launcher import CodexThreadLauncher
        def fence():
            financial()
            return active()
        launcher=CodexThreadLauncher(client,mounted_binary=package['binary_path'],
            expected_binary_sha256=package['binary_sha256'],expected_catalog_sha256=package['catalog_sha256'],
            record_decision=record,pre_thread_fence=fence)
        # Conservative intent precedes all thread I/O. Any exception after this stops workload.
        state='thread_may_exist';journal.write(kind='thread_dispatch_intent',send_state=state)
        thread=launcher.launch_thread(dict(THREAD))
        tid=thread['thread']['id']
        if thread.get('approvalPolicy')!='never':raise ValueError('effective_policy_mismatch')
        journal.write(kind='thread_started',thread_id=tid,send_state='thread_received')
        state='turn_may_be_sent';journal.write(kind='turn_dispatch_intent',thread_id=tid,send_state=state)
        result=client.turn_start({'threadId':tid,'input':[{'type':'text','text':package['prompt']}]},
            before_send=fence,record_event=record,stop_workload=workload.stop)
        journal.write(kind='turn_received',thread_id=tid,turn_id=result.turn_id,send_state='response_received')
        native=result.native_result
        if native.get('state')!='completed':raise ValueError('turn_not_completed')
        # Exact synthetic challenge must have been read through the private Broker.
        if workload.memory_read_verified() is not True:raise ValueError('synthetic_memory_read_missing')
        empty=workload.stop() is True
        if not empty:raise ValueError('workload_stop_unconfirmed')
        if package.get('candidate_fixture'):
            import shutil
            from relay_candidate_tests import run
            fixture=Path(package['candidate_fixture'])
            if hashlib.sha256(fixture.read_bytes()).hexdigest()!=package['candidate_fixture_sha256']:
                raise ValueError('candidate_fixture_pin_mismatch')
            target=Path(journal_path).parent/'candidate-source'
            target.mkdir();(target/'test').mkdir()
            shutil.copyfile(fixture,target/'test/test_entitlement_fixture.py')
            (target/'result.json').write_text(json.dumps({'text':native.get('text'),'expected':package['expected_memory_marker']}),encoding='utf-8')
            tests=run(package['candidate_image'],target.resolve(),'hearth-entitlement-'+package['run_id'])
            journal.write(kind='candidate_tests',result=tests)
        after=financial()
        if before['period']!=after['period']:raise ValueError('financial_period_changed')
        line=f"Entitlement turn finished; human acceptance is pending. No further turn is authorized. Seat usage: {after['usage_percent']}%; run {package['run_id']}."
        journal.write(kind='receipt',thread_id=tid,usage=native.get('usage'),financial=after,status=line,
            understanding='unknown',task_state='unchanged',confirmed_empty=empty)
        return {'status':line,'understanding':'unknown','task_state':'unchanged'}
    except BaseException:
        try:empty=workload.stop() is True
        except BaseException:empty=False
        journal.write(kind='failure',thread_id=tid,send_state=state,confirmed_empty=empty,reason='entitlement_failed')
        raise
    finally:journal.close()

class ContainerWorkload:
    """Explicit root-side attachment to ONE pre-enrolled isolated trial container.
    Does not create containers, discover credentials, set up provider networking or install services.
    The outside watchdog is a separate OS process, independent of the driver/RPC stream.
    """
    outside_deadline_seconds=OUTSIDE_SECONDS
    def __init__(self,cid,*,image,run_id,config_sha256,channel,memory_reads,watchdog_receipt):
        import re,subprocess,sys
        if os.name!='posix' or not re.fullmatch('[0-9a-f]{64}',cid):raise ValueError('trial_linux_exact_cid_required')
        self.cid,self.channel,self.memory_reads=cid,channel,memory_reads
        self.process=None;self.closed=False
        p=subprocess.run(['docker','inspect',cid],capture_output=True,check=True,timeout=5)
        row=json.loads(p.stdout)[0]
        if row['Id']!=cid or row['Image']!=image or row['Config'].get('Labels',{}).get('hearth.entitlement.run')!=run_id:
            raise ValueError('enrolled_container_mismatch')
        h=row['HostConfig']
        if not h.get('ReadonlyRootfs') or h.get('Privileged') or row['Config']['User']!='1000:1000':raise ValueError('container_profile_mismatch')
        # Config and native client are root-enrolled mounts, not model-supplied files.
        got=subprocess.run(['docker','exec',cid,'sha256sum','/scratch/codex-home/config.toml'],capture_output=True,check=True,timeout=5).stdout.decode().split()[0]
        if got!=config_sha256:raise ValueError('config_pin_mismatch')
        code="""import subprocess,sys,time,json,os
time.sleep(90)
r={}
for op in ('kill','rm'):
 try:r[op]=subprocess.run(['docker',op,*(['-f'] if op=='rm' else []),sys.argv[1]],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=5).returncode
 except Exception:r[op]='unknown'
with open(sys.argv[2],'x') as f:
 json.dump(r,f);f.flush();os.fsync(f.fileno())
"""
        self.watchdog=subprocess.Popen([sys.executable,'-I','-c',code,cid,str(watchdog_receipt)],start_new_session=True,
            stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    def active(self):return not self.closed and self.watchdog.poll() is None and self.channel.check() is True
    def client(self,*,turn_timeout_seconds):
        import subprocess
        from hearth2.native_rpc import NativeRpcClient
        if self.process is not None or not self.active():raise ValueError('workload_consumed_or_revoked')
        command=['docker','exec','-i','--user','1000:1000','--env','CODEX_HOME=/scratch/codex-home',self.cid,
            '/opt/codex','-c','model_provider="openai"','-c','features.shell_tool=false',
            '-c','features.apps=false','-c','features.plugins=false','app-server','--listen','stdio://']
        self.process=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
        return NativeRpcClient(self.process.stdout,self.process.stdin,turn_timeout_seconds=turn_timeout_seconds)
    def memory_read_verified(self):return self.memory_reads()>0
    def stop(self):
        import subprocess
        if self.closed:return self.empty
        self.empty=False
        try:
            subprocess.run(['docker','kill',self.cid],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=5)
            removed=subprocess.run(['docker','rm','-f',self.cid],capture_output=True,timeout=5)
            if removed.returncode!=0:return False
            self.empty=True;self.closed=True
            self.channel.close()
            if self.process:
                self.process.wait(timeout=5)
                self.process.stdin.close();self.process.stdout.close()
            # Disarm only after immutable CID removal succeeded.
            self.watchdog.terminate();self.watchdog.wait(timeout=5)
            return True
        except Exception:return False
