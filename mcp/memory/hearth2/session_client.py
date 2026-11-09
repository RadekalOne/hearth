"""Explicit one-pass session delivery integration; no background task or model call."""
import asyncio,hashlib,json,re
from dataclasses import dataclass
from datetime import datetime
import httpx
from .delivery import NoticeSession
from .session_inbox import SessionInbox,SessionInboxError,canonical_origin,encoded


class DeliveryClientError(ValueError):pass


def _need(condition):
    if not condition:raise DeliveryClientError('invalid or mismatched session delivery response')


def _text(value,limit=240):return type(value) is str and 0<len(value)<=limit


def _stamp(value):
    try:return _text(value,80) and datetime.fromisoformat(value).tzinfo is not None
    except (ValueError,TypeError):return False


def _notice_id(value):return type(value) is str and re.fullmatch(r'notice_[a-f0-9]{32}',value) is not None


def _epoch(value):return type(value) is str and re.fullmatch(r'[A-Za-z0-9_-]{1,128}',value) is not None


@dataclass(frozen=True)
class PollResult:
    stored: int
    receipts_recorded: int
    more_pending: bool
    understanding_state: str = 'unknown'


class NamedSessionClient:
    def __init__(self,*,origin,target,token,inbox,transport=None,max_notices=10):
        try:self.origin=canonical_origin(origin)
        except SessionInboxError:raise DeliveryClientError('a fixed HTTPS origin is required') from None
        _need(type(target) is NoticeSession and type(inbox) is SessionInbox)
        _need(inbox.origin==self.origin and inbox.target==target)
        _need(_text(token,16384) and not any(c.isspace() for c in token))
        _need(type(max_notices) is int and 1<=max_notices<=50)
        self.target=target;self._token=token;self.inbox=inbox;self.transport=transport;self.max_notices=max_notices

    async def _json(self,http,method,path,data=None):
        try:
            http.cookies.clear()  # Never forward browser/session cookies beside this bearer.
            async with http.stream(method,self.origin+'/api/hearth2'+path,json=data,
                    headers={'Authorization':'Bearer '+self._token}) as response:
                if response.status_code!=200:raise DeliveryClientError('session delivery HTTP request refused')
                raw=bytearray()
                async for chunk in response.aiter_bytes():
                    raw.extend(chunk)
                    if len(raw)>262144:raise DeliveryClientError('session delivery response exceeds limit')
            def pairs(items):
                result={}
                for key,value in items:
                    if key in result:raise ValueError()
                    result[key]=value
                return result
            def constant(value):raise ValueError()
            result=json.loads(raw,object_pairs_hook=pairs,parse_constant=constant)
            _need(type(result) is dict);return result
        except DeliveryClientError:raise
        except Exception:raise DeliveryClientError('session delivery response unavailable or invalid; receipt may be unknown') from None

    def _inbox(self,value):
        _need(set(value)=={'notices','more_pending','restore_epoch'} and type(value['notices']) is list
            and len(value['notices'])<=50 and type(value['more_pending']) is bool and _epoch(value['restore_epoch']))
        seen=set()
        for row in value['notices']:
            _need(type(row) is dict and set(row)=={'id','task_id','kind','recipient','recipient_session'})
            _need(_notice_id(row['id']) and row['id'] not in seen and _text(row['task_id']) and _text(row['kind'])
                and row['recipient']==self.target.recipient and row['recipient_session']==self.target.session_id)
            seen.add(row['id'])
        return value

    def _offer(self,value,notice_id,epoch,summary):
        _need(set(value)=={'notice','session_id','recipient','delivery_id','notice_digest','restore_epoch','offered_at','offered_sequence'})
        body=value['notice']
        _need(type(body) is dict and set(body)=={'id','project_id','task_id','sender','recipient','kind','reference'})
        _need(body['id']==notice_id and all(_text(body[key],12000 if key=='reference' else 240) for key in body))
        _need(body['recipient']==self.target.recipient and value['session_id']==self.target.session_id
            and value['recipient']==self.target.recipient and value['restore_epoch']==epoch)
        _need(type(value['delivery_id']) is str and re.fullmatch(r'delivery_[a-f0-9]{32}',value['delivery_id']) is not None
            and type(value['offered_sequence']) is int and value['offered_sequence']>0 and _stamp(value['offered_at']))
        _need(value['notice_digest']==hashlib.sha256(encoded(body).encode()).hexdigest())
        if summary is not None:_need(all(body[key]==summary[key] for key in ('id','task_id','kind','recipient')))
        return value

    def _receipt(self,value,offer):
        keys={'session_id','principal_id','recipient','notice_id','notice_digest','delivery_id','restore_epoch','offered_sequence','seq','at','actor'}
        _need(keys<=set(value))
        _need(value['actor']==value['principal_id']==self.target.principal_id and value['session_id']==self.target.session_id
            and value['recipient']==self.target.recipient and value['notice_id']==offer['notice']['id']
            and value['notice_digest']==offer['notice_digest'])
        _need(type(value['delivery_id']) is str and re.fullmatch(r'delivery_[a-f0-9]{32}',value['delivery_id']) is not None
            and _epoch(value['restore_epoch']) and _stamp(value['at']) and type(value['offered_sequence']) is int
            and type(value['seq']) is int and 0<value['offered_sequence']<value['seq'])
        # Server may retain its first receipt from an earlier offer/restore period.
        return {key:value[key] for key in keys}

    async def poll_once(self):
        try:
            async with asyncio.timeout(30):
                async with httpx.AsyncClient(transport=self.transport,trust_env=False,follow_redirects=False,timeout=5) as http:
                    remote=self._inbox(await self._json(http,'GET','/session/notices'))
                    summaries={row['id']:row for row in remote['notices']}
                    ids=list(dict.fromkeys(self.inbox.pending()+list(summaries)))
                    stored=receipts=0
                    for notice_id in ids[:self.max_notices]:
                        _need(_notice_id(notice_id))
                        request_id='session-client-'+hashlib.sha256(encoded([self.origin,self.target.session_id,notice_id,remote['restore_epoch']]).encode()).hexdigest()
                        offer=self._offer(await self._json(http,'POST','/notices/'+notice_id+'/receive',dict(
                            request_id=request_id,expected_epoch=remote['restore_epoch'])),notice_id,remote['restore_epoch'],summaries.get(notice_id))
                        stored+=self.inbox.store(offer)
                        receipt=self._receipt(await self._json(http,'POST','/notices/'+notice_id+'/acknowledge',dict(
                            delivery_id=offer['delivery_id'],notice_digest=offer['notice_digest'],expected_epoch=remote['restore_epoch'])),offer)
                        receipts+=self.inbox.confirm(receipt)
                    return PollResult(stored,receipts,remote['more_pending'] or len(ids)>self.max_notices)
        except TimeoutError:raise DeliveryClientError('session delivery cycle timed out; receipt may be unknown') from None
