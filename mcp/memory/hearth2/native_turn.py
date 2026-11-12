"""One canonical root-owned turn, reducing bounded native events, no OS authority."""
from dataclasses import dataclass
import hashlib
import json
from .native_output import CodexTurn
from .native_rpc import NativeRpcError,canonical_object,_decode


class TurnFailure(ValueError):
    """Only fixed internal cause labels, never provider/user error text."""
    pass


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
        self.last_fence=None
        self.send_state='not_sent';self.bytes_written=0;self.request_written=False
        self.rpc_id=None;self.response_sha256=None;self.stage='dispatch_fence'
        self.failure_class=None

    def write_progress(self,kind,count):
        if kind=='attempt' and self.send_state=='not_sent':
            self.send_state='send_attempted_outcome_unknown';self.request_written=None
        elif kind=='written':
            self.bytes_written+=count;self.send_state='partial_write_outcome_unknown'
        elif kind=='complete':
            self.send_state='request_written_outcome_unknown';self.request_written=True
            self.stage='await_ack'

    def accept(self,value):
        try:
            self.check()
            raw=canonical_object(value)
            self.count+=1;self.bytes+=len(raw)
            if self.count>self.client.max_turn_events or self.bytes>self.client.max_turn_bytes:
                raise TurnFailure('event_bound_exceeded')
            self.digest.update(raw+b'\n')
            if self.reducer is None:self.pending.append(raw)
            else:self.reduce(value)
        except TurnFailure as error:
            # The generic RPC envelope may sanitize this exception pre-ACK.
            # Keep only our fixed cause label in the owned turn context.
            self.failure_class=str(error);raise

    def check(self,*,force=False):
        now=self.client.monotonic()
        if now>=self.deadline:raise TurnFailure('deadline_exceeded')
        # Event-flow cadence only. Idle reads are bounded by their own deadline;
        # independent root cutoff still owns inactivity/escaped descendants.
        if force or self.last_fence is None or now-self.last_fence>=.25:
            try:allowed=self.fence()
            except Exception:raise TurnFailure('authority_check_failed') from None
            if allowed is not True:raise TurnFailure('authority_refused')
            self.last_fence=self.client.monotonic()
            if self.last_fence>=self.deadline:raise TurnFailure('deadline_exceeded')

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
    # Cover acquisition/release too: the workload already exists before the
    # public call. Inner cleanup sets handled before touching callbacks.
    scope={'entered':False,'handled':False}
    try:return _run_turn_locked(client,request,before_send=before_send,
        record_event=record_event,stop_workload=stop_workload,scope=scope)
    except BaseException as cause:
        if isinstance(cause,Exception) or scope['handled']:raise
        entered=scope['entered']
        failure={'rpc_session':client.session_id,'thread_id':None,'turn_id':None,
            'request_sha256':None,'failure_class':'interrupted',
            'stage':'outer_cleanup' if entered else 'serialization',
            'send_state':'possibly_sent_unconfirmed' if entered else 'not_sent',
            'request_written':None if entered else False,'bytes_written':None if entered else 0,
            'rpc_id':None,'response_sha256':None}
        try:confirmed=stop_workload() is True
        except BaseException:confirmed=False
        try:record_event({'kind':'native_turn_failure',**failure,'stop_confirmed':confirmed,'event_count':0})
        except BaseException:pass
        cause.stop_confirmed=confirmed;cause.failure_evidence=dict(failure)
        raise


def _run_turn_locked(client,request,*,before_send,record_event,stop_workload,scope):
    if any(not callable(x) for x in [before_send,record_event,stop_workload]):
        raise NativeRpcError('turn/start',None,'trusted_turn_callbacks_required')
    with client._serialized('turn/start'):
        scope['entered']=True
        if client._turn_used:raise NativeRpcError('turn/start',None,'turn_already_consumed')
        client._turn_used=True
        thread_id=turn_id=request_sha256=None;stream=None;stage='request_validation'
        def audit(kind,**extra):
            row={'kind':kind,'rpc_session':client.session_id,'thread_id':thread_id,'turn_id':turn_id,**extra}
            try:recorded=record_event(row)
            except Exception:raise TurnFailure('audit_unavailable') from None
            if recorded is not True:raise TurnFailure('audit_unavailable')
        try:
            owned,thread_id=_request(client,request)
            request_sha256=hashlib.sha256(canonical_object(owned)).hexdigest()
            if client.turn_timeout_seconds is None:raise TurnFailure('timeout_policy_missing')
            deadline=client.monotonic()+client.turn_timeout_seconds
            stream=TurnEvents(client,thread_id,deadline,before_send)
            def dispatch():
                stream.check(force=True)
                stream.stage='dispatch_audit'
                audit('native_turn_dispatch_intent',rpc_id=client._next_id,
                    request_sha256=request_sha256,send_state='possibly_sent_unconfirmed',
                    timeout_seconds=client.turn_timeout_seconds,fence_interval_seconds=.25)
                # Durable audit can block across expiry/revocation. Recheck the
                # live authority after it, immediately before transport write.
                stream.stage='dispatch_fence';stream.check(force=True)
            client._turn_context=stream
            reply=client._exchange('turn/start',owned,before_send=dispatch)
            stream.stage='turn_identity'
            turn=reply.value.get('turn',{});candidate_turn_id=turn.get('id')
            if (type(candidate_turn_id) is not str or not 1<=len(candidate_turn_id)<=256
                    or turn.get('status') not in {'inProgress','completed','failed','interrupted'}):raise ValueError('turn identity')
            turn_id=candidate_turn_id
            stream.bind(turn_id)
            stream.stage='started_audit'
            audit('native_turn_started',rpc_id=reply.rpc_id,response_sha256=reply.sha256)
            stream.check(force=True);stream.stage='stream_events'
            while not stream.complete:
                if client.monotonic()>=deadline:raise TimeoutError()
                value=_decode(client._line(deadline))
                if 'id' in value or type(value.get('method')) is not str or len(value['method'])>200:
                    raise ValueError('unexpected native request or response')
                if 'result' in value or 'error' in value:raise ValueError('ambiguous notification')
                stream.accept(value)
            stream.stage='terminal_fence';stream.check(force=True)
            result=stream.reducer.outcome()
            text=result.get('text')
            if text is not None and len(text.encode('utf-8'))>16384:raise ValueError('final text bound')
            stream.stage='terminal_audit'
            audit('native_turn_terminal',rpc_id=reply.rpc_id,native_state=result['state'],
                event_count=stream.count,event_sha256=stream.digest.hexdigest())
            stream.stage='terminal_fence';stream.check(force=True)
            return NativeTurnResult(thread_id,turn_id,reply.rpc_id,client.session_id,stream.count,
                stream.digest.hexdigest(),canonical_object(result))
        except BaseException as cause:
            scope['handled']=True
            if not isinstance(cause,Exception):reason='interrupted'
            elif isinstance(cause,TurnFailure):reason=str(cause)
            elif stream is None:reason='request_contract'
            elif stream.failure_class is not None:reason=stream.failure_class
            elif isinstance(cause,NativeRpcError) and cause.code=='remote_error':reason='native_remote_error'
            elif client.monotonic()>=stream.deadline:reason='deadline_exceeded'
            else:reason='native_protocol_or_io_error'
            failure={'rpc_session':client.session_id,'thread_id':thread_id,'turn_id':turn_id,
                'request_sha256':request_sha256,'failure_class':reason,'stage':stream.stage if stream else stage,
                'send_state':stream.send_state if stream else 'not_sent',
                'request_written':stream.request_written if stream else False,
                'bytes_written':stream.bytes_written if stream else 0,
                'rpc_id':stream.rpc_id if stream else None,
                'response_sha256':stream.response_sha256 if stream else None}
            try:confirmed=stop_workload() is True
            except BaseException:confirmed=False
            try:audit('native_turn_failure',stop_confirmed=confirmed,**failure,
                event_count=stream.count if stream else 0)
            except BaseException:pass
            if not isinstance(cause,Exception):
                cause.stop_confirmed=confirmed;cause.failure_evidence=dict(failure)
                raise
            error=NativeRpcError('turn/start',failure['rpc_id'],'turn_refused_or_incomplete',failure['response_sha256'])
            error.stop_confirmed=confirmed
            error.failure_evidence=dict(failure)
            raise error from None
        finally:client._turn_context=None
