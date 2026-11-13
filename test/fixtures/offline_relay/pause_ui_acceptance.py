"""Explicit visible-dialog acceptance for this program's own windows only."""
import argparse,ctypes,json,os,subprocess,sys,time
from ctypes import wintypes as W
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[3]/'ops/hearth2'))
import offline_relay_pause as recovery


def observe_and_close(process):
    user=ctypes.WinDLL('user32',use_last_error=True)
    user.GetWindowThreadProcessId.argtypes=[W.HWND,ctypes.POINTER(W.DWORD)]
    user.IsWindowVisible.argtypes=[W.HWND];user.GetWindowTextW.argtypes=[W.HWND,W.LPWSTR,ctypes.c_int]
    user.GetDlgItem.argtypes=[W.HWND,ctypes.c_int];user.GetDlgItem.restype=W.HWND
    user.PostMessageW.argtypes=[W.HWND,W.UINT,ctypes.c_size_t,ctypes.c_ssize_t]
    callback=ctypes.WINFUNCTYPE(W.BOOL,W.HWND,ctypes.c_void_p)
    user.EnumWindows.argtypes=[callback,ctypes.c_void_p];user.EnumChildWindows.argtypes=[W.HWND,callback,ctypes.c_void_p]
    events=[];found=[];end=time.monotonic()+20
    while time.monotonic()<end and process.poll() is None:
        def visit(window,param):
            pid=W.DWORD();user.GetWindowThreadProcessId(window,ctypes.byref(pid))
            title=ctypes.create_unicode_buffer(256);user.GetWindowTextW(window,title,len(title))
            if pid.value==process.pid and user.IsWindowVisible(window) and title.value=='Hearth relay pause':
                texts=[];buttons=[]
                def child(w,p):
                    text=ctypes.create_unicode_buffer(4096);user.GetWindowTextW(w,text,len(text))
                    if text.value:texts.append(text.value)
                    if text.value=='OK':buttons.append(w)
                    return True
                user.EnumChildWindows(window,callback(child),None)
                if not found:found.append({'title':title.value,'visible':True,'text':'\n'.join(texts)})
                button=buttons[0] if buttons else None
                posted=user.PostMessageW(button,0xF5,0,0) if button else False
                if len(events)<3:events.append({'button':bool(button),'posted':bool(posted),'error':ctypes.get_last_error(),'texts':texts}) # IDOK only on this child process's dialog.
            return True
        user.EnumWindows(callback(visit),None);time.sleep(.05)
    if not found or process.poll() is None:
        print(json.dumps({'found':found,'events':events,'exit':process.poll()}),flush=True);process.kill();process.wait();raise RuntimeError('owned result dialog observation/close unconfirmed')
    return found[0]


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    if not recovery.host_identity():raise SystemExit('exact approved laptop required')
    source=Path(recovery.__file__).resolve();results={}
    for state,expected in [('paused','confirmed stopped'),('paused_pending_stop','Do not resume'),('refused','not confirmed')]:
        code='import importlib.util,json,sys;s=importlib.util.spec_from_file_location("recovery_ui",sys.argv[1]);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);m.show_result(json.loads(sys.argv[2]))'
        child=subprocess.Popen([sys.executable,'-I','-c',code,str(source),json.dumps({'state':state,'synthetic':True})],
            stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=0x08000000)
        item=observe_and_close(child);child.wait(timeout=5)
        if expected not in item['text'] or child.returncode!=0:raise RuntimeError('visible state did not match')
        results[state]=item
    # The actual installed default shortcut target, not just the renderer fixture.
    target=recovery.installed_root()/'recovery/offline_relay_pause.py'
    child=subprocess.Popen([recovery.PYTHON,'-I',str(target)],stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,text=True,creationflags=0x08000000)
    results['installed_default']=observe_and_close(child)
    output,error=child.communicate(timeout=5);results['installed_result']=json.loads(output)
    if child.returncode!=0 or results['installed_result']['state']!='paused':raise RuntimeError('installed default failed')
    args.output.write_text(json.dumps({'synthetic_renderer_cases':True,'dialogs':results,'model_calls':0},indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'visible_states':list(results)[:3],'installed_default':'paused','output':str(args.output)}))
