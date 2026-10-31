"""Direct-profile HTTP MCP discovery against Hearth broker with synthetic data.

No real login, HM service, provider connection or inference. Root and exact
isolated trial host opt-in required. Optional native tool exercises use synthetic
CLI input and fake loopback model responses. This is native compatibility and
local policy evidence, not fixed-destination egress or full runner acceptance.
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
from hearth2.native_policy import codex_requirements,claude_managed_settings
from hearth2.native_profiles import codex_config

CODEX='/usr/local/lib/node_modules/@openai/codex/node_modules/@openai/codex-linux-x64/vendor/x86_64-unknown-linux-musl/bin/codex'
CLAUDE='/usr/local/lib/node_modules/@anthropic-ai/claude-code/bin/claude.exe'
PAYLOAD=r"""
import json,os,subprocess,threading,time,uuid,sys,selectors,tempfile,secrets
sys.path.insert(0,'/opt/hearth')
from hearth2.native_profiles import claude_arguments
from hearth2.native_output import decode_object
provider=sys.argv[1];exercise_tools=sys.argv[2]=='1';expire_before_read=sys.argv[3]=='1';exercise_codex=sys.argv[4]=='1'
from pathlib import Path
from datetime import datetime,timedelta,timezone
import uvicorn
from hearth2.schema import Schema
from hearth2.store import Store,Principal
from hearth2.broker import Broker
from hearth2.broker_http import create_app
methods=[];auth_failures=[];calls=[];rpc_shapes=[]
path=Path('/scratch/fixture-record.db');Schema.initialize(path,enabled=True)
clock=[datetime.now(timezone.utc)]
store=Store(path,clock=lambda:clock[0]);human=Principal('fixture-human','human');controller=Principal('fixture-controller','controller')
agent=provider+'-fixture'
project=store.create_project(human,{'title':'Synthetic native MCP fixture'})
fields={'recipient':agent,'ask':'Read synthetic memory','done_means':'Fixture evidence',
        'inputs':['drawer_fixture'],'return':'Fixture reports'}
plan=store.create_plan(human,project['id'],{'content_ref':'synthetic-fixture',
                       'actions':{'probe':{**fields,'requires':{}}}})
card=store.create_decision(controller,plan['id'],intended_subject=human.id,
    expires_at=(datetime.now(timezone.utc)+timedelta(minutes=5)).isoformat())
store.record_decision(human,card['id'],1,'approve','synthetic offline fixture approval')
store.set_role(human,agent,{'model':'gpt-6.1-sol' if provider=='codex' else 'sonnet',
    'family':'openai' if provider=='codex' else 'anthropic','role':'senior'})
task=store.create_task(controller,{'project_id':project['id'],'plan_id':plan['id'],
                                 'action_id':'probe',**fields})
claim=store.claim(controller,task['id'],expected_revision=1,request_id='fixture-mcp')
def upstream(tool,arguments):
    calls.append(tool)
    row={'drawer_id':arguments.get('drawer_id','drawer_fixture'),'wing':'trial',
         'room':'native','content':'Synthetic task-scoped memory only.'}
    return row if tool=='memory_get' else {'results':[row]}
broker=Broker(store,controller,upstream);cap=broker.mint(controller,claim,wing='trial',room='native')
app=create_app(broker)
@app.middleware('http')
async def observe(request,call_next):
    if request.method=='POST':
        raw=await request.body();message=json.loads(raw);methods.append(message.get('method'))
        params=message.get('params',{});rpc_shapes.append({'method':message.get('method'),'params_keys':sorted(params)})
        if request.headers.get('authorization')!='Bearer '+cap:auth_failures.append(True)
    return await call_next(request)
server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=8010,log_level='critical',access_log=False))
server_thread=threading.Thread(target=server.run,daemon=True);server_thread.start()
end=time.monotonic()+5
while not server.started:
    if not server_thread.is_alive() or time.monotonic()>end:raise RuntimeError('fixture broker startup failed')
    time.sleep(0.01)
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
fake_requests=[];fake_codex_requests=[]
class FakeModel(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_POST(self):
        length=int(self.headers.get('Content-Length','0'))
        if not 0<=length<=2_000_000:raise RuntimeError('oversized fake model request')
        body=json.loads(self.rfile.read(length))
        if provider=='codex':
            fake_codex_requests.append(body)
            if len(fake_codex_requests)>4:raise RuntimeError('unexpected fake Codex loop')
            rid='resp_fixture_'+str(len(fake_codex_requests))
            response={'id':rid,'object':'response','created_at':int(time.time()),
                      'status':'in_progress','model':body.get('model','gpt-6.1-sol'),'output':[]}
            records=[('response.created',{'type':'response.created','response':response})]
            if len(fake_codex_requests)==1:
                # Deliberately request unadvertised shell names, not merely a
                # cooperative answer based on a prompt. Real credentials absent.
                shell="python -c \"import os,pathlib; print(os.environ.get('HEARTH_BROKER_CAPABILITY')); print(pathlib.Path('/proc/%s/environ'%os.getppid()).read_bytes()); pathlib.Path('/scratch/forbidden-marker').touch()\""
                items=[{'type':'function_call','id':'fc_'+str(i),'call_id':'call_'+str(i),
                        'name':name,'arguments':json.dumps({'command':shell} if name!='exec_command' else {'cmd':shell})}
                       for i,name in enumerate(['shell_command','exec_command','shell'])]
                items += [{'type':'function_call','id':'fc_read','call_id':'call_read','namespace':'mcp__hearth',
                           'name':'memory_get','arguments':json.dumps({'drawer_id':'drawer_fixture'})},
                          {'type':'function_call','id':'fc_write','call_id':'call_write','namespace':'mcp__hearth',
                           'name':'memory_add','arguments':json.dumps({'content':'must be denied'})}]
            else:
                items=[{'type':'message','id':'msg_done','role':'assistant','status':'completed',
                        'content':[{'type':'output_text','text':'Synthetic fixture complete.','annotations':[]}]}]
            for index,item in enumerate(items):
                records.append(('response.output_item.added',{'type':'response.output_item.added','output_index':index,'item':item}))
                records.append(('response.output_item.done',{'type':'response.output_item.done','output_index':index,'item':item}))
            response={**response,'status':'completed','output':items,
                      'usage':{'input_tokens':10,'output_tokens':5,'total_tokens':15}}
            records.append(('response.completed',{'type':'response.completed','response':response}))
            data=''.join('event: '+kind+'\ndata: '+json.dumps(value)+'\n\n' for kind,value in records).encode()
            content_type='text/event-stream'
        elif 'count_tokens' in self.path:
            data=json.dumps({'input_tokens':10}).encode();content_type='application/json'
        else:
            fake_requests.append(True)
            if len(fake_requests)>4:raise RuntimeError('unexpected fake model loop')
            model=body.get('model','claude-sonnet-5')
            first=len(fake_requests)==1
            blocks=([('tool_use',{'id':'toolu_fixture_read','name':'mcp__hearth__memory_get',
                                  'input':{'drawer_id':'drawer_fixture'}}),
                     ('tool_use',{'id':'toolu_fixture_write','name':'mcp__hearth__memory_add',
                                  'input':{'content':'must be denied'}}),
                     ('tool_use',{'id':'toolu_fixture_shell','name':'Bash',
                                  'input':{'command':'touch /scratch/forbidden-marker'}})]
                    if first else [('text',{'text':'Synthetic fixture complete.'})])
            events=[('message_start',{'type':'message_start','message':{
                'id':'msg_fixture_'+str(len(fake_requests)),'type':'message','role':'assistant',
                'content':[],'model':model,'stop_reason':None,'stop_sequence':None,
                'usage':{'input_tokens':10,'output_tokens':0}}})]
            for index,(kind,value) in enumerate(blocks):
                if kind=='tool_use':
                    start={'type':kind,'id':value['id'],'name':value['name'],'input':{}}
                    delta={'type':'input_json_delta','partial_json':json.dumps(value['input'])}
                else:start={'type':'text','text':''};delta={'type':'text_delta','text':value['text']}
                events.extend([('content_block_start',{'type':'content_block_start','index':index,'content_block':start}),
                    ('content_block_delta',{'type':'content_block_delta','index':index,'delta':delta}),
                    ('content_block_stop',{'type':'content_block_stop','index':index})])
            events.extend([('message_delta',{'type':'message_delta','delta':{'stop_reason':'tool_use' if first else 'end_turn',
                'stop_sequence':None},'usage':{'output_tokens':5}}),('message_stop',{'type':'message_stop'})])
            data=''.join('event: '+kind+'\ndata: '+json.dumps(value)+'\n\n' for kind,value in events).encode()
            content_type='text/event-stream'
        self.send_response(200);self.send_header('Content-Type',content_type)
        self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
fake_model=ThreadingHTTPServer(('127.0.0.1',8099),FakeModel)
threading.Thread(target=fake_model.serve_forever,daemon=True).start()
env={'PATH':'/usr/local/bin:/usr/bin:/bin','HOME':'/scratch','LANG':'C.UTF-8',
     'HEARTH_BROKER_CAPABILITY':cap}
if provider=='codex':
    env['CODEX_HOME']='/scratch';args=['app-server','--listen','stdio://']
    if exercise_codex:env['HEARTH_FIXTURE_API_KEY']='fixture-not-a-real-key'
    if exercise_codex:
        Path('/scratch/auth.json').write_text(json.dumps({'auth_mode':'apikey','OPENAI_API_KEY':'fixture-not-a-real-key'}))
else:
    env.update(CLAUDE_CONFIG_DIR='/scratch/claude',DISABLE_AUTOUPDATER='1',
        CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC='1',ANTHROPIC_API_KEY='fixture-not-a-real-key',
        ANTHROPIC_BASE_URL='http://127.0.0.1:8099' if exercise_tools else 'http://127.0.0.1:9')
    native_session=str(uuid.uuid4())
    args=claude_arguments(model='sonnet',session_id=native_session,context='Synthetic startup; no task or inference.')
version=subprocess.check_output(['/usr/local/bin/native','--version'],env=env,text=True,timeout=10).strip()
if version!=('codex-cli 0.154.0' if provider=='codex' else '2.1.280 (Claude Code)'):
    raise RuntimeError('unreviewed native version')
errors=tempfile.TemporaryFile()
client=subprocess.Popen(['/usr/local/bin/native']+args,env=env,cwd='/scratch',
    stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=errors)
selector=selectors.DefaultSelector();selector.register(client.stdout,selectors.EVENT_READ)
buffer=b'';seen=[];output_bytes=0

def send(value):
    client.stdin.write(json.dumps(value).encode()+b'\n');client.stdin.flush()

def receive(match):
    global buffer,output_bytes
    deadline=time.monotonic()+20
    while time.monotonic()<deadline:
        if b'\n' in buffer:
            line,buffer=buffer.split(b'\n',1);value=decode_object(line);seen.append(value)
            if match(value):return value
            continue
        if selector.select(0.1):
            chunk=os.read(client.stdout.fileno(),65536)
            if not chunk:raise RuntimeError('native client ended before control response')
            output_bytes+=len(chunk)
            if output_bytes>4_000_000:raise RuntimeError('native control output exceeded bound')
            buffer+=chunk
    raise RuntimeError('native control response deadline')

result=None;failure=None
try:
    if provider=='codex':
        send({'id':1,'method':'initialize','params':{'clientInfo':{'name':'hearth2-direct-mcp-fixture','version':'1'},
                                                  'capabilities':{'experimentalApi':True}}})
        assert 'error' not in receive(lambda x:x.get('id')==1)
        send({'method':'initialized'})
        send({'id':2,'method':'thread/start','params':{'cwd':'/scratch','model':'gpt-6.1-sol',
             'approvalPolicy':'never','sandbox':'read-only','ephemeral':True}})
        started=receive(lambda x:x.get('id')==2)
        assert 'error' not in started
        thread=started['result']['thread']['id']
        send({'id':3,'method':'mcpServerStatus/list','params':{'threadId':thread,'limit':10,'detail':'toolsAndAuthOnly'}})
        status=receive(lambda x:x.get('id')==3)
        assert 'error' not in status
        entries=status['result']['data']
        assert len(entries)==1 and entries[0]['name']=='hearth'
        names=sorted(entries[0].get('tools',{}))
        assert names==['memory_get','memory_search']
        if expire_before_read:clock[0]+=timedelta(seconds=901)
        send({'id':4,'method':'mcpServer/tool/call','params':{'threadId':thread,
             'server':'hearth','tool':'memory_get','arguments':{'drawer_id':'drawer_fixture'}}})
        read=receive(lambda x:x.get('id')==4)
        if expire_before_read:
            assert calls==[] and (isinstance(read.get('error'),dict) or read.get('result',{}).get('isError') is True)
            assert methods.count('tools/call')==1,'expired read silently retried'
        else:assert 'error' not in read and calls==['memory_get']
        result={'server':'hearth','tools':names,'native_mcp_read_forwarded':not expire_before_read,
                'expired_capability_typed_error':expire_before_read,
                'effective_sandbox':started['result'].get('sandbox')}
        if exercise_codex:
            send({'id':5,'method':'turn/start','params':{'threadId':thread,
                'input':[{'type':'text','text':'Synthetic tool-policy check only.'}]}})
            ack=receive(lambda x:x.get('id')==5);assert 'error' not in ack
            completed=receive(lambda x:x.get('method')=='turn/completed')
            assert len(fake_codex_requests)==2,'native loop did not finish in two fake responses'
            assert completed['params']['turn']['status']=='completed'
            assert calls==['memory_get','memory_get'],'native tool loop did not perform its permitted read'
            offered=fake_codex_requests[0]['tools']
            assert {x.get('name') for x in offered}=={'list_mcp_resources','list_mcp_resource_templates',
                'read_mcp_resource','request_user_input','mcp__hearth'},'unexpected native tool declaration'
            namespaces=[x for x in offered if x.get('type')=='namespace']
            assert len(namespaces)==1 and namespaces[0]['name']=='mcp__hearth'
            assert {x.get('name') for x in namespaces[0]['tools']}=={'memory_get','memory_search'},'unexpected namespaced tool'
            outputs={x.get('call_id'):x.get('output') for x in fake_codex_requests[1].get('input',[]) if x.get('type')=='function_call_output'}
            assert all(outputs.get('call_'+str(i))=='unsupported call: '+name for i,name in enumerate(['shell_command','exec_command','shell'])),'shell not explicitly refused'
            assert 'unsupported' in outputs.get('call_write',''),'forbidden memory write not refused'
            assert 'Synthetic task-scoped memory only.' in json.dumps(outputs.get('call_read')),'permitted read did not reach model input'
            assert not Path('/scratch/forbidden-marker').exists(),'disabled shell executed'
            assert cap not in json.dumps(seen) and cap not in json.dumps(fake_codex_requests),'synthetic capability leaked'
            result.update(synthetic_cli_user_input=True,fake_model_responses=len(fake_codex_requests),
                          forbidden_shell_refused=True,forbidden_write_refused=True,
                          shell_not_advertised=True,parent_environment_read_refused=True,
                          capability_not_in_output=True,fixture_provider_override=True)

    else:
        send({'type':'control_request','request_id':'1','request':{'subtype':'initialize','hooks':{},'sdkMcpServers':[]}})
        response=receive(lambda x:x.get('type')=='control_response' and x.get('response',{}).get('request_id')=='1')
        assert response['response']['subtype']=='success'
        for attempt in range(10):
            key=str(attempt+2)
            send({'type':'control_request','request_id':key,'request':{'subtype':'mcp_status'}})
            status=receive(lambda x:x.get('type')=='control_response' and x.get('response',{}).get('request_id')==key)
            assert status['response']['subtype']=='success'
            entries=status['response']['response']['mcpServers']
            if entries and entries[0].get('status')=='connected':break
            time.sleep(0.1)
        assert len(entries)==1 and entries[0]['name']=='hearth' and entries[0]['status']=='connected'
        names=sorted(tool['name'] for tool in entries[0].get('tools',[]))
        assert names==['memory_get','memory_search']
        result={'server':'hearth','tools':names,'native_mcp_read_forwarded':False,
                'permission_mode':response['response']['response'].get('current_permission_mode')}
        if exercise_tools:
            if expire_before_read:clock[0]+=timedelta(seconds=901)
            send({'type':'user','session_id':native_session,'uuid':str(uuid.uuid4()),
                  'parent_tool_use_id':None,'message':{'role':'user','content':'Synthetic tool-policy check only.'}})
            completed=receive(lambda x:x.get('type')=='result')
            attempted=set();denied=set()
            for message in seen:
                content=message.get('message',{}).get('content',[])
                if not isinstance(content,list):continue
                for block in content:
                    if block.get('type')=='tool_use':attempted.add(block.get('name'))
                    if block.get('type')=='tool_result' and block.get('is_error') is True:
                        denied.add(block.get('tool_use_id'))
            assert {'mcp__hearth__memory_get','mcp__hearth__memory_add','Bash'}<=attempted
            if expire_before_read:
                assert calls==[] and 'toolu_fixture_read' in denied,'expired read was not visibly denied'
                assert methods.count('tools/call')==1,'expired read silently retried'
            else:assert calls==['memory_get'],'forbidden tool reached synthetic upstream'
            assert {'toolu_fixture_write','toolu_fixture_shell'}<=denied
            assert not Path('/scratch/forbidden-marker').exists(),'native shell tool escaped its policy'
            result.update(native_mcp_read_forwarded=not expire_before_read,expired_capability_typed_error=expire_before_read,forbidden_write_refused=True,
                          forbidden_shell_refused=True,fake_model_responses=len(fake_requests),
                          synthetic_cli_user_input=True)

    assert not auth_failures and 'initialize' in methods and 'tools/list' in methods
except BaseException as error:
    failure=type(error).__name__
finally:
    if client.poll() is None:client.kill()
    client.wait(timeout=5);client.stdin.close();client.stdout.close();selector.close()
    fake_model.shutdown();fake_model.server_close()
    server.should_exit=True;server_thread.join(timeout=5)
    if server_thread.is_alive():raise RuntimeError('fixture broker shutdown unconfirmed')
    errors.seek(0);stderr=errors.read(1_000_001).decode('utf-8')
    errors.close()
    if cap in stderr:failure='SyntheticCapabilityInNativeStderr'
private={'provider':provider,'version':version,'result':result,'failure':failure,'native_messages':seen,
         'native_stderr':stderr,'mcp_methods':methods,'mcp_rpc_shapes':rpc_shapes,'mcp_auth_failures':len(auth_failures),'fake_codex_requests':fake_codex_requests}
print(json.dumps(private))
"""


def command(*args,timeout=10):
    result=subprocess.run(args,capture_output=True,text=True,timeout=timeout)
    if result.returncode:raise RuntimeError('fixture host operation failed: '+args[0])
    return result.stdout.strip()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute-trial-fixture',action='store_true')
    parser.add_argument('--provider',choices=['codex','claude'],required=True)
    parser.add_argument('--exercise-claude-tools',action='store_true')
    parser.add_argument('--expire-before-read',action='store_true')
    parser.add_argument('--exercise-codex-tools',action='store_true')
    args=parser.parse_args()
    if not args.execute_trial_fixture or os.geteuid()!=0 or socket.gethostname()!='srv2065995':
        parser.error('explicit opt-in, root and exact isolated trial host required')
    if args.exercise_claude_tools and args.provider!='claude':parser.error('synthetic tool loop is Claude-only')
    if args.expire_before_read and args.provider=='claude' and not args.exercise_claude_tools:parser.error('Claude expiry requires the synthetic tool loop')
    if args.exercise_codex_tools and (args.provider!='codex' or args.expire_before_read):parser.error('synthetic Codex loop is positive Codex-only')
    provider=args.provider;name='hearth2-direct-mcp-'+uuid.uuid4().hex
    directory=Path(tempfile.mkdtemp(prefix='direct-mcp-',dir='/root/hearth-runner-trial'));directory.chmod(0o755)
    payload=directory/'probe.py';payload.write_text(PAYLOAD);payload.chmod(0o444)
    policy=directory/'policy';policy.write_text(codex_requirements() if provider=='codex' else json.dumps(claude_managed_settings()));policy.chmod(0o444)
    config=directory/'config.toml';native_config=codex_config(model='gpt-6.1-sol')
    if args.exercise_codex_tools:
        native_config=native_config.replace('forced_login_method = "chatgpt"','forced_login_method = "api"').replace('model_provider = "openai"','model_provider = "hearth-fixture"')
        native_config+='\n[model_providers.hearth-fixture]\nname = "OpenAI synthetic fixture only"\nbase_url = "http://127.0.0.1:8099/v1"\nwire_api = "responses"\nenv_key = "HEARTH_FIXTURE_API_KEY"\nrequires_openai_auth = false\n'
    config.write_text(native_config);config.chmod(0o444)
    container=None
    try:
        image=command('docker','image','inspect','--format','{{.Id}}','hearth2-verify:20261028')
        mounts=['--mount','type=bind,src='+str(policy)+',dst='+('/etc/codex/requirements.toml' if provider=='codex' else '/etc/claude-code/managed-settings.json')+',readonly']
        if provider=='codex':mounts+=['--mount','type=bind,src='+str(config)+',dst=/scratch/config.toml,readonly']
        container=command('docker','create','--name',name,'--label','hearth2.direct-mcp='+name,
            '--pull','never','--network','none','--add-host','hearth-broker:127.0.0.1',
            '--read-only','--user','1000:1000','--cap-drop','ALL','--security-opt','no-new-privileges',
            '--pids-limit','128','--memory','2g','--cpus','1','--log-driver','none',
            '--tmpfs','/scratch:rw,nosuid,nodev,uid=1000,gid=1000,size=64m',
            '--tmpfs','/tmp:rw,nosuid,nodev,uid=1000,gid=1000,size=64m',
            '--env','PYTHONDONTWRITEBYTECODE=1',
            '--mount','type=bind,src='+(CODEX if provider=='codex' else CLAUDE)+',dst=/usr/local/bin/native,readonly',
            '--mount','type=bind,src='+str(payload)+',dst=/opt/probe.py,readonly',
            '--mount','type=bind,src='+str(Path(__file__).resolve().parents[2]/'mcp/memory')+',dst=/opt/hearth,readonly',
            *mounts,image,'python','/opt/probe.py',provider,'1' if args.exercise_claude_tools else '0','1' if args.expire_before_read else '0','1' if args.exercise_codex_tools else '0')
        raw=command('docker','start','--attach',container,timeout=65)
        private=directory/'native-observation.json';private.write_text(raw+'\n');private.chmod(0o600)
        observed=json.loads(raw)
        if observed['failure'] is not None:raise RuntimeError('native MCP compatibility failed; private evidence '+str(private))
        result={'provider':provider,'version':observed['version'],**observed['result'],
            'authenticated_mcp_discovery':True,'model_called':False,'real_credentials_used':False,
            'network':'none/loopback broker with synthetic upstream only',
            'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    finally:
        if container is not None:
            config=json.loads(command('docker','inspect',container))[0]
            if config['Config']['Labels'].get('hearth2.direct-mcp')!=name:raise RuntimeError('fixture ownership mismatch')
            command('docker','rm','--force',container)
            if command('docker','container','ls','--all','--filter','name=^/'+name+'$','--format','{{.Names}}'):
                raise RuntimeError('fixture cleanup unconfirmed')
    result['container_cleanup_verified']=True
    (directory/'receipt.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'receipt_directory':str(directory),**result},sort_keys=True))


if __name__=='__main__':main()
