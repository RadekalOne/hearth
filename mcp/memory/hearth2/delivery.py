"""Authenticated protocol receipts, never comprehension or task transitions."""
from dataclasses import asdict,dataclass
import hashlib,json,re,uuid
from .control import ControlJournal
from .store import RecordError,require,safe_payload,text


@dataclass(frozen=True)
class NoticeSession:
    session_id: str
    principal_id: str
    recipient: str

    def __post_init__(self):
        for value in (self.session_id,self.principal_id,self.recipient):
            if type(value) is not str or re.fullmatch(r'[A-Za-z0-9_@][A-Za-z0-9_.:@-]{0,119}',value) is None or value=='anonymous':
                raise RecordError('invalid named-session identity')


def session_enrollments(raw,recipients,other_principals):
    def pairs(items):
        result={}
        for key,value in items:
            if key in result:raise ValueError()
            result[key]=value
        return result
    try:
        if raw is None:return {}
        if type(raw) is not str or len(raw)>32768:raise ValueError()
        values=json.loads(raw,object_pairs_hook=pairs)
        if type(values) is not dict or len(values)>128:raise ValueError()
        sessions={};subjects=set()
        for key,value in values.items():
            if type(value) is not dict or set(value)!={'principal_id','recipient'}:raise ValueError()
            target=NoticeSession(key,**value)
            if target.recipient not in recipients or target.principal_id in other_principals or target.principal_id in subjects:raise ValueError()
            sessions[key]=target;subjects.add(target.principal_id)
        return sessions
    except (ValueError,TypeError,RecursionError):
        raise RuntimeError('invalid Hearth 2 notice session enrollment') from None


def notice_body(notice):
    data=json.loads(notice['data'])
    return {**{key:notice[key] for key in ('id','project_id','task_id','sender','recipient','kind')},'reference':data['reference']}


def _digest(notice):
    return hashlib.sha256(safe_payload(notice_body(notice)).encode()).hexdigest()


def _events(db,notice_id,action):
    return db.execute('SELECT * FROM audit_events WHERE entity_id=? AND action=? ORDER BY seq',(notice_id,action)).fetchall()


def address_notice(store,db,actor,notice,target):
    if (type(target) is not NoticeSession or target.recipient!=notice['recipient'] or target.principal_id==actor.id
            or json.loads(notice['data']).get('recipient_session')!=target.session_id):
        raise RecordError('notice needs matching trusted named-session enrollment')
    epoch=db.execute('SELECT restore_epoch FROM record_meta WHERE id=1').fetchone()[0]
    store.audit(db,actor,notice['id'],'notice_addressed',{**asdict(target),
        'notice_digest':_digest(notice),'restore_epoch':epoch})


def _address(db,notice):
    rows=_events(db,notice['id'],'notice_addressed')
    if not rows:return None
    row=rows[0];data=json.loads(row['data'])
    try:
        target=NoticeSession(**{key:data[key] for key in ('session_id','principal_id','recipient')})
        if (row['actor']!=notice['sender'] or notice['recipient']!=target.recipient
                or data['notice_digest']!=_digest(notice)):return None
    except (KeyError,TypeError,RecordError):return None
    return {**data,'at':row['at'],'seq':row['seq']}


def _authorized(db,store,actor,target,notice_id):
    require(actor,{'session'})
    if type(target) is not NoticeSession or actor.id!=target.principal_id:
        raise RecordError('named session is not authorized')
    notice=store.row(db,'notices',notice_id);address=_address(db,notice)
    if address is None or any(address[key]!=value for key,value in asdict(target).items()):
        raise RecordError('notice is not addressed to this named session')
    return notice,address


def _epoch(db,expected):
    current=db.execute('SELECT restore_epoch FROM record_meta WHERE id=1').fetchone()[0]
    if current!=expected:raise RecordError('delivery restore epoch conflict')
    return current


def _matches(data,address):
    return all(data.get(key)==address[key] for key in ('session_id','principal_id','recipient','notice_digest'))


def _receipt(db,notice,address):
    for row in _events(db,notice['id'],'notice_receipt'):
        data=json.loads(row['data'])
        if row['actor']!=address['principal_id'] or not _matches(data,address):continue
        offer=db.execute("SELECT * FROM audit_events WHERE seq=? AND entity_id=? AND action='notice_offered'",
            (data.get('offered_sequence'),notice['id'])).fetchone()
        if offer is None:continue
        offered=json.loads(offer['data'])
        if (offer['actor']==row['actor'] and _matches(offered,address)
                and offered.get('delivery_id')==data.get('delivery_id')
                and offered.get('restore_epoch')==data.get('restore_epoch')):
            return ControlJournal.decode(row)
    return None


def receive_notice(store,actor,target,notice_id,*,request_id,expected_epoch):
    require(actor,{'session'});text(request_id,'delivery request id',128)
    with store.transaction() as db:
        epoch=_epoch(db,expected_epoch)
        notice,address=_authorized(db,store,actor,target,notice_id)
        offer=None
        for row in _events(db,notice_id,'notice_offered'):
            data=json.loads(row['data'])
            if (data.get('request_id')==request_id and data.get('restore_epoch')==epoch
                    and row['actor']==actor.id and _matches(data,address)):
                offer=ControlJournal.decode(row);break
        if offer is None:
            offer=ControlJournal(store).append(db,actor,notice_id,'notice_offered',dict(
                **asdict(target),notice_id=notice_id,notice_digest=address['notice_digest'],
                request_id=request_id,restore_epoch=epoch,delivery_id='delivery_'+uuid.uuid4().hex))
        return dict(notice=notice_body(notice),session_id=target.session_id,recipient=target.recipient,
            delivery_id=offer['delivery_id'],notice_digest=offer['notice_digest'],restore_epoch=epoch,
            offered_at=offer['at'],offered_sequence=offer['seq'])


def acknowledge_notice(store,actor,target,notice_id,*,delivery_id,notice_digest,expected_epoch):
    require(actor,{'session'})
    text(delivery_id,'delivery identity',128);text(notice_digest,'notice digest',64)
    with store.transaction() as db:
        epoch=_epoch(db,expected_epoch)
        notice,address=_authorized(db,store,actor,target,notice_id)
        if notice_digest!=address['notice_digest']:raise RecordError('notice content digest differs')
        offer=None
        for row in _events(db,notice_id,'notice_offered'):
            data=json.loads(row['data'])
            if (data.get('delivery_id')==delivery_id and data.get('restore_epoch')==epoch
                    and row['actor']==actor.id and _matches(data,address)):
                offer=row;break
        if offer is None:raise RecordError('matching current-period delivery offer required')
        existing=_receipt(db,notice,address)
        if existing is not None:return existing
        return ControlJournal(store).append(db,actor,notice_id,'notice_receipt',dict(
            **asdict(target),notice_id=notice_id,notice_digest=notice_digest,delivery_id=delivery_id,
            restore_epoch=epoch,offered_sequence=offer['seq']))


def delivery_status(db,notice,current_epoch):
    address=_address(db,notice);receipt=_receipt(db,notice,address) if address else None
    return dict(delivery_state='received' if receipt else 'unconfirmed',
        acknowledgement_state='receipt_recorded' if receipt else 'unknown',understanding_state='unknown',
        intended_session=address['session_id'] if address else None,recorded_at=address['at'] if address else None,
        receipt_actor=receipt['actor'] if receipt else None,acknowledged_at=receipt['at'] if receipt else None,
        acknowledgement_sequence=receipt['seq'] if receipt else None,delivery_id=receipt['delivery_id'] if receipt else None,
        notice_digest=address['notice_digest'] if address else None,
        receipt_restore_epoch=receipt['restore_epoch'] if receipt else None,
        receipt_historical=receipt['restore_epoch']!=current_epoch if receipt else False)


def session_inbox(store,actor,target):
    require(actor,{'session'})
    if type(target) is not NoticeSession or actor.id!=target.principal_id:raise RecordError('named session is not authorized')
    with store.transaction() as db:
        epoch=db.execute('SELECT restore_epoch FROM record_meta WHERE id=1').fetchone()[0]
        pending=[]
        for row in db.execute('SELECT * FROM notices ORDER BY id'):
            address=_address(db,row)
            if (address is None or any(address[key]!=value for key,value in asdict(target).items())
                    or _receipt(db,row,address) is not None):continue
            pending.append(dict(id=row['id'],task_id=row['task_id'],kind=row['kind'],recipient=row['recipient'],recipient_session=target.session_id))
            if len(pending)>50:break
        return dict(notices=pending[:50],more_pending=len(pending)>50,restore_epoch=epoch)
