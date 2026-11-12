"""Explicit manual acceptance: harmless Windows jobs and TRIAL-only containers."""
import argparse
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import time
import uuid

sys.path.insert(0,str(Path(__file__).resolve().parents[3]/'ops/hearth2'))
from offline_relay import Dispatcher,Approval,ROOM,THREAD,admit
from offline_relay_state import State
from offline_relay_ports import RemoteSandbox


def create(root,kind):
    state=State(root/'relay.sqlite3')
    with state.tx() as db:db.execute('UPDATE control SET paused=0,enabled=1')
    work={'work_id':'fixture-'+kind,'aliases':[],'generation':1,'review_event':'$synthetic-review',
        'base_commit':'a'*40,'paths':['mcp/memory/hearth2/broker.py'],'scope':'hearth2-offline'}
    proof=Approval(ROOM,THREAD,'@rad:hearth.radekal.me',work['work_id'],1,'a'*40,tuple(work['paths']),'$synthetic-approval','fixture',(),work['review_event'])
    bound=admit(work,proof,acceptance=True);bound['kind']=kind
    job=state.claim(bound)
    if not state.dispatch(job):raise RuntimeError('fixture dispatch refused')
    return state,job


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--mode',choices=['windows','trial'],required=True)
    p.add_argument('--cutoff',action='store_true',help='abandon starter and observe outside cutoff before pause')
    p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    if os.environ.get('COMPUTERNAME')!='RSLABINSKI-PC':raise SystemExit('exact laptop required')
    root=args.output.parent;root.mkdir(parents=True,exist_ok=True)
    state,job=create(root/(args.mode+'-'+uuid.uuid4().hex),args.mode);result={'started_at':datetime.now(timezone.utc).isoformat(),'mode':args.mode,
        'synthetic':True,'cutoff_test':args.cutoff,'model_calls':0,'paid_runs':False,'production_contact':False,'job':job['id']}
    try:
        def pause_process():
            p=subprocess.run([sys.executable,'-I',str(Path(__file__).resolve().parents[3]/'ops/hearth2/offline_relay.py'),
                'pause','--state',str(state.path)],capture_output=True,text=True,timeout=65,check=True)
            return json.loads(p.stdout)
        if args.mode=='windows':
            from offline_relay_windows import start,stop
            if args.cutoff:
                code='import json,sys;sys.path.insert(0,sys.argv[1]);from offline_relay_state import State;from offline_relay_windows import start;s=State(sys.argv[2]);p,r=start(s,s.jobs()[0]);print(json.dumps(r))'
                parent=subprocess.run([sys.executable,'-I','-c',code,str(Path(__file__).resolve().parents[3]/'ops/hearth2'),str(state.path)],
                    capture_output=True,text=True,timeout=10,check=True)
                result['ready']=json.loads(parent.stdout);result['starter_exit']=parent.returncode
                from offline_relay_windows import kernel,name
                import ctypes
                k=kernel();end=time.monotonic()+20
                while time.monotonic()<end:
                    h=k.OpenJobObjectW(0x4,False,name(job['id']))
                    if not h:
                        if ctypes.get_last_error()!=2:raise RuntimeError('fixture absence unknown')
                        result['cutoff_observed']=True;break
                    k.CloseHandle(h);time.sleep(.1)
                if not result.get('cutoff_observed'):raise RuntimeError('outside cutoff missing')
                result['pause']=pause_process()
            else:
                process,ready=start(state,job);result['ready']=ready
                result['pause']=pause_process();process.wait(timeout=5);process.stdout.close()
                result['keeper_exit']=process.returncode
        else:
            port=RemoteSandbox();result['start']=port.call('start',job['id'])
            for _ in range(30):
                info=port.call('inspect',job['id'])
                if info.get('probe'):break
                time.sleep(.1)
            result['isolation']=info.get('probe')
            if args.cutoff:
                end=time.monotonic()+20
                while time.monotonic()<end:
                    if port.call('inspect',job['id']).get('absent') is True:
                        result['cutoff_observed']=True;break
                    time.sleep(.2)
                if not result.get('cutoff_observed'):raise RuntimeError('outside cutoff missing')
            result['pause']=pause_process()
            result['late_start']=port.call('start',job['id'])
            c=result['isolation']
            if not (c and c['uid']==1000 and c['credentials_absent'] and c['docker_socket_absent'] and c['readonly_root']
                and c['egress_denied'] and c['scratch_writable'] and c['network_interfaces']==['lo']
                and result['late_start'].get('refused')):raise RuntimeError('isolation refusal incomplete')
        if result['pause']['state']!='paused' or state.control()['enabled']:raise RuntimeError('pause incomplete')
        result['passed']=True
    finally:
        if args.mode=='windows':
            from offline_relay_windows import stop
            result['final_empty']=stop(state,job)
        else:result['final_empty']=RemoteSandbox().call('stop',job['id']).get('confirmed_empty') is True
        args.output.write_text(json.dumps(result,indent=2)+'\n')
    if not result.get('final_empty'):raise SystemExit('cleanup unconfirmed')
    print(json.dumps({'mode':args.mode,'passed':result.get('passed',False),'final_empty':result['final_empty'],'output':str(args.output)}))
