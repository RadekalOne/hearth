"""Pinned native stdio, capacity observations and an explicit closed financial gate.
No refresh/reset/purchase method is permitted. Metadata never starts a thread/turn.
"""
import base64,ctypes,hashlib,json,math,os,queue,signal,subprocess,sys,tempfile,threading,time,uuid
from ctypes import wintypes as W
from datetime import datetime,timezone
from pathlib import Path
from relay_matrix import decode

MODEL='gpt-6.1-sol'
class NativeRefused(RuntimeError):pass


def sanitize_observation(account,limits,models,now,evidence):
    bucket=limits.get('rateLimitsByLimitId',{}).get('codex') if type(limits.get('rateLimitsByLimitId')) is dict else None
    if bucket is None:bucket=limits.get('rateLimits')
    rates={}
    if type(bucket) is dict:
        for k in ['limitId','primary','secondary','credits','rateLimitReachedType','spendControlReached']:
            if k in bucket:
                value=bucket[k]
                allowed={'primary':('usedPercent','windowDurationMins','resetsAt'),
                         'secondary':('usedPercent','windowDurationMins','resetsAt'),
                         'credits':('hasCredits','unlimited','balance')}.get(k)
                if allowed and type(value) is dict:value={a:value[a] for a in allowed if a in value and type(value[a]) in (int,float,bool,type(None))}
                elif allowed and value is not None:value=None
                elif not allowed and type(value) not in (str,bool,type(None)):value=None
                if k=='limitId' and value!='codex':value=None
                if k=='rateLimitReachedType' and value not in (None,'primary','secondary'):value='unknown'
                if k=='spendControlReached' and type(value) is not bool:value=None
                rates[k]=value
    entries=models.get('data');present=(type(entries) is list and models.get('nextCursor') is None and
        any(type(x) is dict and x.get('model',x.get('id'))==MODEL for x in entries))
    a=account.get('account');account_type=a.get('type') if type(a) is dict else None
    if type(account_type) is not str or account_type not in {'chatgpt','apiKey'}:account_type=None
    required=account.get('requiresOpenaiAuth')
    if type(required) is not bool:required=None
    return {'observed_at':now.astimezone(timezone.utc).isoformat(),'account_type':account_type,
        'requires_auth':required,'model_present':present,'binary_verified':True,
        'rates':rates,'rpc_evidence':evidence}


def assess_capacity(observation,now):
    result={'capacity_available':False,'inference_authorized':False,'included_only_verified':False,'reason':'capacity_unverified'}
    try:
        o=observation;t=datetime.fromisoformat(o['observed_at']);age=(now-t).total_seconds();r=o['rates'];c=r.get('credits')
        if not 0<=age<=60 or o.get('account_type')!='chatgpt' or o.get('requires_auth') is not True or o.get('binary_verified') is not True or o.get('model_present') is not True:return result
        if r.get('limitId','codex')!='codex' or r.get('rateLimitReachedType') is not None or r.get('spendControlReached') is True:return result
        if type(c) is not dict or c.get('hasCredits') is not False or c.get('unlimited') is not False:
            result['reason']='credit_fallback_unknown_or_available';return result
        used=[]
        for k in ['primary','secondary']:
            if k not in r:return result
            w=r[k]
            if w is None:continue
            p=w.get('usedPercent') if type(w) is dict else None;reset=w.get('resetsAt') if type(w) is dict else None
            if type(p) not in (int,float) or not math.isfinite(p) or not 0<=p<100 or type(reset) is not int or reset<=now.timestamp():return result
            used.append(p)
        if not used:return result
        result.update(capacity_available=True,reason='financial_authority_and_route_boundary_required',used_percent=used,observed_at=o['observed_at'])
    except (KeyError,TypeError,ValueError,OverflowError):pass
    return result


def authorize_turn(observation,*,approval,financial_boundary,work,now):
    if not assess_capacity(observation,now)['capacity_available']:raise NativeRefused('capacity_unverified')
    # The pinned account schema exposes quota/credits, not a server-enforced
    # per-run monetary ceiling. Never promote a caller dict or quota snapshot.
    if approval is None:raise NativeRefused('paid_run_not_approved')
    raise NativeRefused('financial_route_boundary_unverified')


def read_selected_auth(path,now):
    path=Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size>65536:raise NativeRefused('selected_auth_unavailable')
    try:
        value=decode(path.read_bytes());tokens=value.get('tokens',{});token=tokens.get('access_token');account=tokens.get('account_id')
        if value.get('OPENAI_API_KEY') or type(token) is not str or type(account) is not str or not account:raise ValueError()
        pieces=token.split('.')
        if len(pieces)!=3:raise ValueError()
        payload=decode(base64.urlsafe_b64decode(pieces[1]+'='*(-len(pieces[1])%4)))
        if type(payload.get('exp')) is not int or payload['exp']<now.timestamp()+120:raise ValueError()
        return {'accessToken':token,'chatgptAccountId':account,'account_sha256':hashlib.sha256(account.encode()).hexdigest()}
    except Exception:raise NativeRefused('selected_auth_unavailable_or_expiring') from None


class ProcessOwner:
    """Windows: suspended creation -> Job assignment -> resume; crash closes job.
    POSIX fixture uses its own process group. No child runs before containment.
    """
    def __init__(self,command,env,cwd,job_id=None):
        self.job=None;self.confirmed_empty=False;self.closed=False
        if os.name=='nt':
            from offline_relay_windows import kernel,Limits
            k=kernel();self.k=k
            from offline_relay_windows import name
            self.job=k.CreateJobObjectW(None,name(job_id) if job_id else 'Local\\HearthNative-'+uuid.uuid4().hex)
            if not self.job:raise NativeRefused('native_job_unavailable')
            limits=Limits();limits.basic.flags=0x2000|0x8;limits.basic.active_limit=16
            if not k.SetInformationJobObject(self.job,9,ctypes.byref(limits),ctypes.sizeof(limits)):
                k.CloseHandle(self.job);raise NativeRefused('native_job_unavailable')
            self.process=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=env,cwd=cwd,creationflags=0x4|0x08000000)
            try:
                if not k.AssignProcessToJobObject(self.job,int(self.process._handle)):raise NativeRefused('native_containment_failed')
                self._resume(self.process.pid)
            except BaseException:self.process.kill();self.close();raise
        else:self.process=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=env,cwd=cwd,start_new_session=True)
    def _resume(self,pid):
        class Entry(ctypes.Structure):
            _fields_=[('size',W.DWORD),('usage',W.DWORD),('thread',W.DWORD),('owner',W.DWORD),('base',W.LONG),('delta',W.LONG),('flags',W.DWORD)]
        k=self.k;k.CreateToolhelp32Snapshot.argtypes=[W.DWORD,W.DWORD];k.CreateToolhelp32Snapshot.restype=W.HANDLE
        k.Thread32First.argtypes=[W.HANDLE,ctypes.POINTER(Entry)];k.Thread32Next.argtypes=[W.HANDLE,ctypes.POINTER(Entry)]
        k.OpenThread.argtypes=[W.DWORD,W.BOOL,W.DWORD];k.OpenThread.restype=W.HANDLE;k.ResumeThread.argtypes=[W.HANDLE];k.ResumeThread.restype=W.DWORD
        snapshot=k.CreateToolhelp32Snapshot(4,0);ids=[]
        if snapshot==ctypes.c_void_p(-1).value:raise NativeRefused('native_thread_unavailable')
        try:
            row=Entry();row.size=ctypes.sizeof(row);ok=k.Thread32First(snapshot,ctypes.byref(row))
            while ok:
                if row.owner==pid:ids.append(row.thread)
                ok=k.Thread32Next(snapshot,ctypes.byref(row))
        finally:k.CloseHandle(snapshot)
        if len(ids)!=1:raise NativeRefused('native_startup_identity_ambiguous')
        thread=k.OpenThread(2,False,ids[0])
        if not thread:raise NativeRefused('native_thread_unavailable')
        try:
            if k.ResumeThread(thread)!=1:raise NativeRefused('native_resume_failed')
        finally:k.CloseHandle(thread)
    def close(self):
        if self.closed:return self.confirmed_empty
        self.closed=True
        if self.job:
            from offline_relay_windows import Accounting
            k=self.k;k.TerminateJobObject(self.job,137);end=time.monotonic()+5
            while time.monotonic()<end:
                row=Accounting()
                if k.QueryInformationJobObject(self.job,1,ctypes.byref(row),ctypes.sizeof(row),None) and row.active==0:self.confirmed_empty=True;break
                time.sleep(.02)
            k.CloseHandle(self.job);self.job=None
        elif os.name!='nt':
            try:os.killpg(self.process.pid,signal.SIGKILL)
            except ProcessLookupError:pass
        try:self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:pass
        if os.name!='nt':
            try:os.killpg(self.process.pid,0)
            except ProcessLookupError:self.confirmed_empty=True
        for stream in [self.process.stdin,self.process.stdout,self.process.stderr]:
            try:stream.close()
            except Exception:pass
        return self.confirmed_empty


class NativeSession:
    @classmethod
    def fixture(cls,command,root,timeout=5):return cls(command,root,timeout=timeout,fixture=True)
    @classmethod
    def pinned(cls,binary,binary_sha256,root,*,auth=None,timeout=10,check_active=lambda:True,job_id=None):
        if job_id is None:raise NativeRefused('durable_native_owner_required')
        binary=Path(binary)
        if binary.is_symlink() or not binary.is_file() or hashlib.sha256(binary.read_bytes()).hexdigest()!=binary_sha256:raise NativeRefused('native_binary_pin_mismatch')
        command=[str(binary),'-c','model_provider="openai"','-c','model="'+MODEL+'"','-c','approval_policy="never"','-c','sandbox_mode="read-only"','-c','features.shell_tool=false','-c','features.apps=false','-c','features.plugins=false','-c','web_search="disabled"','app-server','--listen','stdio://']
        return cls(command,root,auth=auth,timeout=timeout,check_active=check_active,job_id=job_id)
    def __init__(self,command,root,*,auth=None,timeout=5,fixture=False,check_active=lambda:True,job_id=None):
        self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True);self.timeout=timeout;self.check_active=check_active;self.auth=auth
        self.home=Path(tempfile.mkdtemp(prefix='native-',dir=self.root));self.confirmed_empty=False;self.counter=0;self.evidence={};self.notifications=[]
        self.fixture_mode=fixture;self.turn_methods=False;self.total=0;self.q=queue.Queue(maxsize=128);self.deadline=time.monotonic()+min(60,max(1,timeout*6))
        env={k:os.environ[k] for k in ['SystemRoot','WINDIR','COMSPEC'] if k in os.environ}
        env.update(CODEX_HOME=str(self.home),HOME=str(self.home),USERPROFILE=str(self.home),TEMP=str(self.home),TMP=str(self.home),NO_COLOR='1')
        try:
            if not check_active():raise NativeRefused('native_authority_revoked_before_spawn')
            self.owner=ProcessOwner(command,env,self.home,job_id=job_id)
        except BaseException:self._remove_home();raise
        self.process=self.owner.process
        def read():
            try:
                while True:
                    line=self.process.stdout.readline(1048577)
                    self.q.put(line,timeout=1)
                    if not line:break
            except Exception:
                try:self.q.put_nowait(b'')
                except queue.Full:pass
        def discard():
            try:
                while self.process.stderr.read(4096):pass
            except Exception:pass
        self.reader=threading.Thread(target=read,daemon=True);self.reader.start();threading.Thread(target=discard,daemon=True).start()
    def __enter__(self):return self
    def __exit__(self,*args):self.close()
    def _remove_home(self):
        import shutil
        if self.home.parent.resolve()!=self.root.resolve() or not self.home.name.startswith('native-'):raise NativeRefused('private native home differs')
        if self.home.exists():shutil.rmtree(self.home)
    def close(self):
        self.confirmed_empty=self.owner.close();self.reader.join(timeout=1)
        if self.confirmed_empty:self._remove_home()
        return self.confirmed_empty
    def _send(self,value):
        if not self.check_active() or time.monotonic()>=self.deadline:raise NativeRefused('native_authority_or_deadline')
        raw=json.dumps(value,allow_nan=False,separators=(',',':')).encode()+b'\n'
        if len(raw)>131072:raise NativeRefused('native_request_bound')
        result=queue.Queue(maxsize=1)
        def write():
            try:self.process.stdin.write(raw);self.process.stdin.flush();result.put(True)
            except Exception:result.put(False)
        writer=threading.Thread(target=write,daemon=True);writer.start()
        end=min(self.deadline,time.monotonic()+self.timeout)
        while time.monotonic()<end:
            if not self.check_active():break
            try:
                if result.get(timeout=min(.05,max(.001,end-time.monotonic()))):return
                raise NativeRefused('native_write_unknown')
            except queue.Empty:pass
        self.owner.close();writer.join(timeout=.5)
        raise NativeRefused('native_write_timeout_or_authority')
    def call(self,method,params=None):
        if method not in ({'initialize','account/login/start','account/read','account/rateLimits/read','model/list'} | ({'thread/start','turn/start'} if self.turn_methods else set())):raise NativeRefused('metadata_method_refused')
        self.counter+=1;ident=self.counter;self._send({'id':ident,'method':method,**({'params':params} if params is not None else {})})
        end=min(self.deadline,time.monotonic()+self.timeout);count=0
        while time.monotonic()<end:
            if not self.check_active():raise NativeRefused('native_authority_revoked')
            try:raw=self.q.get(timeout=min(.1,max(.001,end-time.monotonic())))
            except queue.Empty:continue
            self.total+=len(raw);count+=1
            if not raw or len(raw)>1048576 or self.total>8388608 or count>128:raise NativeRefused('native_stream_bound_or_exit')
            try:value=decode(raw)
            except Exception:raise NativeRefused('native_invalid_json') from None
            if type(value) is not dict:raise NativeRefused('native_invalid_envelope')
            if 'method' in value:
                if 'id' in value:raise NativeRefused('native_server_request_refused')
                if self.turn_methods:
                    if len(self.notifications)>=128:raise NativeRefused('native_notification_bound')
                    self.notifications.append(value)
                continue
            if value.get('id')!=ident or type(value.get('result')) is not dict or 'error' in value:raise NativeRefused('native_rpc_refused')
            self.evidence[method]={'id':ident,'sha256':hashlib.sha256(raw).hexdigest()};return value['result']
        raise NativeRefused('native_rpc_timeout')
    def metadata(self):
        self.call('initialize',{'clientInfo':{'name':'hearth-relay','version':'1'},'capabilities':{'experimentalApi':True}});self._send({'method':'initialized'})
        if self.auth:
            self.call('account/login/start',{'type':'chatgptAuthTokens','accessToken':self.auth['accessToken'],'chatgptAccountId':self.auth['chatgptAccountId']})
        account=self.call('account/read',{'refreshToken':False});limits=self.call('account/rateLimits/read');models=self.call('model/list',{'includeHidden':True,'limit':128})
        return sanitize_observation(account,limits,models,datetime.now(timezone.utc),dict(self.evidence))

    def fixture_proposal(self,prompt):
        """Explicit credential-free protocol fixture. Not a live send capability."""
        if not self.fixture_mode or self.auth:raise NativeRefused('fixture_only')
        if type(prompt) is not str or len(prompt.encode())>65536:raise NativeRefused('prompt_bound')
        self.turn_methods=True
        self.call('initialize',{'clientInfo':{'name':'hearth-relay-fixture','version':'1'}});self._send({'method':'initialized'})
        thread=self.call('thread/start',{'model':MODEL,'modelProvider':'openai','cwd':str(self.home),'approvalPolicy':'never',
            'sandbox':'read-only','ephemeral':True,'baseInstructions':'Return only a JSON changes proposal. No tools.'})
        tid=thread.get('thread',{}).get('id')
        if type(tid) is not str or not tid or len(tid)>200:raise NativeRefused('thread_identity')
        turn=self.call('turn/start',{'threadId':tid,'model':MODEL,'input':[{'type':'text','text':prompt}]})
        turnid=turn.get('turn',{}).get('id')
        if type(turnid) is not str or not turnid or len(turnid)>200:raise NativeRefused('turn_identity')
        texts=[];count=0
        while time.monotonic()<self.deadline:
            if not self.check_active():raise NativeRefused('native_authority_revoked')
            if self.notifications:value=self.notifications.pop(0)
            else:
                try:raw=self.q.get(timeout=.1)
                except queue.Empty:continue
                self.total+=len(raw)
                if not raw or len(raw)>1048576 or self.total>8388608:raise NativeRefused('turn_stream_bound')
                value=decode(raw)
            count+=1
            if count>4096 or type(value) is not dict or 'id' in value:raise NativeRefused('turn_stream_or_tool_refused')
            method=value.get('method');params=value.get('params')
            if type(params) is not dict:raise NativeRefused('turn_event_shape')
            if method in {'item/completed','turn/completed'}:
                if params.get('threadId')!=tid:raise NativeRefused('turn_scope')
            if method=='item/completed':
                if params.get('turnId')!=turnid:raise NativeRefused('turn_scope')
                item=params.get('item',{})
                if item.get('type')=='agentMessage':
                    text=item.get('text')
                    if type(text) is not str or len(text.encode())>131072 or texts:raise NativeRefused('proposal_output_bound')
                    texts.append(text)
                elif item.get('type') not in {'reasoning','plan'}:raise NativeRefused('tool_item_refused')
            if method=='turn/completed':
                t=params.get('turn',{})
                if t.get('id')!=turnid or t.get('status')!='completed' or len(texts)!=1:raise NativeRefused('turn_incomplete')
                return decode(texts[0])
        raise NativeRefused('turn_deadline')
