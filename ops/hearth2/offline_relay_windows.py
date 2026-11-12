"""Windows Job Object acceptance helper. Hardcoded harmless fixture, never Codex."""
import ctypes
from ctypes import wintypes as W
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

sys.path.insert(0,str(Path(__file__).resolve().parent))
from offline_relay_state import State


def name(ident):
    if type(ident) is not str or not re.fullmatch('[0-9a-f]{32}',ident):raise ValueError('owned job identity required')
    return 'Local\\HearthOfflineRelay-'+ident


class Accounting(ctypes.Structure):
    _fields_=[('times',ctypes.c_longlong*4),('faults',W.DWORD),('total',W.DWORD),('active',W.DWORD),('terminated',W.DWORD)]


class BasicLimits(ctypes.Structure):
    _fields_=[('process_time',ctypes.c_longlong),('job_time',ctypes.c_longlong),('flags',W.DWORD),
        ('min_work',ctypes.c_size_t),('max_work',ctypes.c_size_t),('active_limit',W.DWORD),
        ('affinity',ctypes.c_size_t),('priority',W.DWORD),('scheduling',W.DWORD)]


class Limits(ctypes.Structure):
    _fields_=[('basic',BasicLimits),('io',ctypes.c_ulonglong*6),('process_memory',ctypes.c_size_t),
        ('job_memory',ctypes.c_size_t),('peak_process',ctypes.c_size_t),('peak_job',ctypes.c_size_t)]


def kernel():
    if os.name!='nt':raise RuntimeError('Windows job objects unavailable')
    k=ctypes.WinDLL('kernel32',use_last_error=True)
    for function in ['CreateJobObjectW','OpenJobObjectW','GetCurrentProcess']:getattr(k,function).restype=W.HANDLE
    k.CreateJobObjectW.argtypes=[ctypes.c_void_p,W.LPCWSTR]
    k.OpenJobObjectW.argtypes=[W.DWORD,W.BOOL,W.LPCWSTR]
    k.SetInformationJobObject.argtypes=[W.HANDLE,ctypes.c_int,ctypes.c_void_p,W.DWORD]
    k.AssignProcessToJobObject.argtypes=[W.HANDLE,W.HANDLE]
    k.QueryInformationJobObject.argtypes=[W.HANDLE,ctypes.c_int,ctypes.c_void_p,W.DWORD,ctypes.c_void_p]
    k.TerminateJobObject.argtypes=[W.HANDLE,W.UINT];k.CloseHandle.argtypes=[W.HANDLE]
    return k


def stop(state,job):
    ident=job['id'];name(ident)
    if not any(j['id']==ident and j.get('kind')=='windows' for j in state.jobs()):return False
    # Durable latch precedes inspection; a delayed keeper must acquire this
    # writer lock and recheck epoch before it can create any process/job.
    state.pause();k=kernel();h=k.OpenJobObjectW(0x0004|0x0008,False,name(ident))
    if not h:return ctypes.get_last_error()==2
    try:
        if not k.TerminateJobObject(h,137):return False
        end=time.monotonic()+5
        while time.monotonic()<end:
            a=Accounting()
            if not k.QueryInformationJobObject(h,1,ctypes.byref(a),ctypes.sizeof(a),None):return False
            if a.active==0:return True
            time.sleep(.02)
        return False
    finally:k.CloseHandle(h)


def keeper(state,ident):
    k=kernel();h=None
    with state.tx() as db:
        control=db.execute('SELECT * FROM control WHERE id=1').fetchone()
        row=db.execute('SELECT * FROM jobs WHERE id=?',(ident,)).fetchone()
        if (not row or row['state']!='dispatching' or control['paused'] or not control['enabled']
            or row['epoch']!=control['epoch'] or json.loads(row['body']).get('kind')!='windows'):
            raise RuntimeError('fixture admission refused')
        h=k.CreateJobObjectW(None,name(ident))
        if not h:raise RuntimeError('fixture job unavailable')
        limits=Limits();limits.basic.flags=0x2000|0x8;limits.basic.active_limit=8
        if not k.SetInformationJobObject(h,9,ctypes.byref(limits),ctypes.sizeof(limits)):
            k.CloseHandle(h);raise RuntimeError('fixture containment unavailable')
        if not k.AssignProcessToJobObject(h,k.GetCurrentProcess()):
            k.CloseHandle(h);raise RuntimeError('fixture containment unavailable')
        child=subprocess.Popen([sys.executable,'-I','-c',
            'import subprocess,sys,time;subprocess.Popen([sys.executable,"-I","-c","import time;time.sleep(15)"]);time.sleep(15)'],
            stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        db.execute("UPDATE jobs SET state='active' WHERE id=?",(ident,))
    print(json.dumps({'fixture':True,'job':ident,'keeper_pid':os.getpid(),'child_pid':child.pid}),flush=True)
    # Independent acceptance watchdog enforces a shorter15s fixture ceiling.
    time.sleep(15)
    k.CloseHandle(h)


def supervise(state,job,env):
    import queue,threading
    p=subprocess.Popen([sys.executable,'-I',__file__,'watch',str(state.path),job['id']],env=env,
        stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,creationflags=0x08000000)
    q=queue.Queue()
    threading.Thread(target=lambda:q.put(p.stdout.readline(4097)),daemon=True).start()
    try:
        if json.loads(q.get(timeout=5)).get('supervising')!=job['id']:raise ValueError()
    except Exception:
        state.pause();p.kill();p.wait(timeout=5);raise RuntimeError('fixture supervision unavailable') from None
    finally:p.stdout.close()
    return p


def start(state,job):
    import queue
    import threading
    env={key:os.environ[key] for key in ['SystemRoot','WINDIR'] if key in os.environ}
    supervise(state,job,env) # Must be ready before the keeper can create a workload.
    p=subprocess.Popen([sys.executable,'-I',__file__,'keep',str(state.path),job['id']],env=env,
        stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,creationflags=0x08000000)
    q=queue.Queue()
    def read():q.put(p.stdout.readline(4097))
    threading.Thread(target=read,daemon=True).start()
    try:
        raw=q.get(timeout=5);data=json.loads(raw)
        if data.get('job')!=job['id'] or not data.get('fixture'):raise ValueError()
    except Exception:
        stop(state,job);p.wait(timeout=5);p.stdout.close();raise RuntimeError('fixture startup unavailable') from None
    return p,data


if __name__=='__main__':
    action,path,ident=sys.argv[1:];name(ident);state=State(Path(path))
    if action=='keep':keeper(state,ident)
    elif action=='watch':
        # Return promptly when the keeper's Job Object has gone away; no service.
        k=kernel();end=time.monotonic()+15;saw_job=False
        print(json.dumps({'supervising':ident}),flush=True)
        while time.monotonic()<end:
            h=k.OpenJobObjectW(0x4,False,name(ident))
            if h:saw_job=True;k.CloseHandle(h)
            elif saw_job:break
            time.sleep(.1)
        else:
            job=next(j for j in state.jobs() if j['id']==ident);stop(state,job)
    else:raise SystemExit('fixture action refused')
