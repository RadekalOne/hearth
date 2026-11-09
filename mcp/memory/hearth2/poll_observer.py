"""Explicit one-pass observer; scheduling and independent host availability are external."""
import json
from .control import ControlJournal
from .poll_timing import assess_poll, poll_expectations
from .store import RecordError, require, text


def observe_polls(store, actor, *, controllers, expectations, request_id, expected_seq, expected_epoch):
    require(actor, {'observer'})
    if type(controllers) not in (set,frozenset) or len(controllers)>128 or actor.id in controllers:
        raise RecordError('observer requires independent identity and at most 128 controllers')
    for name in controllers:text(name,'controller identity',240)
    text(request_id,'observer request id',128)
    ControlJournal.validate(expected_seq,['server-journal-poll-assessment'])
    try:policy=poll_expectations(json.dumps(expectations,allow_nan=False),controllers)
    except (RuntimeError,ValueError,TypeError,RecursionError):
        raise RecordError('invalid observer poll expectations') from None
    journal=ControlJournal(store)
    with store.transaction() as db:
        epoch=db.execute('SELECT restore_epoch FROM record_meta WHERE id=1').fetchone()[0]
        if expected_epoch!=epoch:raise RecordError('observer restore epoch conflict')
        entity=journal.entity(['poll_observation',actor.id,epoch])
        rows=db.execute("SELECT * FROM audit_events WHERE entity_id=? AND action='poll_observation' ORDER BY seq DESC",(entity,)).fetchall()
        prior={}
        for row in rows:
            value=journal.decode(row)
            if value['request_id']==request_id:
                if (value['expected_seq']!=expected_seq or value['expectations']!=policy
                        or value['controllers']!=sorted(controllers)):
                    raise RecordError('observer request identity conflict')
                return value
            for assessment in value['observations']:
                prior.setdefault(assessment['controller'],assessment)
        if expected_seq!=(rows[0]['seq'] if rows else 0):raise RecordError('observer sequence conflict')
        snapshot=journal.snapshot_in(db)
        ticks={tick['runner']:tick for tick in snapshot['ticks']}
        observations=[]
        for name in sorted(controllers):
            result=assess_poll(name,ticks.get(name),policy.get(name),snapshot['observed_at'],epoch)
            previous=prior.get(name,{})
            state=previous.get('incident_state','none')
            stale_seq=previous.get('stale_tick_sequence')
            recovery_seq=previous.get('recovery_tick_sequence')
            if result['poll_state']=='stale':
                state='open';stale_seq=result['sequence'];recovery_seq=None
            elif (result['poll_state']=='recent' and state=='open'
                    and result['sequence'] is not None and stale_seq is not None and result['sequence']>stale_seq):
                state='recovered';recovery_seq=result['sequence']
            observations.append({**result,'incident_state':state,'stale_tick_sequence':stale_seq,
                'recovery_tick_sequence':recovery_seq})
        return journal.append(db,actor,entity,'poll_observation',dict(restore_epoch=epoch,
            request_id=request_id,expected_seq=expected_seq,controllers=sorted(controllers),expectations=policy,
            assessed_at=snapshot['observed_at'],observations=observations))
