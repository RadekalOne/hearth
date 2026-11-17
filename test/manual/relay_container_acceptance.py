"""Explicit trial-only credential-free Docker/Broker/watchdog acceptance. Never a native model."""
import hashlib,json,os,signal,subprocess,sys,tempfile,time
from pathlib import Path
root=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(root/'ops/hearth2'),str(root/'mcp/memory'),str(root/'test')]
from relay_entitlement import ContainerWorkload
from test_hearth2_private_broker import PrivateBrokerTests
IMAGE=sys.argv[1]
assert os.geteuid()==0
assert IMAGE.startswith('sha256:') and len(IMAGE)==71
run_id='offline-20261117'
work=Path(tempfile.mkdtemp(prefix='entitlement-check-',dir='/root/hearth-runner-trial'))
config=root/'docs/hearth2/entitlement-run/config.toml'
config_hash=hashlib.sha256(config.read_bytes()).hexdigest()
cids=[];records={};started=time.time()
def docker(*args):return subprocess.check_output(['docker',*args],stderr=subprocess.STDOUT,text=True,timeout=10).strip()
def create(socket=None):
 args=['create','--read-only','--network=none','--cap-drop=ALL','--security-opt=no-new-privileges','--user=1000:1000','--pids-limit=32','--memory=128m','--label','hearth.entitlement.run='+run_id,'--mount',f'type=bind,src={config},dst=/scratch/codex-home/config.toml,readonly']
 args+=['--mount','type=bind,src=/root/hearth-runner-trial/clients/codex/0.159.1/vendor/x86_64-unknown-linux-musl/bin/codex,dst=/opt/codex,readonly']
 if socket:args+=['--mount',f'type=bind,src={socket},dst=/run/hearth-memory.sock']
 cid=docker(*args,IMAGE,'python','-c','import time;time.sleep(360)');cids.append(cid);docker('start',cid);return cid
try:
 f=PrivateBrokerTests('test_real_scoped_read_without_worker_bearer_and_no_secret_in_metadata');f.setUp();f.channel.start()
 cid=create(f.channel.socket_path)
 w=ContainerWorkload(cid,image=IMAGE,run_id=run_id,config_sha256=config_hash,channel=f.channel,memory_reads=lambda:len(f.reads),watchdog_receipt=work/'normal-watchdog.json')
 code="import socket,json;s=socket.socket(socket.AF_UNIX);s.connect('/run/hearth-memory.sock');s.sendall(b'{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"tools/call\",\"params\":{\"name\":\"memory_get\",\"arguments\":{\"drawer_id\":\"drawer_fixture\"}}}\\n');print(s.makefile('rb').readline().decode())"
 reply=json.loads(docker('exec',cid,'python','-c',code))
 assert 'result' in reply and w.memory_read_verified()
 assert w.stop() is True
 records['broker_read_and_normal_stop']={'cid':cid,'reads':len(f.reads),'removed':True,'channel_revoked':f.channel.metadata()['closed']}
 f.doCleanups();f.tmp.cleanup()
 cid=create();ready=work/'armed';receipt=work/'outside.json'
 driver=work/'driver.py'
 driver.write_text("import sys,time\nfrom pathlib import Path\nsys.path.insert(0,"+repr(str(root/'ops/hearth2'))+")\nfrom relay_entitlement import ContainerWorkload\nclass C:\n def check(self):return True\n def close(self):pass\nw=ContainerWorkload("+repr(cid)+",image="+repr(IMAGE)+",run_id="+repr(run_id)+",config_sha256="+repr(config_hash)+",channel=C(),memory_reads=lambda:0,watchdog_receipt="+repr(str(receipt))+")\nPath("+repr(str(ready))+").write_text(str(w.watchdog.pid))\nwhile True:time.sleep(1)\n")
 p=subprocess.Popen([sys.executable,'-I',str(driver)],start_new_session=True)
 end=time.monotonic()+15
 while not ready.exists() and time.monotonic()<end:time.sleep(.1)
 assert ready.exists(),'watchdog not armed'
 os.kill(p.pid,signal.SIGKILL);p.wait(timeout=5)
 end=time.monotonic()+105
 while not receipt.exists() and time.monotonic()<end:time.sleep(.25)
 assert receipt.exists(),'outside watchdog did not complete'
 outside=json.loads(receipt.read_text());assert outside['rm']==0
 assert subprocess.run(['docker','inspect',cid],capture_output=True).returncode!=0
 records['driver_killed_watchdog_survived']={'cid':cid,'driver_exit':p.returncode,'watchdog':outside,'removed':True}
 records.update(image=IMAGE,started_at=started,ended_at=time.time(),model_turns=0,auth_supplied=False)
 print(json.dumps(records,sort_keys=True),flush=True)
finally:
 for cid in cids:subprocess.run(['docker','rm','-f',cid],capture_output=True,timeout=10)
