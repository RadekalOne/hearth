"""Piece 2 A4/A8/A9 walking fixture. Root/trial opt-in only; never a service.

Real record, claims, dispatch, Broker and native client. Synthetic approval,
memory upstream, provider, poll scheduler and output/OS composition adapters.
No credentials, account entitlement, production or RootLifecycleDriver v1 claim.
"""
import argparse
from datetime import datetime,timedelta,timezone
import hashlib
import json
import os
from pathlib import Path
import socket
import socketserver
import subprocess
import sys
import threading
import time
import uuid

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'mcp/memory'))
from hearth2.store import Store,Principal,RecordError
from hearth2.schema import Schema
from hearth2.dispatch import DispatchRegistry
from hearth2.broker import Broker,BrokerError
from hearth2.native_rpc import NativeRpcClient,NativeRpcError,_decode,canonical_object
from hearth2.native_model_audit import RootModelDecisionJournal
from hearth2.native_thread_launcher import CodexThreadLauncher
from hearth2.private_broker import PrivateBrokerChannel
from hearth2.native_profiles import codex_private_config

TRIAL=Path('/root/hearth-runner-trial')
BINARY=TRIAL/'clients/codex/0.159.1/vendor/x86_64-unknown-linux-musl/bin/codex'
BINARY_SHA='f1cd7fa4ac866c724122f173d408a95385257cbcc9ac5ce5ddba42669c74ba97'
CATALOG_SHA='719c75b77ed02c783263f8fe62532ecd0abc1d1ccf2c34b12e5d221d509995a1'
IMAGE='sha256:5e2bdb1b0d542d5039cffb8181c65930093949194a65c365dfb1b0fe13a4fa5b'
REQUEST={'model':'gpt-6.1-sol','cwd':'/scratch','approvalPolicy':'never','sandbox':'read-only','ephemeral':True}


def now():return datetime.now(timezone.utc).isoformat()
def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require_trial_host(host,uid):
    if host!='srv2065995' or uid!=0:raise RuntimeError('exact root trial host required')


def mcp_read_tools():
    return [{'name':'memory_get','description':'Read synthetic scoped memory',
        'annotations':{'readOnlyHint':True,'destructiveHint':False,'idempotentHint':True},
        'inputSchema':{'type':'object','properties':{'drawer_id':{'type':'string'}},
            'required':['drawer_id'],'additionalProperties':False}}]


def poll_once(store,controller,registry,policy_sha256):
    """One bounded snapshot scan; external wake/scheduler is explicitly a stub."""
    snapshot=store.snapshot()
    for task in snapshot['tasks']:
        if task['state']!='ready':continue
        role=next(r for r in snapshot['role_grants'] if r['agent']==task['assignee'])
        if role['model']!='gpt-6.1-sol':raise RecordError('fixture exact-model role required')
        bound=registry.claim_and_prepare(task['id'],expected_revision=task['revision'],
            request_id='walk-'+uuid.uuid4().hex,expected_role_revision=role['revision'],policy_sha256=policy_sha256)
        bound['registration']=registry.consume(bound['claim'])
        return bound
    return None


def settle(registry,claim,result,*,memory_reads,ended_at,exit_status,verified_empty,evidence):
    """Trusted fixture output bridge, not a worker-facing broker write API."""
    if result.get('state')=='completed' and 'memory_get' not in memory_reads:
        raise RecordError('fixture memory-first evidence absent')
    return registry.record_native_result(claim,result,ended_at=ended_at,exit_status=exit_status,
        containment_state='verified_empty' if verified_empty else 'unconfirmed',termination_evidence=evidence)


def command(*args,timeout=12):
    result=subprocess.run(args,capture_output=True,text=True,timeout=timeout)
    if result.returncode:raise RuntimeError('fixture host command failed: '+args[0])
    return result.stdout.strip()


def make_record(path):
    Schema.initialize(path,enabled=True);store=Store(path,deadline_seconds=120)
    human=Principal('synthetic-fixture-human','human');controller=Principal('walking-fixture','controller')
    project=store.create_project(human,{'title':'Synthetic walking skeleton only'})
    fields={'recipient':'codex','ask':'Read synthetic task memory and return closeout',
        'done_means':'Fixture evidence only','inputs':['drawer_fixture'],'return':'independent review'}
    plan=store.create_plan(human,project['id'],{'content_ref':'synthetic-fixture-plan',
        'actions':{'walk':{**fields,'requires':{}}}})
    card=store.create_decision(controller,plan['id'],intended_subject=human.id,
        expires_at=(datetime.now(timezone.utc)+timedelta(minutes=5)).isoformat())
    store.record_decision(human,card['id'],1,'approve','synthetic fixture approval, not a human deployment approval')
    store.set_role(human,'codex',{'model':'gpt-6.1-sol','family':'openai','role':'senior'})
    task=store.create_task(controller,{'project_id':project['id'],'plan_id':plan['id'],'action_id':'walk',**fields})
    return store,controller,task


def watchdog(cid,ident,directory):
    """Finite independent root fixture cutoff; no installed service/timer."""
    end=time.monotonic()+90;out={'container_id':cid,'exercise_id':ident,'triggered':False}
    while time.monotonic()<end:
        if (directory/'watch-stop').exists():break
        time.sleep(.1)
    else:
        try:
            spec=json.loads(command('docker','inspect',cid))[0]
            if spec['Id']==cid and spec['Config']['Labels'].get('hearth2.walk')==ident and spec['State']['Running']:
                command('docker','kill','--signal','KILL',cid);out['triggered']=True
        except Exception:out['inspection_error']=True
    out['completed_at']=now();(directory/'watchdog.json').write_text(json.dumps(out))


def unknown_result():
    return {'provider':'openai','state':'unknown','text':None,'stop_reason':None,
        'pause_role':False,'usage_scope':'unknown','usage':{'state':'unknown','units':None,
        'estimated_cost':None,'actual_charge':None}}


def cleanup(state,receipt):
    """Independently try every cleanup; uncertainty cannot become empty proof."""
    receipt.setdefault('verified_empty',False)
    def attempt(name,action):
        try:return action()
        except Exception as error:receipt['errors'].append(name+': '+type(error).__name__);return None
    cid=state.get('cid');directory=state['directory']
    if cid:
        spec=attempt('cleanup inspect',lambda:json.loads(command('docker','inspect',cid))[0])
        identity=bool(spec and spec['Id']==cid and spec['Config']['Labels'].get('hearth2.walk')==state.get('ident'))
        if not identity:receipt['errors'].append('cleanup identity unconfirmed')
        else:
            if spec['State']['Running']:attempt('cleanup kill',lambda:command('docker','kill','--signal','KILL',cid))
            attempt('cleanup wait',lambda:command('docker','wait',cid))
            final=attempt('cleanup final inspect',lambda:json.loads(command('docker','inspect',cid))[0])
            if final and final['Id']==cid:
                os_state=final['State']
                receipt.update(container_stopped=not os_state['Running'] and os_state['Pid']==0,
                    exit_status=os_state['ExitCode'] if not os_state['Running'] else None,
                    ended_at=os_state['FinishedAt'] if not os_state['Running'] else None)
            cg=state.get('cg')
            if cg is not None and receipt.get('container_stopped'):
                empty=attempt('cleanup cgroup',lambda:not cg.exists() or 'populated 0' in (cg/'cgroup.events').read_text())
                receipt['verified_empty']=empty is True
            if receipt.get('container_stopped'):
                attempt('cleanup remove',lambda:command('docker','rm',cid))
                absent=attempt('cleanup absence',lambda:not command('docker','container','ls','--all','--filter','id='+cid,'--format','{{.ID}}'))
                receipt['container_removed']=absent is True
        if not receipt['verified_empty']:receipt['errors'].append('cleanup workload empty unconfirmed')
    if state.get('attach'):attempt('cleanup attach',lambda:state['attach'].wait(timeout=5))
    # Never cancel the independent cutoff while workload stop is uncertain.
    if receipt.get('container_stopped') and receipt['verified_empty']:
        attempt('cleanup watchdog stop',lambda:(directory/'watch-stop').touch())
        if state.get('watch'):attempt('cleanup watchdog join',lambda:state['watch'].wait(timeout=4))
    if state.get('broker') and state.get('cap'):
        attempt('cleanup revoke',lambda:state['broker'].revoke(state['controller'],state['cap']))
    if state.get('server'):
        attempt('cleanup server shutdown',state['server'].shutdown)
        attempt('cleanup server close',state['server'].server_close)
    if state.get('private_channel'):attempt('cleanup private channel',state['private_channel'].close)


def run_case(directory,mode):
    state={'directory':directory}
    try:return _run_case(directory,mode,state)
    except Exception as error:
        receipt=state.get('receipt',{'mode':mode,'started_at':now(),'errors':[]})
        receipt['errors'].append('setup/settlement failure: '+type(error).__name__)
        cleanup(state,receipt)
        if state.get('claim'):
            claim=state['claim'];receipt.update(task_id=claim['task_id'],run_id=claim['run_id'],claim_id=claim['id'])
            try:
                finished=settle(state['registry'],claim,unknown_result(),memory_reads=[],ended_at=state['store'].now().isoformat(),
                    exit_status=receipt.get('exit_status'),verified_empty=receipt['verified_empty'],
                    evidence=['root-fixture-cleanup'] if receipt['verified_empty'] else [])
                receipt['record_run']=finished['run']
            except Exception as failed:
                receipt['errors'].append('unknown settlement unavailable: '+type(failed).__name__)
                try:
                    state['store'].reconcile(state['controller'],claim['run_id'],outcome='unknown',
                        termination_evidence=['fixture failure; native completion and/or containment not accepted'])
                except Exception as fenced:
                    receipt['errors'].append('unknown reconciliation unavailable: '+type(fenced).__name__)
        if state.get('store'):
            snapshot=state['store'].snapshot()
            receipt['task_state']=snapshot['tasks'][0]['state'] if snapshot['tasks'] else None
            (directory/'record-snapshot.json').write_text(json.dumps(snapshot,indent=2))
        receipt.update(status='failed_closed',completed_at=now())
        (directory/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
        return receipt


def _run_case(directory,mode,state):
    directory.mkdir(mode=0o700)
    store,controller,task=make_record(directory/'record.sqlite3')
    registry=DispatchRegistry(store,controller)
    state.update(store=store,controller=controller,registry=registry)
    policy={'kind':'walking-fixture-only','image':IMAGE,'network':'none','mounts':'explicit-fixture',
        'root_lifecycle_v1':False,'model':'gpt-6.1-sol','source_sha256':digest(__file__)}
    policy_raw=canonical_object(policy);(directory/'fixture-policy.json').write_bytes(policy_raw)
    bound=poll_once(store,controller,registry,hashlib.sha256(policy_raw).hexdigest());claim=bound['claim']
    state['claim']=claim
    if poll_once(store,controller,registry,hashlib.sha256(policy_raw).hexdigest()) is not None:
        raise RuntimeError('duplicate fixture dispatch')
    challenge=uuid.uuid4().hex;reads=[]
    def upstream(tool,args):
        reads.append(tool)
        row={'drawer_id':'drawer_fixture','wing':'trial','room':'skeleton','content':'synthetic-memory-'+challenge}
        return row if tool=='memory_get' else {'results':[row]}
    captured=[]
    class ObservedBroker(Broker):
        def mint(self,*args,**kwargs):
            token=super().mint(*args,**kwargs);captured.append(token);return token
    broker=ObservedBroker(store,controller,upstream)
    channel=PrivateBrokerChannel(broker,controller,claim,directory=directory,wing='trial',room='skeleton')
    state['private_channel']=channel;channel.start()
    assets=directory/'assets';assets.mkdir(mode=0o755);assets.chmod(0o755)
    closeout={'task':claim['task_id'],'attempt':claim['attempt'],'status':'done','produced':'synthetic-plan-via-stdio',
        'changed':'fixture only','unblocked':'none','memory-used':['drawer_fixture'],
        'checks-run':[{'name':'actual scoped memory read','passed':True,'evidence':'root-broker-read'}],
        'next':'independent review; no human acceptance implied'}
    (assets/'task.json').write_text(json.dumps({'mode':mode,'closeout':closeout,'challenge':challenge}))
    prior=TRIAL/'native-thread-launcher-raheblm6'
    config=codex_private_config(model='gpt-6.1-sol').replace('forced_login_method = "chatgpt"','forced_login_method = "api"')
    # Fixture-only transport substitution; never silently applied to a live profile.
    config=config.replace('model_provider = "openai"','model_provider = "hearth-fixture"')
    config+='\n[model_providers.hearth-fixture]\nname="Synthetic loopback only"\nbase_url="http://127.0.0.1:8099/v1"\nwire_api="responses"\nrequires_openai_auth=false\n'
    (assets/'config.toml').write_text(config)
    (assets/'requirements.toml').write_bytes((prior/'requirements.toml').read_bytes())
    bootstrap=Path(__file__).with_name('hearth2_walking_bootstrap.py')
    (assets/'bootstrap.py').write_bytes(bootstrap.read_bytes())
    (assets/'private_broker_bridge.py').write_bytes((Path(__file__).parents[2]/'mcp/memory/hearth2/private_broker_bridge.py').read_bytes())
    for path in assets.iterdir():path.chmod(0o444)
    ident='walk-'+uuid.uuid4().hex;cid=None;attach=None;watch=None;cg=None;turn=None
    receipt={'exercise_id':ident,'mode':mode,'started_at':now(),'host':socket.gethostname(),
        'task_id':task['id'],'run_id':claim['run_id'],'claim_id':claim['id'],'production_contacted':False,
        'activation':False,'paid_run':False,'real_credentials':False,'errors':[]}
    state.update(ident=ident,receipt=receipt)
    try:
        cid=command('docker','create','-i','--name','hearth2-'+ident,'--label','hearth2.walk='+ident,
            '--pull','never','--network','none','--add-host','hearth-broker:127.0.0.1','--read-only',
            '--user','1000:1000','--cap-drop','ALL','--security-opt','no-new-privileges',
            '--pids-limit','64','--memory','1g','--cpus','1','--log-driver','none',
            '--tmpfs','/scratch:rw,nosuid,nodev,uid=1000,gid=1000,size=64m',
            '--tmpfs','/tmp:rw,nosuid,nodev,uid=1000,gid=1000,size=64m','--workdir','/scratch',
            '--mount',f'type=bind,src={BINARY.parent.parent},dst=/opt/codex,readonly',
            '--mount',f'type=bind,src={assets},dst=/fixture,readonly',
            '--mount',f'type=bind,src={assets}/requirements.toml,dst=/etc/codex/requirements.toml,readonly',
            '--mount',f'type=bind,src={channel.socket_path},dst=/run/hearth-memory.sock,readonly',IMAGE,'python','/fixture/bootstrap.py')
        receipt['container_id']=cid
        state['cid']=cid
        watch=subprocess.Popen([sys.executable,__file__,'--watch',cid,ident,str(directory)],
            stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
        state['watch']=watch
        with (directory/'native-stderr.txt').open('wb') as stderr:
            attach=subprocess.Popen(['docker','start','--attach','--interactive',cid],
                stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=stderr,start_new_session=True)
        state['attach']=attach
        client=NativeRpcClient(attach.stdout,attach.stdin)
        client.initialize()
        spec=json.loads(command('docker','inspect',cid))[0];pid=spec['State']['Pid']
        if pid<=0:raise RuntimeError('fixture native process not running')
        rel=next(x.split(':',2)[2] for x in Path(f'/proc/{pid}/cgroup').read_text().splitlines() if x.startswith('0::'))
        cg=Path('/sys/fs/cgroup')/rel.lstrip('/')
        if cg==Path('/sys/fs/cgroup') or not cg.resolve().is_relative_to('/sys/fs/cgroup'):
            raise RuntimeError('fixture cgroup path refused')
        state['cg']=cg
        receipt['cgroup']=str(cg);receipt['cgroup_before']=(cg/'cgroup.events').read_text()
        public=json.dumps(spec)+Path(f'/proc/{pid}/environ').read_bytes().decode(errors='replace')+Path(f'/proc/{pid}/cmdline').read_bytes().decode(errors='replace')
        public+=Path(f'/proc/{pid}/root/scratch/codex-home/config.toml').read_text()
        receipt['worker_bearer_absent']=bool(captured) and all(token not in public for token in captured)
        receipt['worker_token_env_absent']='HEARTH_BROKER_CAPABILITY' not in public
        if not receipt['worker_bearer_absent'] or not receipt['worker_token_env_absent']:
            raise RuntimeError('private Broker delivery failed')
        journal=RootModelDecisionJournal(directory)
        def fence():
            channel.check()
            current=json.loads(command('docker','inspect',cid))[0]
            return (current['Id']==cid and current['State']['Running'] and current['State']['Pid']==pid
                and current['HostConfig']['NetworkMode']=='none' and current['HostConfig']['ReadonlyRootfs']
                and current['Config']['Labels'].get('hearth2.walk')==ident)
        launcher=CodexThreadLauncher(client,mounted_binary=Path(f'/proc/{pid}/root/opt/codex/bin/codex'),
            expected_binary_sha256=BINARY_SHA,expected_catalog_sha256=CATALOG_SHA,
            record_decision=journal.record,pre_thread_fence=fence)
        thread=launcher.launch_thread(REQUEST);receipt['thread_id']=thread['thread']['id']
        def stop_workload():
            current=json.loads(command('docker','inspect',cid))[0]
            if current['Id']!=cid or current['Config']['Labels'].get('hearth2.walk')!=ident:return False
            if current['State']['Running']:command('docker','kill','--signal','KILL',cid)
            command('docker','wait',cid);attach.wait(timeout=5)
            current=json.loads(command('docker','inspect',cid))[0]['State']
            return not current['Running'] and current['Pid']==0 and (not cg.exists() or 'populated 0' in (cg/'cgroup.events').read_text())
        turn=client.turn_start({'threadId':thread['thread']['id'],'input':[{'type':'text',
            'text':'Synthetic trial only: read drawer_fixture using Hearth memory, then return the structured fixture closeout.'}]},
            before_send=fence,record_event=journal.record,stop_workload=stop_workload)
        receipt.update(turn_id=turn.turn_id,native_event_count=turn.event_count,native_event_sha256=turn.event_sha256,
            usage_provenance='synthetic_provider_reported')
        (directory/'turn-result.json').write_text(json.dumps(turn.native_result,indent=2))
        client.writer.close();attach.wait(timeout=10)
    except Exception as error:
        receipt['errors'].append(type(error).__name__+': '+str(error)[:300])
        if attach and 'client' in locals():
            (directory/'native-events-failure.json').write_text(json.dumps({'last_rpc_id':client.last_request_id},indent=2))
    finally:
        cleanup(state,receipt)
        receipt['memory_reads']=reads
    completed=not receipt['errors'] and turn is not None
    result=turn.native_result if completed else unknown_result()
    settled=settle(registry,claim,result,memory_reads=reads,ended_at=now(),exit_status=receipt.get('exit_status'),
        verified_empty=receipt['verified_empty'],evidence=['root-docker-cgroup-observer:'+ident] if receipt['verified_empty'] else [])
    receipt['record_run']=settled['run'];receipt['registration_phase']=settled['registration']['phase']
    snapshot=store.snapshot();(directory/'record-snapshot.json').write_text(json.dumps(snapshot,indent=2))
    receipt['task_state']=snapshot['tasks'][0]['state'];receipt['incident_count']=len(snapshot['incidents'])
    receipt['understanding']='unknown';receipt['human_acceptance']=False
    receipt['completed_at']=now();receipt['status']='failed_closed' if receipt['errors'] else 'observed'
    (directory/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    return receipt


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute-trial-fixture',action='store_true')
    parser.add_argument('--watch',nargs=3)
    args=parser.parse_args()
    require_trial_host(socket.gethostname(),os.geteuid())
    if args.watch:
        cid,ident,directory=args.watch;watchdog(cid,ident,Path(directory));return
    if not args.execute_trial_fixture:parser.error('explicit trial opt-in required')
    if digest(BINARY)!=BINARY_SHA:raise RuntimeError('fixture binary pin mismatch')
    command('docker','image','inspect',IMAGE)
    directory=TRIAL/('walking-'+uuid.uuid4().hex);directory.mkdir(mode=0o700)
    results=[run_case(directory/'positive','positive'),run_case(directory/'missing-closeout','missing-closeout')]
    passed=(all(not r['errors'] and r.get('verified_empty') and r.get('container_removed') and r['exit_status']==0
                and r.get('worker_bearer_absent') and r.get('worker_token_env_absent') for r in results)
        and results[0].get('native_event_count',0)>64
        and results[0]['task_state']=='review' and results[0]['registration_phase']=='released'
        and results[1]['task_state']=='ready' and results[1]['incident_count']==1
        and results[1]['record_run']['closeout_validation']=='missing')
    summary={'directory':str(directory),'piece':2,'test_shapes':['A4','A8','A9'],'passed':passed,
        'full_live_acceptance':False,'results':results}
    (directory/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps({'directory':str(directory),'passed':passed,'runs':[{k:r.get(k) for k in
        ['run_id','exercise_id','task_state','exit_status','verified_empty','errors']} for r in results]}))
    raise SystemExit(0 if passed else 1)


if __name__=='__main__':main()
