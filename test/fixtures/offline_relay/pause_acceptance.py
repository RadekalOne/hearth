"""EXPLICIT integration only: harmless active fixture, real owned-task disable.

The installed relay stays paused/disabled throughout. A synthetic external fixture
is recorded in its DB solely so the real recovery entry can stop that identity.
No controller/worker activation, model, provider or production call occurs.
"""
import argparse,hashlib,importlib.util,json,os,sqlite3,subprocess,sys,time,uuid
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[3]/'ops/hearth2'))
sys.path.insert(0,str(Path(__file__).resolve().parent))
import offline_relay_pause as source_pause
from offline_relay_state import State
from offline_relay_ports import RemoteSandbox
from acceptance import create


def windows_active(ident):
    from offline_relay_windows import kernel,name,Accounting
    import ctypes
    k=kernel();h=k.OpenJobObjectW(0x4,False,name(ident))
    if not h:return 0 if ctypes.get_last_error()==2 else -1
    try:
        a=Accounting()
        if not k.QueryInformationJobObject(h,1,ctypes.byref(a),ctypes.sizeof(a),None):return -1
        return a.active
    finally:k.CloseHandle(h)


def run(mode,failure,output):
    if not source_pause.host_identity():raise RuntimeError('exact host required')
    root=source_pause.installed_root();real=State(root/'relay.sqlite3')
    control=real.control()
    if not control['paused'] or control['enabled'] or control['activation_at'] is not None:raise RuntimeError('installed relay must remain inactive')
    if any(j['state'] in source_pause.ACTIVE for j in real.jobs()):raise RuntimeError('preserve existing active work')
    directory=output.parent/(mode+'-'+failure+'-'+uuid.uuid4().hex);directory.mkdir(parents=True)
    fixture,job=create(directory,mode);job['kind']=mode
    result={'mode':mode,'failure':failure,'synthetic':True,'model_calls':0,'activation':False,'production_contact':False,'job':job['id']}
    process=None;original=None;manifest_backup=None
    target=root/'program/offline_relay_ports.py';manifest=root/'manifest.json'
    registered=False;started=time.monotonic()
    try:
        if mode=='windows':
            from offline_relay_windows import start
            process,ready=start(fixture,job);result['active_before']=windows_active(job['id'])>=2
        else:
            remote=RemoteSandbox();remote.call('start',job['id']);info=remote.call('inspect',job['id'])
            result['active_before']=info.get('running') is True
        if not result['active_before']:raise RuntimeError('active workload not observed')
        # Record only the verified harmless fixture identity; never enable this DB.
        body={**job,'synthetic':True,'acceptance':'independent-pause-integrity'}
        with real.tx() as db:
            c=db.execute('SELECT paused,enabled,epoch FROM control WHERE id=1').fetchone()
            if tuple(c[:2])!=(1,0):raise RuntimeError('relay changed; refuse fixture registration')
            db.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,NULL)',(job['id'],'pause-acceptance-'+job['id'],1,'active',c['epoch'],json.dumps(body)))
        registered=True;env=dict(os.environ)
        if failure=='staged':
            original=target.read_bytes();target.chmod(0o666);target.write_bytes(b'raise RuntimeError("damaged stage must not execute")\n')
        elif failure=='manifest':
            manifest_backup=root/('manifest.pause-test-'+job['id']);manifest.rename(manifest_backup);manifest.mkdir()
        else:
            decoy=directory/'decoy/Hearth/OfflineRelay';decoy.mkdir(parents=True)
            decoy_state=State(decoy/'relay.sqlite3')
            with decoy_state.tx() as db:db.execute('UPDATE control SET epoch=4242')
            env['LOCALAPPDATA']=str(directory/'decoy')
        failed=subprocess.run([source_pause.PYTHON,'-I',str(root/'program/offline_relay.py'),'status','--state',str(real.path)],
            capture_output=True,env=env,timeout=10)
        result['launch_verification_refused']=failed.returncode!=0
        # This is the fixed installed desktop shortcut target, not a staged import.
        recovery=root/'recovery/offline_relay_pause.py'
        p=subprocess.run([source_pause.PYTHON,'-I',str(recovery)],capture_output=True,text=True,env=env,timeout=65)
        result['recovery_exit']=p.returncode;result['pause']=json.loads(p.stdout)
        if mode=='windows':
            process.wait(timeout=5);process.stdout.close();result['observed_empty']=windows_active(job['id'])==0
            result['keeper_exit']=process.returncode
        else:result['observed_empty']=RemoteSandbox().call('inspect',job['id']).get('absent') is True
        result['elapsed_seconds']=round(time.monotonic()-started,3)
        result['relay_remained_disabled']=real.control()['enabled']==0 and real.control()['activation_at'] is None
        if failure=='localappdata':result['decoy_untouched']=decoy_state.control()['epoch']==4242
        if not (p.returncode==0 and result['pause']['state']=='paused' and result['observed_empty'] and
            result['launch_verification_refused'] and result['relay_remained_disabled'] and result.get('decoy_untouched',True)):
            raise RuntimeError('physical pause acceptance failed')
        result['passed']=True
    finally:
        if original is not None:target.write_bytes(original);target.chmod(0o444)
        if manifest_backup is not None:
            manifest.rmdir();manifest_backup.rename(manifest)
        if mode=='windows':
            from offline_relay_windows import stop
            result['final_empty']=stop(fixture,job)
            if process and process.stdout and not process.stdout.closed:process.wait(timeout=5);process.stdout.close()
        else:result['final_empty']=RemoteSandbox().call('stop',job['id']).get('confirmed_empty') is True
        if registered:
            # Reconcile only this acceptance row after its independent empty proof.
            with real.tx() as db:
                if result['final_empty']:
                    db.execute("UPDATE jobs SET state='paused',receipt=? WHERE id=?",(json.dumps({'synthetic':True,'confirmed_empty':True,'failure_case':failure}),job['id']))
        output.write_text(json.dumps(result,indent=2)+'\n')
    if not result['final_empty']:raise RuntimeError('cleanup unknown')
    print(json.dumps({'mode':mode,'failure':failure,'passed':True,'final_empty':True,'output':str(output)}))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--mode',choices=['windows','trial'],required=True)
    p.add_argument('--failure',choices=['staged','manifest','localappdata'],required=True)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args();run(a.mode,a.failure,a.output)
