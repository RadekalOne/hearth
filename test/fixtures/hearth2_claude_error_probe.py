"""Observe installed Claude error output against a fake loopback-only API.

An intentionally synthetic user input is sent to the CLI. There is no real
login, provider connection or inference. The entire container has network none.
This is output-compatibility evidence, not subscription or runtime acceptance.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import uuid

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'mcp/memory'))
from hearth2.native_policy import claude_managed_settings
from hearth2.native_output import JsonLines

CLAUDE='/usr/local/lib/node_modules/@anthropic-ai/claude-code/bin/claude.exe'
PAYLOAD=r'''
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json,os,subprocess,threading,time,uuid,sys,selectors,tempfile
sys.path.insert(0,'/opt/hearth')
from hearth2.native_output import NativeStream
status=int(sys.argv[1])
calls=[]
class FakeAPI(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_POST(self):
        size=int(self.headers.get('Content-Length','0'))
        if not 0<=size<=2_000_000:raise RuntimeError('oversized fixture request')
        self.rfile.read(size)
        calls.append(self.path)
        data=json.dumps({'type':'error','error':{'type':('rate_limit_error' if status==429 else 'authentication_error'),
            'message':'Synthetic fixture limit; no provider involved.'}}).encode()
        self.send_response(status)
        for key,value in {'Content-Type':'application/json','Content-Length':str(len(data)),
            'retry-after':'0','anthropic-ratelimit-unified-status':'rejected',
            'anthropic-ratelimit-unified-reset':str(int(time.time())+3600)}.items():
            self.send_header(key,value)
        self.end_headers();self.wfile.write(data)
server=ThreadingHTTPServer(('127.0.0.1',0),FakeAPI)
threading.Thread(target=server.serve_forever,daemon=True).start()
env={'PATH':'/usr/local/bin:/usr/bin:/bin','HOME':'/scratch',
    'CLAUDE_CONFIG_DIR':'/scratch/claude','LANG':'C.UTF-8',
    'DISABLE_AUTOUPDATER':'1','CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC':'1',
    'ANTHROPIC_API_KEY':'fixture-not-a-real-key',
    'ANTHROPIC_BASE_URL':'http://127.0.0.1:'+str(server.server_port)}
session=str(uuid.uuid4())
version=subprocess.check_output(['/usr/local/bin/claude','--version'],env=env,text=True,timeout=10).strip()
if version!='2.1.280 (Claude Code)':raise RuntimeError('unreviewed native version')
args=['/usr/local/bin/claude','-p','Synthetic protocol fixture. Reply OK.',
    '--output-format','stream-json','--verbose','--no-chrome',
    '--permission-mode','dontAsk','--tools','','--strict-mcp-config',
    '--mcp-config','{"mcpServers":{}}','--disable-slash-commands','--setting-sources','',
    '--settings','{"fastMode":false,"enableWorkflows":false}',
    '--session-id',session,'--model','sonnet','--max-turns','1']
stream=NativeStream('claude',session_id=session)
errors=tempfile.TemporaryFile()
client=subprocess.Popen(args,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,
    stderr=errors,env=env,cwd='/scratch')
selector=selectors.DefaultSelector();selector.register(client.stdout,selectors.EVENT_READ)
timeout=False;stopped=False;chunks=[];size=0;end=time.monotonic()+20
try:
    while time.monotonic()<end:
        if not selector.select(0.1):continue
        chunk=os.read(client.stdout.fileno(),65536)
        if not chunk:break
        size+=len(chunk)
        if size>2_000_000:raise RuntimeError('oversized fixture output')
        chunks.append(chunk)
        outcome=stream.feed(chunk)
        if outcome['pause_role']:
            stopped=True;client.kill();break
    else:timeout=True;client.kill()
    tail,_=client.communicate(timeout=3)
    if tail:chunks.append(tail);stream.feed(tail)
    outcome=stream.finish()
    out=b''.join(chunks);errors.seek(0);err=errors.read(2_000_001)
finally:
    if client.poll() is None:client.kill();client.wait(timeout=3)
    selector.close();errors.close();server.shutdown();server.server_close()
if len(out)>2_000_000 or len(err)>2_000_000:raise RuntimeError('oversized fixture output')
print(json.dumps({'session_id':session,'exit_status':client.returncode,'timed_out':timeout,
    'version':version,
    'stopped_by_adapter':stopped,'native_outcome':outcome,
    'local_api_request_count':len(calls),'local_api_paths':sorted(set(calls)),
    'stdout':out.decode('utf-8'),'stderr':err.decode('utf-8')}))
'''


def run(*args,timeout=10):
    result=subprocess.run(args,capture_output=True,text=True,timeout=timeout)
    if result.returncode:raise RuntimeError('fixture operation failed: '+args[0])
    return result.stdout.strip()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute-trial-fixture',action='store_true')
    parser.add_argument('--status',type=int,choices=[401,429],default=401)
    args=parser.parse_args()
    if not args.execute_trial_fixture or os.geteuid()!=0 or socket.gethostname()!='srv2065995':
        parser.error('explicit opt-in, root and exact isolated trial host required')
    name='hearth2-claude-error-'+uuid.uuid4().hex
    directory=Path(tempfile.mkdtemp(prefix='claude-error-',dir='/root/hearth-runner-trial'))
    directory.chmod(0o755)
    payload=directory/'probe.py';payload.write_text(PAYLOAD);payload.chmod(0o444)
    policy=directory/'managed-settings.json'
    policy.write_text(json.dumps(claude_managed_settings()));policy.chmod(0o444)
    container=None
    try:
        image=run('docker','image','inspect','--format','{{.Id}}','hearth2-verify:20261028')
        container=run('docker','create','--name',name,'--label','hearth2.claude-error='+name,
            '--pull','never','--network','none','--read-only','--user','1000:1000',
            '--cap-drop','ALL','--security-opt','no-new-privileges','--pids-limit','128',
            '--memory','2g','--cpus','1','--log-driver','none',
            '--tmpfs','/scratch:rw,nosuid,nodev,uid=1000,gid=1000,size=64m',
            '--tmpfs','/tmp:rw,nosuid,nodev,uid=1000,gid=1000,size=64m',
            '--env','PYTHONDONTWRITEBYTECODE=1',
            '--mount','type=bind,src='+CLAUDE+',dst=/usr/local/bin/claude,readonly',
            '--mount','type=bind,src='+str(policy)+',dst=/etc/claude-code/managed-settings.json,readonly',
            '--mount','type=bind,src='+str(payload)+',dst=/opt/probe.py,readonly',
            '--mount','type=bind,src='+str(Path(__file__).resolve().parents[2]/'mcp/memory')+',dst=/opt/hearth,readonly',
            image,'python','/opt/probe.py',str(args.status))
        raw=run('docker','start','--attach',container,timeout=35)
        observed=json.loads(raw)
        private=directory/'native-output.json';private.write_text(json.dumps(observed,indent=2)+'\n');private.chmod(0o600)
        decoder=JsonLines();events=decoder.feed(observed['stdout'].encode())+decoder.finish()
        result={'session_id':observed['session_id'],'exit_status':observed['exit_status'],
            'version':observed['version'],
            'fake_api_status':args.status,'output_observation_only':True,
            'stopped_by_adapter':observed['stopped_by_adapter'],
            'native_state':observed['native_outcome']['state'],
            'timed_out':observed['timed_out'],'local_api_request_count':observed['local_api_request_count'],
            'event_types':sorted({str(event.get('type')) for event in events}),
            'rate_limit_events':[event.get('rate_limit_info') for event in events if event.get('type')=='rate_limit_event'],
            'result_subtypes':[event.get('subtype') for event in events if event.get('type')=='result'],
            'network':'none','real_credentials_used':False,'provider_connected':False,
            'model_called':False,'synthetic_cli_user_input':True,
            'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
        assert observed['local_api_request_count']>0,'native client did not exercise the fake API'
        assert not observed['timed_out'],'adapter failed to stop the native retry'
        assert observed['stopped_by_adapter'],'no typed native stop observed'
        assert observed['local_api_request_count']==1,'native client retried before containment stop'
        assert observed['native_outcome']['state']==('authentication_stop' if args.status==401 else 'rate_limit_stop')
    finally:
        if container is not None:
            current=json.loads(run('docker','inspect',container))[0]
            if current['Config']['Labels'].get('hearth2.claude-error')!=name:
                raise RuntimeError('fixture ownership mismatch')
            run('docker','rm','--force',container)
            if run('docker','container','ls','--all','--filter','name=^/'+name+'$',
                   '--format','{{.Names}}'):raise RuntimeError('fixture cleanup unconfirmed')
    result['container_cleanup_verified']=True
    (directory/'receipt.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'receipt_directory':str(directory),**result},sort_keys=True))


if __name__=='__main__':main()
