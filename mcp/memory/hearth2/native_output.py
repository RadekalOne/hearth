"""Bounded native stdout decoding; no process, credential or launch authority.

A completed native turn is not a successful Hearth receipt. The controller must
separately bind the model/account/claim, validate closeout, observe actual exit
and prove containment empty. Raw native errors are never returned as evidence.
"""
import copy
import json
import math
from .store import RecordError


def decode_object(raw):
    """Bound both protocol envelopes and JSON hidden inside result text."""
    def pairs(values):
        result={}
        for key,value in values:
            if key in result:raise ValueError('duplicate field')
            result[key]=value
        return result
    def constant(value):raise ValueError('nonfinite value')
    def validate(value,depth=0):
        if depth>32:raise ValueError('nested output')
        if isinstance(value,str):value.encode('utf-8')
        elif isinstance(value,float) and not math.isfinite(value):raise ValueError('nonfinite value')
        elif isinstance(value,dict):
            for key,item in value.items():validate(key,depth+1);validate(item,depth+1)
        elif isinstance(value,list):
            for item in value:validate(item,depth+1)
    try:
        if isinstance(raw,str):raw=raw.encode('utf-8')
        if type(raw) is not bytes or len(raw)>1_000_000:raise ValueError('bounded bytes required')
        value=json.loads(raw.decode('utf-8'),object_pairs_hook=pairs,parse_constant=constant)
        if not isinstance(value,dict):raise ValueError('object required')
        validate(value)
        return value
    except (ValueError,TypeError,UnicodeError,RecursionError):
        raise RecordError('native JSON object unavailable or invalid') from None


class JsonLines:
    def __init__(self, *, max_line=1_000_000, max_total=16_000_000, max_records=10000):
        for value, ceiling in [(max_line,1_000_000),(max_total,16_000_000),(max_records,10000)]:
            if type(value) is not int or not 1 <= value <= ceiling:
                raise RecordError('invalid native output bound')
        self.max_line,self.max_total,self.max_records=max_line,max_total,max_records
        self.buffer=b'';self.total=0;self.records=0;self.closed=False

    def _bad(self):
        self.closed=True;self.buffer=b''
        raise RecordError('native output unavailable or invalid') from None

    def _parse(self,line):
        if len(line)>self.max_line:self._bad()
        if not line.strip():return None
        try:value=decode_object(line)
        except RecordError:self._bad()
        self.records+=1
        if self.records>self.max_records:self._bad()
        return value

    def feed(self,chunk):
        return list(self.iter_feed(chunk))

    def iter_feed(self,chunk):
        """Dispatch valid prefix records before a later parse/budget failure."""
        if self.closed or type(chunk) is not bytes:self._bad()
        remaining=self.max_total-self.total
        exceeded=len(chunk)>remaining
        accepted=chunk[:remaining]
        self.total+=len(accepted)
        self.buffer+=accepted
        while b'\n' in self.buffer:
            line,self.buffer=self.buffer.split(b'\n',1)
            value=self._parse(line)
            if value is not None:yield value
        if len(self.buffer)>self.max_line or exceeded:self._bad()

    def finish(self):
        if self.closed:self._bad()
        value=self._parse(self.buffer) if self.buffer else None
        self.buffer=b'';self.closed=True
        return [] if value is None else [value]


class CodexTurn:
    """Reduce installed 0.154.0 app-server notifications for ONE native turn.

    Thread and turn IDs come from validated controller-side start responses.
    This is a data reducer, not an executor or a provider-authentication proof.
    A typed usageLimitExceeded signal requests role pause; it never retries.
    """
    def __init__(self, *, thread_id, turn_id):
        for value in [thread_id,turn_id]:
            if not isinstance(value,str) or not value.strip() or len(value)>256:
                raise RecordError('native turn identity required')
        self.thread_id,self.turn_id=thread_id,turn_id
        self.broken=False;self.pause=False;self.terminal=None;self.status=None
        self.messages={};self.units=None;self.count=0

    def _bad(self):
        self.broken=True;self.messages={};self.units=None
        raise RecordError('native turn output unavailable or invalid') from None

    def _matching(self,params,turn):
        if not isinstance(params,dict) or not isinstance(params.get('threadId'),str):self._bad()
        if params['threadId']!=self.thread_id:return False
        if not isinstance(turn,str):self._bad()
        return turn==self.turn_id

    def _item(self,item):
        if not isinstance(item,dict):self._bad()
        if item.get('type')!='agentMessage':return
        identity,text=item.get('id'),item.get('text')
        phase=item.get('phase')
        if (not isinstance(identity,str) or not identity or not isinstance(text,str)
                or len(text.encode('utf-8'))>1_000_000
                or phase not in {None,'commentary','final_answer'}):self._bad()
        value=(text,phase)
        if self.terminal is not None and self.messages.get(identity)!=value:self._bad()
        if identity in self.messages and self.messages[identity]!=value:self._bad()
        self.messages[identity]=value

    def _tokens(self,units):
        required=['inputTokens','outputTokens','totalTokens','cachedInputTokens','reasoningOutputTokens']
        if not isinstance(units,dict):self._bad()
        selected={key:units.get(key) for key in required}
        if 'cacheWriteInputTokens' in units:selected['cacheWriteInputTokens']=units['cacheWriteInputTokens']
        if any(type(value) is not int or not 0<=value<2**63 for value in selected.values()):self._bad()
        return selected

    def accept(self,event):
        try:
            self._accept(event)
        except (RecordError,ValueError,TypeError,UnicodeError,RecursionError,OverflowError):
            self._bad()

    def _accept(self,event):
        if self.broken or not isinstance(event,dict):self._bad()
        self.count+=1
        if self.count>10000:self._bad()
        method=event.get('method')
        if method not in {'turn/completed','item/completed','thread/tokenUsage/updated','error'}:return
        params=event.get('params')
        if not isinstance(params,dict):self._bad()
        turn=params.get('turn') if method=='turn/completed' else None
        if method=='turn/completed' and not isinstance(turn,dict):self._bad()
        identity=turn.get('id') if turn is not None else params.get('turnId')
        if not self._matching(params,identity):return
        if method=='item/completed':
            self._item(params.get('item'))
        elif method=='thread/tokenUsage/updated':
            usage=params.get('tokenUsage')
            if not isinstance(usage,dict):self._bad()
            self._tokens(usage.get('last'))
            self.units=self._tokens(usage.get('total'))
        elif method=='error':
            error=params.get('error')
            if not isinstance(error,dict) or type(params.get('willRetry')) is not bool:self._bad()
            if error.get('codexErrorInfo')=='usageLimitExceeded':self.pause=True
        else:
            try:canonical=json.dumps(turn,allow_nan=False,sort_keys=True,separators=(',',':'))
            except (ValueError,TypeError,RecursionError):self._bad()
            if self.terminal is not None and self.terminal!=canonical:self._bad()
            status=turn.get('status')
            if status not in {'completed','failed','interrupted'} or not isinstance(turn.get('items'),list):self._bad()
            error=turn.get('error')
            if error is not None and not isinstance(error,dict):self._bad()
            if status=='completed' and error is not None:self._bad()
            if isinstance(error,dict) and error.get('codexErrorInfo')=='usageLimitExceeded':self.pause=True
            for item in turn['items']:self._item(item)
            self.terminal,self.status=canonical,status

    def outcome(self):
        messages=[text for text,phase in self.messages.values() if phase!='commentary' and text.strip()]
        text=messages[-1] if messages else None
        state=('unknown' if self.broken else 'allowance_stop' if self.pause else self.status or 'unknown')
        if state=='completed' and text is None:state='unknown'
        return {'provider':'openai','state':state,'text':text if state=='completed' else None,
            'pause_role':self.pause,'stop_reason':'allowance_stop' if self.pause else None,
            'usage_scope':'native_thread_total' if self.units is not None else 'unknown',
            'usage':{'state':'measured' if self.units is not None else 'unknown',
                     'units':copy.deepcopy(self.units),'estimated_cost':None,'actual_charge':None}}


class ClaudeTurn:
    """Reduce ONE root prompt in a fresh, non-resumed native Claude session.

    api_retry auth/429 shapes were observed against installed 2.1.280 and a fake
    local API. rate_limit_event is the documented SDK contract, not proof that
    real subscription exhaustion has been exercised. Stop flags require an
    external controller to kill/reconcile the workload and persist a role hold.
    """
    def __init__(self, *, session_id):
        if not isinstance(session_id,str) or not session_id.strip() or len(session_id)>256:
            raise RecordError('native session identity required')
        self.session_id=session_id;self.broken=False;self.stop=None;self.count=0
        self.terminal=None;self.state='unknown';self.text=None
        self.units=None;self.scope='unknown';self.estimate=None

    def _bad(self):
        self.broken=True;self.text=None;self.units=None;self.scope='unknown';self.estimate=None
        raise RecordError('native session output unavailable or invalid') from None

    def _tokens(self,value,names):
        if not isinstance(value,dict):self._bad()
        result=[value.get(name) for name in names]
        if any(type(item) is not int or not 0<=item<2**63 for item in result):self._bad()
        return result

    def _usage(self,event):
        models=event.get('modelUsage')
        if models is not None and not isinstance(models,dict):self._bad()
        if models:
            totals=[0,0,0,0]
            for name,value in models.items():
                if not isinstance(name,str) or not name:self._bad()
                counts=self._tokens(value,['inputTokens','outputTokens','cacheReadInputTokens','cacheCreationInputTokens'])
                totals=[left+right for left,right in zip(totals,counts)]
            self.scope='query_model_totals'
        elif 'usage' in event:
            usage=event['usage']
            if not isinstance(usage,dict):self._bad()
            counts=self._tokens(usage,['input_tokens','output_tokens'])
            self.units=dict(zip(['inputTokens','outputTokens'],counts))
            for native,name in [('cache_read_input_tokens','cachedInputTokens'),
                                ('cache_creation_input_tokens','cacheWriteInputTokens')]:
                if native in usage:self.units[name]=self._tokens(usage,[native])[0]
            if len(self.units)==4:
                total=sum(self.units.values())
                if total>=2**63:self._bad()
                self.units['totalTokens']=total;self.scope='main_loop_only'
            else:self.scope='main_loop_partial'
            totals=None
        else:totals=None
        if totals is not None:
            if sum(totals)>=2**63:self._bad()
            self.units=dict(zip(['inputTokens','outputTokens','cachedInputTokens','cacheWriteInputTokens'],totals))
            self.units['totalTokens']=sum(totals)
        if 'total_cost_usd' in event:
            amount=event['total_cost_usd']
            if type(amount) not in {int,float} or not math.isfinite(amount) or amount<0:self._bad()
            self.estimate={'amount':amount,'currency':'USD','source':'Claude native total_cost_usd (estimate)'}

    def accept(self,event):
        try:self._accept(event)
        except (RecordError,ValueError,TypeError,UnicodeError,RecursionError,OverflowError):self._bad()

    def _accept(self,event):
        if self.broken or not isinstance(event,dict):self._bad()
        self.count+=1
        if self.count>10000:self._bad()
        kind=event.get('type')
        if kind not in {'system','rate_limit_event','result'}:return
        identity=event.get('session_id')
        if not isinstance(identity,str):self._bad()
        if identity!=self.session_id:return
        parent=event.get('parent_tool_use_id')
        if parent is not None:
            if not isinstance(parent,str) or not parent:self._bad()
            return
        if kind=='system':
            if event.get('subtype')=='api_retry':
                status=event.get('error_status')
                if type(status) is not int or not 400<=status<=599:self._bad()
                if status in {401,403}:self.stop=self.stop or 'authentication_stop'
                elif status==429:self.stop=self.stop or 'rate_limit_stop'
            return
        if kind=='rate_limit_event':
            info=event.get('rate_limit_info')
            status=info.get('status') if isinstance(info,dict) else None
            if status not in {'allowed','allowed_warning','rejected'}:self._bad()
            if status=='rejected':self.stop=self.stop or 'allowance_stop'
            return
        try:canonical=json.dumps(event,allow_nan=False,sort_keys=True,separators=(',',':'))
        except (ValueError,TypeError,RecursionError):self._bad()
        if self.terminal is not None and self.terminal!=canonical:self._bad()
        subtype,error=event.get('subtype'),event.get('is_error')
        if type(error) is not bool:self._bad()
        if subtype=='success' and error is False:
            text=event.get('result')
            if not isinstance(text,str) or len(text.encode('utf-8'))>1_000_000:self._bad()
            self.text=text
            self.state='completed' if text.strip() and not event.get('local_command') else 'unknown'
        elif error is True and subtype in {'error_max_turns','error_during_execution',
                                           'error_max_budget_usd','error_max_structured_output_retries'}:
            self.state='failed'
            if subtype=='error_max_budget_usd':self.stop=self.stop or 'budget_stop'
        else:self._bad()
        self._usage(event);self.terminal=canonical

    def outcome(self):
        state='unknown' if self.broken else self.stop or self.state
        return {'provider':'anthropic','state':state,'text':self.text if state=='completed' else None,
                'pause_role':self.stop is not None,'stop_reason':self.stop,'usage_scope':self.scope,
                'usage':{'state':'measured' if self.units is not None else 'unknown',
                         'units':copy.deepcopy(self.units),'estimated_cost':copy.deepcopy(self.estimate),
                         'actual_charge':None}}


class NativeStream:
    """Bounded native stdout. Catch RecordError from feed AND finish, tear down
    and observe the workload, then settle outcome(); typed stop flags survive.
    """
    def __init__(self,provider,**identity):
        self.decoder=JsonLines()
        try:
            if provider=='codex':self.turn=CodexTurn(**identity)
            elif provider=='claude':self.turn=ClaudeTurn(**identity)
            else:raise RecordError('unsupported native output provider')
        except TypeError:
            raise RecordError('native output identity unavailable') from None

    def feed(self,chunk):
        try:
            for event in self.decoder.iter_feed(chunk):self.turn.accept(event)
        except RecordError:self.turn._bad()
        return self.outcome()

    def finish(self):
        try:
            for event in self.decoder.finish():self.turn.accept(event)
        except RecordError:self.turn._bad()
        return self.outcome()

    def outcome(self):return self.turn.outcome()
