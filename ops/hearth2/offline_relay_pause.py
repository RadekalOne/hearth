"""Trusted emergency pause. Standalone stdlib; never import staged launch code.

Installed separately in recovery/. Trust the OS, interpreter and this artifact.
The staged manifest and environment path hints are deliberately not authority.
"""
import ctypes
from ctypes import wintypes as W
import json
import os
from pathlib import Path
import re
import socket
import sqlite3
import subprocess
import sys

TASK='Hearth-Codex-Offline-Relay'
PYTHON='C:\\Python314\\python.exe'
REMOTE='/root/hearth-runner-trial/offline-relay-20261112/sandbox_controller.py'
ACTIVE=('claimed','dispatching','active','held')


def known_folder(kind):
    import uuid
    ids={'local':'F1B32785-6FBA-4FCF-9D55-7B8E7F157091','profile':'5E6C858F-0E22-4760-9AFE-EA3317B67173'}
    raw=(ctypes.c_ubyte*16).from_buffer_copy(uuid.UUID(ids[kind]).bytes_le)
    pointer=ctypes.c_void_p()
    shell=ctypes.WinDLL('shell32');ole=ctypes.WinDLL('ole32')
    shell.SHGetKnownFolderPath.argtypes=[ctypes.c_void_p,W.DWORD,W.HANDLE,ctypes.POINTER(ctypes.c_void_p)]
    shell.SHGetKnownFolderPath.restype=ctypes.c_long
    ole.CoTaskMemFree.argtypes=[ctypes.c_void_p]
    try:
        if shell.SHGetKnownFolderPath(ctypes.byref(raw),0,None,ctypes.byref(pointer))!=0:raise OSError('known folder unavailable')
        return Path(ctypes.wstring_at(pointer))
    finally:
        if pointer.value:ole.CoTaskMemFree(pointer)


def installed_root():return known_folder('local')/'Hearth/OfflineRelay'


def system_directory():
    value=ctypes.create_unicode_buffer(32768)
    k=ctypes.WinDLL('kernel32',use_last_error=True)
    if not 0<k.GetSystemDirectoryW(value,len(value))<len(value):raise OSError('system directory unavailable')
    return Path(value.value)


def host_identity():return os.name=='nt' and socket.gethostname().upper()=='RSLABINSKI-PC'


def connect(root):
    root=Path(root).absolute();path=root/'relay.sqlite3'
    if root.resolve()!=root or path.is_symlink() or not path.is_file():raise OSError('installed state unavailable')
    return sqlite3.connect(path.as_uri()+'?mode=rw',uri=True,timeout=3)


def latch(root):
    db=connect(root)
    try:
        db.row_factory=sqlite3.Row;db.execute('BEGIN IMMEDIATE')
        if db.execute("UPDATE control SET paused=1,enabled=0,epoch=epoch+1,status='paused_pending_stop' WHERE id=1").rowcount!=1:
            raise ValueError('control unavailable')
        rows=[dict(r) for r in db.execute("SELECT id,body FROM jobs WHERE state IN ('claimed','dispatching','active','held') LIMIT 2")]
        db.commit() # Persist the latch even if a recorded identity is malformed.
        if len(rows)>1:raise ValueError('ambiguous active records')
        jobs=[]
        for row in rows:
            if type(row['id']) is not str or not re.fullmatch('[0-9a-f]{32}',row['id']) or len(row['body'])>16384:
                raise ValueError('recorded identity unavailable')
            body=json.loads(row['body'])
            if type(body) is not dict or body.get('kind') not in {'windows','trial'}:raise ValueError('unknown workload kind')
            jobs.append({'id':row['id'],'kind':body['kind']})
        return jobs
    finally:db.close()


def settle(root,jobs,stops,disabled):
    db=connect(root)
    try:
        with db:
            db.execute('BEGIN IMMEDIATE')
            for job in jobs:
                if stops.get(job['id']) is True:
                    db.execute("UPDATE jobs SET state='paused' WHERE id=? AND state IN ('claimed','dispatching','active','held')",(job['id'],))
            remaining=db.execute("SELECT count(*) FROM jobs WHERE state IN ('claimed','dispatching','active','held')").fetchone()[0]
            control=db.execute('SELECT paused,enabled FROM control WHERE id=1').fetchone()
            complete=disabled and not remaining and control==(1,0) and all(stops.get(j['id']) is True for j in jobs)
            status='paused' if complete else 'paused_pending_stop'
            db.execute('UPDATE control SET status=? WHERE id=1',(status,))
        return status
    finally:db.close()


def stop_windows(ident):
    import time
    class Accounting(ctypes.Structure):
        _fields_=[('times',ctypes.c_longlong*4),('faults',W.DWORD),('total',W.DWORD),('active',W.DWORD),('terminated',W.DWORD)]
    k=ctypes.WinDLL('kernel32',use_last_error=True)
    k.OpenJobObjectW.argtypes=[W.DWORD,W.BOOL,W.LPCWSTR];k.OpenJobObjectW.restype=W.HANDLE
    k.TerminateJobObject.argtypes=[W.HANDLE,W.UINT];k.CloseHandle.argtypes=[W.HANDLE]
    k.QueryInformationJobObject.argtypes=[W.HANDLE,ctypes.c_int,ctypes.c_void_p,W.DWORD,ctypes.c_void_p]
    h=k.OpenJobObjectW(0x0004|0x0008,False,'Local\\HearthOfflineRelay-'+ident)
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


class RecoveryPorts:
    def __init__(self,root):self.root=Path(root).absolute()

    def disable(self):
        def quote(value):return "'"+str(value).replace("'","''")+"'"
        program=self.root/'program';argument=f'-I "{program / "offline_relay.py"}" check --state "{self.root / "relay.sqlite3"}"'
        script=("try{$t=Get-ScheduledTask -TaskPath '\\' -TaskName '"+TASK+"' -ErrorAction Stop}catch{"
            "if($_.FullyQualifiedErrorId -like 'CmdletizationQuery_NotFound_TaskName*'){exit 0};exit 2};"
            "if($t.Description -ne 'Hearth offline relay disabled candidate' -or @($t.Actions).Count -ne 1){exit 2};"
            "$a=$t.Actions[0];if($a.Execute -ne "+quote(PYTHON)+" -or $a.Arguments -ne "+quote(argument)+
            " -or $a.WorkingDirectory -ne "+quote(program)+
            "){exit 2};$t|Disable-ScheduledTask|Out-Null;"
            "if((Get-ScheduledTask -TaskPath '\\' -TaskName '"+TASK+"').Settings.Enabled){exit 2};exit 0")
        try:
            return subprocess.run([str(system_directory()/'WindowsPowerShell/v1.0/powershell.exe'),'-NoProfile','-NonInteractive','-Command',script],
                stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=30).returncode==0
        except (OSError,subprocess.TimeoutExpired):return False

    def stop(self,job):
        ident=job['id']
        if type(ident) is not str or not re.fullmatch('[0-9a-f]{32}',ident):return False
        if job['kind']=='windows':return stop_windows(ident)
        if job['kind']!='trial':return False
        command=[str(system_directory()/'OpenSSH/ssh.exe'),'-T','-o','BatchMode=yes','-o','IdentityAgent=none','-o','IdentitiesOnly=yes',
            '-o','StrictHostKeyChecking=yes','-o','ConnectTimeout=8','-i',str(known_folder('profile')/'.ssh/hermes-key'),
            'root@179.236.82.242',f'python3 {REMOTE} stop {ident}']
        try:
            p=subprocess.run(command,stdin=subprocess.DEVNULL,capture_output=True,timeout=25,check=True)
            if len(p.stdout)>32768:return False
            result=json.loads(p.stdout)
            return type(result) is dict and result.get('job')==ident and result.get('confirmed_empty') is True
        except (OSError,ValueError,subprocess.SubprocessError):return False


def pause(root,ports):
    jobs=[];stops={};latched=False
    try:jobs=latch(root);latched=True
    except Exception:pass
    if latched:
        for job in jobs:
            try:stops[job['id']]=ports.stop(job) is True
            except Exception:stops[job['id']]=False
    try:disabled=ports.disable() is True
    except Exception:disabled=False
    status='paused_pending_stop'
    if latched:
        try:status=settle(root,jobs,stops,disabled)
        except Exception:pass
    return {'state':status,'scheduler_disabled':disabled,'latch_confirmed':latched,'stops':stops}


def main():
    if len(sys.argv)!=1 or not host_identity():return 3
    try:root=installed_root();result=pause(root,RecoveryPorts(root))
    except Exception:result={'state':'paused_pending_stop','scheduler_disabled':False,'latch_confirmed':False,'stops':{}}
    print(json.dumps(result,sort_keys=True))
    return 0 if result['state']=='paused' else 2


if __name__=='__main__':raise SystemExit(main())
