"""One canonical root-owned turn, reducing bounded native events, no OS authority."""
from dataclasses import dataclass
import hashlib
import json
from .native_output import CodexTurn
from .native_rpc import NativeRpcError,canonical_object,_decode


@dataclass(frozen=True)
class NativeTurnResult:
    thread_id:str
    turn_id:str
    rpc_id:int
    session_id:str
    event_count:int
    event_sha256:str
    canonical:bytes

    @property
    def native_result(self):return json.loads(self.canonical)


class TurnEvents:
    def __init__(self,client,thread_id,deadline,fence):
        self.client,self.thread_id=client,thread_id
        self.deadline,self.fence=deadline,fence
        self.turn_id=None;self.reducer=None;self.pending=[]
        self.count=0;self.bytes=0;self.digest=hashlib.sha256()

    def accept(self,value):
        self.check()
        raw=canonical_object(value)
        self.count+=1;self.bytes+=len(raw)
        if self.count>self.client.max_turn_events or self.bytes>self.client.max_turn_bytes:
            raise ValueError('turn event bound')
        self.digest.update(raw+b'\n')
        if self.reducer is None:self.pending.append(raw)
        else:self.reduce(value)

    def check(self):
        if self.client.monotonic()>=self.deadline:raise TimeoutError()
        if self.fence() is not True:raise ValueError('turn authority refused')

    def bind(self,turn_id):
        self.turn_id=turn_id;self.reducer=CodexTurn(thread_id=self.thread_id,turn_id=turn_id)
        for raw in self.pending:self.reduce(_decode(raw))
        self.pending=[]

    def reduce(self,value):
        params=value.get('params',{});method=value.get('method')
        if method in {'item/completed','thread/tokenUsage/updated','error','turn/completed'}:
            if type(params) is not dict:raise ValueError('turn params')
            turn=params.get('turn',{}).get('id') if method=='turn/completed' else params.get('turnId')
            if params.get('threadId')!=self.thread_id or turn!=self.turn_id:raise ValueError('foreign turn event')
            item=params.get('item',{})
            if (method=='item/completed' and type(item) is dict and item.get('type')=='agentMessage'
                    and len(item.get('text','').encode('utf-8'))>16384):raise ValueError('final text bound')
        self.reducer.accept(value)

    @property
    def complete(self):return self.reducer is not None and self.reducer.terminal is not None


def _request(client,request):
    if (type(request) is not dict or any(type(k) is not str for k in request)
            or set(request)!={'threadId','input'} or type(request['threadId']) is not str
            or type(request['input']) is not list or len(request['input'])!=1):raise ValueError('canonical turn fields')
    item=request['input'][0]
    if (type(item) is not dict or set(item)!={'type','text'} or any(type(k) is not str for k in item)
            or type(item['type']) is not str or item['type']!='text' or type(item['text']) is not str
            or not item['text'].strip() or len(item['text'].encode('utf-8'))>2048):raise ValueError('canonical text input')
    expected={'model':'gpt-6.1-sol','cwd':'/scratch','approvalPolicy':'never','sandbox':'read-only','ephemeral':True}
    started=client._started_thread
    if (client._started_request!=canonical_object(expected) or started is None
            or started.session_id!=client.session_id):raise ValueError('owned safe thread required')
    value=started.value;thread=value.get('thread',{}).get('id')
    if (type(thread) is not str or not 1<=len(thread)<=256 or request['threadId']!=thread
            or value.get('model')!='gpt-6.1-sol' or value.get('approvalPolicy')!='never'
            or value.get('sandbox')!={'type':'readOnly','networkAccess':False}):raise ValueError('effective thread profile differs')
    return _decode(canonical_object(request)),thread


def run_turn(client,request,*,before_send,record_event,stop_workload):
    if any(not callable(x) for x in [before_send,record_event,stop_workload]):
        raise NativeRpcError('turn/start',None,'trusted_turn_callbacks_required')
    with client._serialized('turn/start'):
        if client._turn_used:raise NativeRpcError('turn/start',None,'turn_already_consumed')
        client._turn_used=True
        thread_id=turn_id=None;stream=None
        def audit(kind,**extra):
            row={'kind':kind,'rpc_session':client.session_id,'thread_id':thread_id,'turn_id':turn_id,**extra}
            if record_event(row) is not True:raise ValueError('durable turn audit required')
        try:
            owned,thread_id=_request(client,request)
            deadline=client.monotonic()+client.turn_timeout_seconds
            stream=TurnEvents(client,thread_id,deadline,before_send)
            def dispatch():
                if before_send() is not True:raise ValueError('turn authority refused')
                audit('native_turn_dispatch_intent',rpc_id=client._next_id)
                # Durable audit can block across expiry/revocation. Recheck the
                # live authority after it, immediately before transport write.
                stream.check()
            client._turn_context=stream
            reply=client._exchange('turn/start',owned,before_send=dispatch)
            turn=reply.value.get('turn',{});turn_id=turn.get('id')
            if (type(turn_id) is not str or not 1<=len(turn_id)<=256
                    or turn.get('status') not in {'inProgress','completed','failed','interrupted'}):raise ValueError('turn identity')
            stream.bind(turn_id)
            audit('native_turn_started',rpc_id=reply.rpc_id,response_sha256=reply.sha256)
            stream.check()
            while not stream.complete:
                if client.monotonic()>=deadline:raise TimeoutError()
                value=_decode(client._line(deadline))
                if 'id' in value or type(value.get('method')) is not str or len(value['method'])>200:
                    raise ValueError('unexpected native request or response')
                if 'result' in value or 'error' in value:raise ValueError('ambiguous notification')
                stream.accept(value)
            stream.check()
            result=stream.reducer.outcome()
            text=result.get('text')
            if text is not None and len(text.encode('utf-8'))>16384:raise ValueError('final text bound')
            audit('native_turn_terminal',rpc_id=reply.rpc_id,native_state=result['state'],
                event_count=stream.count,event_sha256=stream.digest.hexdigest())
            stream.check()
            return NativeTurnResult(thread_id,turn_id,reply.rpc_id,client.session_id,stream.count,
                stream.digest.hexdigest(),canonical_object(result))
        except Exception:
            try:confirmed=stop_workload() is True
            except Exception:confirmed=False
            try:audit('native_turn_failure',stop_confirmed=confirmed,
                event_count=stream.count if stream else 0)
            except Exception:pass
            error=NativeRpcError('turn/start',client.last_request_id,'turn_refused_or_incomplete')
            error.stop_confirmed=confirmed
            raise error from None
        finally:client._turn_context=None
