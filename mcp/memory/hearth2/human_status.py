"""Allowlisted human read model. Poll timing is assessment, never delivery proof."""
from datetime import datetime
import json

from .control import ControlJournal
from .store import RecordError


def poll_expectations(raw, controllers):
    """Validate optional operator config. No implicit cadence or observer."""
    def pairs(items):
        result={}
        for key,value in items:
            if key in result:raise ValueError()
            result[key]=value
        return result
    try:
        if raw is None:return {}
        if type(raw) is not str or len(raw)>16384:raise ValueError()
        values=json.loads(raw,object_pairs_hook=pairs)
        if type(values) is not dict or set(values)-set(controllers):raise ValueError()
        for value in values.values():
            if type(value) is not dict or set(value)!={'cadence_seconds','grace_seconds'}:raise ValueError()
            if type(value['cadence_seconds']) is not int or not 1<=value['cadence_seconds']<=86400:raise ValueError()
            if type(value['grace_seconds']) is not int or not 0<=value['grace_seconds']<=3600:raise ValueError()
        return values
    except (ValueError,TypeError,RecursionError):
        raise RuntimeError('invalid Hearth 2 poll expectations') from None


def _time(value):
    if type(value) is not str:raise ValueError()
    stamp=datetime.fromisoformat(value)
    if stamp.tzinfo is None:raise ValueError()
    return stamp


def human_status(store, controllers, expectations, project_id=None):
    with store.transaction() as db:
        project=store.row(db,'projects',project_id) if project_id is not None else None
        control=ControlJournal(store).snapshot_in(db)
        tasks=[];notices=[]
        rows=db.execute('SELECT id,project_id,assignee,state,revision,data FROM tasks'
            +(' WHERE project_id=?' if project_id is not None else '')+' ORDER BY id',
            (project_id,) if project_id is not None else ())
        for row in rows:
            data=json.loads(row['data'])
            tasks.append(dict(id=row['id'],project_id=row['project_id'],assignee=row['assignee'],
                state=row['state'],revision=row['revision'],ask=data.get('ask','Task'),done_means=data.get('done_means','')))
        rows=db.execute('SELECT id,project_id,task_id,sender,recipient,kind,data FROM notices'
            +(' WHERE project_id=?' if project_id is not None else '')+' ORDER BY id',
            (project_id,) if project_id is not None else ())
        for row in rows:
            data=json.loads(row['data'])
            reference=data.get('reference')
            notices.append(dict(id=row['id'],task_id=row['task_id'],sender=row['sender'],recipient=row['recipient'],
                kind=row['kind'],record_state='recorded',delivery_state='unconfirmed',acknowledgement_state='unknown',
                recorded_at=None,evidence=[reference] if type(reference) is str else []))
        ticks={t['runner']:t for t in control['ticks']}
        polls=[]
        for name in sorted(controllers):
            tick=ticks.get(name);policy=expectations.get(name)
            state='unknown';reason='no_completed_poll';age=None
            if tick is not None:
                try:
                    age=(_time(control['observed_at'])-_time(tick['at'])).total_seconds()
                    if age<0:reason='poll_time_in_future';age=None
                    elif policy is None:reason='timing_not_configured'
                    else:
                        state='stale' if age>policy['cadence_seconds']+policy['grace_seconds'] else 'recent'
                        reason='poll_overdue' if state=='stale' else 'within_expected_window'
                except (TypeError,ValueError,OverflowError):reason='poll_time_unusable'
            polls.append(dict(controller=name,poll_state=state,reason=reason,age_seconds=age,
                last_completed_at=tick['at'] if tick else None,request_id=tick.get('request_id') if tick else None,
                sequence=tick['seq'] if tick else None,restore_epoch=control['restore_epoch'],
                cadence_seconds=policy['cadence_seconds'] if policy else None,
                grace_seconds=policy['grace_seconds'] if policy else None,
                evidence=tick.get('evidence',[]) if tick else []))
        failures=[dict(kind=f['kind'],target=f['target'],key=f['key'],state=f['state'],at=f['at'],
            sequence=f['seq'],actor=f['actor'],restore_epoch=f['restore_epoch'],evidence=f['evidence'],
            historical=f['restore_epoch']!=control['restore_epoch']) for f in control['failures']
            if f['kind']=='runner_stale' or project_id is None or any(t['id']==f['target'] for t in tasks)]
        return dict(observed_at=control['observed_at'],restore_epoch=control['restore_epoch'],
            project_id=project_id,project_title=project['title'] if project else None,
            tasks=tasks,notices=notices,controllers=polls,failures=failures)
