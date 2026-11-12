"""Bounded Linux stdio port for an already isolated, root-selected app-server.

Owns no process, credentials, container, turn, cleanup or launch authority.
One canonical turn is available only through the bounded public turn_start API.
"""
from dataclasses import dataclass
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import math
import os
import selectors
import threading
import time
import uuid


def canonical_object(value):
    if type(value) is not dict: raise ValueError('object required')
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True,
                      allow_nan=False).encode('ascii')


def _pairs(items):
    result={}
    for k,v in items:
        if k in result: raise ValueError('duplicate field')
        result[k]=v
    return result


def _constant(value): raise ValueError('nonfinite value')


def _decode(raw):
    value=json.loads(raw.decode('utf-8'),object_pairs_hook=_pairs,parse_constant=_constant)
    stack=[(value,0)]
    while stack:
        item,depth=stack.pop()
        if depth>32: raise ValueError('nested frame')
        if isinstance(item,str): item.encode('utf-8')
        elif isinstance(item,dict): stack.extend((x,depth+1) for pair in item.items() for x in pair)
        elif isinstance(item,list): stack.extend((x,depth+1) for x in item)
        elif isinstance(item,float) and not math.isfinite(item): raise ValueError('nonfinite value')
    if type(value) is not dict: raise ValueError('object frame required')
    return value


class NativeRpcError(RuntimeError):
    def __init__(self,method,rpc_id,code,response_sha256=None,*,response=None):
        self.method,self.rpc_id,self.code,self.response_sha256=method,rpc_id,code,response_sha256
        self.response=response
        super().__init__('native RPC '+code)


@dataclass(frozen=True)
class NativeReply:
    method: str
    rpc_id: int
    session_id: str
    canonical: bytes
    received_at: str
    received_monotonic: float

    @property
    def sha256(self): return hashlib.sha256(self.canonical).hexdigest()

    @property
    def value(self): return _decode(self.canonical)['result']


class NativeRpcClient:
    def __init__(self,reader,writer,*,timeout_seconds=15,max_frame=1_000_000,
                 max_total=16_000_000,clock=None,monotonic=time.monotonic,
                 max_turn_events=10000,max_turn_bytes=8_000_000,turn_timeout_seconds=45):
        if (os.name!='posix' or type(timeout_seconds) not in (int,float)
                or not math.isfinite(timeout_seconds) or not 0<timeout_seconds<=30
                or type(max_frame) is not int or not 128<=max_frame<=1_000_000
                or type(max_total) is not int or not max_frame<=max_total<=16_000_000):
            raise NativeRpcError('configuration',None,'invalid_limits_or_platform')
        self.reader,self.writer=reader,writer
        self.timeout,self.max_frame,self.max_total=timeout_seconds,max_frame,max_total
        self.clock=clock or (lambda:datetime.now(timezone.utc))
        self.monotonic=monotonic;self.session_id=uuid.uuid4().hex
        self.last_request_id=None;self.last_request_method=None
        self._next_id=1;self._buffer=b'';self._total=0;self._notifications=[]
        self._initialized=False;self._lock=threading.RLock()
        if (type(max_turn_events) is not int or not 1<=max_turn_events<=10000
                or type(max_turn_bytes) is not int or not 1024<=max_turn_bytes<=16_000_000
                or type(turn_timeout_seconds) not in (int,float) or not math.isfinite(turn_timeout_seconds)
                or not 0<turn_timeout_seconds<=45):raise NativeRpcError('configuration',None,'invalid_turn_bounds')
        self.max_turn_events,self.max_turn_bytes=max_turn_events,max_turn_bytes
        self.turn_timeout_seconds=turn_timeout_seconds
        self._started_thread=None;self._started_request=None;self._turn_used=False;self._turn_context=None
        os.set_blocking(reader.fileno(),False);os.set_blocking(writer.fileno(),False)

    @property
    def notifications(self):return tuple(_decode(x) for x in self._notifications)

    @contextmanager
    def _serialized(self,method):
        if not self._lock.acquire(timeout=self.timeout):
            raise NativeRpcError(method,None,'serialization_timeout')
        try:yield
        finally:self._lock.release()

    def _write(self,raw,deadline):
        if len(raw)>self.max_frame:raise ValueError('request bound')
        with selectors.DefaultSelector() as selector:
            selector.register(self.writer,selectors.EVENT_WRITE)
            while raw:
                remaining=deadline-self.monotonic()
                if remaining<=0 or not selector.select(remaining):raise TimeoutError()
                try:n=os.write(self.writer.fileno(),raw)
                except BlockingIOError:continue
                if not n:raise EOFError()
                raw=raw[n:]

    def _line(self,deadline):
        with selectors.DefaultSelector() as selector:
            selector.register(self.reader,selectors.EVENT_READ)
            while True:
                if b'\n' in self._buffer:
                    line,self._buffer=self._buffer.split(b'\n',1)
                    if len(line)>self.max_frame:raise ValueError('frame bound')
                    return line
                if len(self._buffer)>self.max_frame:raise ValueError('frame bound')
                remaining=deadline-self.monotonic()
                if remaining<=0 or not selector.select(remaining):raise TimeoutError()
                try:chunk=os.read(self.reader.fileno(),min(65536,self.max_frame+1))
                except BlockingIOError:continue
                if not chunk:raise EOFError()
                self._total+=len(chunk)
                if self._total>self.max_total:raise ValueError('session output bound')
                self._buffer+=chunk

    def _exchange(self,method,params,*,before_send=None):
        if method=='turn/start' and self._turn_context is None:
            raise NativeRpcError(method,None,'public_turn_context_required')
        if method not in ('initialize','model/list','thread/start','turn/start'):
            raise NativeRpcError(method,None,'method_not_permitted')
        with self._serialized(method):
            # Authority/freshness belong at dispatch, after lock acquisition.
            # Exceptions here keep their original refusal/audit classification.
            if before_send is not None:before_send()
            ident=self._next_id;self._next_id+=1
            if ident>10000:raise NativeRpcError(method,None,'request_limit')
            self.last_request_id,self.last_request_method=ident,method
            try:
                deadline=self.monotonic()+self.timeout
                if method=='turn/start':deadline=min(deadline,self._turn_context.deadline)
                self._write(canonical_object({'id':ident,'method':method,'params':params})+b'\n',deadline)
                while True:
                    value=_decode(self._line(deadline))
                    if 'id' not in value:
                        if (type(value.get('method')) is not str or len(value['method'])>200
                                or 'result' in value or 'error' in value):
                            raise ValueError('invalid notification')
                        if method=='turn/start':self._turn_context.accept(value)
                        else:
                            if len(self._notifications)>=64:raise ValueError('control notification bound')
                            self._notifications.append(canonical_object(value))
                        continue
                    if (type(value['id']) is not int or value['id']!=ident
                            or ('result' in value)==('error' in value)):
                        raise ValueError('unexpected response identity')
                    raw=canonical_object(value)
                    now=self.clock()
                    if not isinstance(now,datetime) or now.tzinfo is None:raise ValueError('trusted UTC clock required')
                    reply=NativeReply(method,ident,self.session_id,raw,now.astimezone(timezone.utc).isoformat(),self.monotonic())
                    if 'error' in value:raise NativeRpcError(method,ident,'remote_error',reply.sha256,response=reply)
                    if type(value['result']) is not dict:raise ValueError('result object required')
                    return reply
            except NativeRpcError:raise
            except Exception:raise NativeRpcError(method,ident,'protocol_or_io_error') from None

    def initialize(self):
        with self._serialized('initialize'):
            if self._initialized:return
            self._exchange('initialize',{'clientInfo':{'name':'hearth2-root-launcher','version':'1'},
                                        'capabilities':{'experimentalApi':True}})
            try:self._write(b'{"method":"initialized"}\n',self.monotonic()+self.timeout)
            except Exception:raise NativeRpcError('initialize',self.last_request_id,'notification_failed') from None
            self._initialized=True

    def model_list(self):
        if not self._initialized:raise NativeRpcError('model/list',None,'not_initialized')
        return self._exchange('model/list',{'includeHidden':True,'limit':128})

    def thread_start(self,request,*,before_send=None):
        if not self._initialized:raise NativeRpcError('thread/start',None,'not_initialized')
        with self._serialized('thread/start'):
            raw=canonical_object(request)
            reply=self._exchange('thread/start',_decode(raw),before_send=before_send)
            self._started_thread=reply;self._started_request=raw
            return reply

    def turn_start(self,request,*,before_send,record_event,stop_workload):
        from .native_turn import run_turn
        return run_turn(self,request,before_send=before_send,record_event=record_event,stop_workload=stop_workload)
