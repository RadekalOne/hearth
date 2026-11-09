"""Allowlisted human read model. Poll timing is assessment, never delivery proof."""
import json

from .control import ControlJournal
from .store import RecordError
from .poll_timing import poll_expectations, _time, assess_poll


def human_status(store, controllers, expectations, project_id=None):
    with store.transaction() as db:
        project=store.row(db,'projects',project_id) if project_id is not None else None
        control=ControlJournal(store).snapshot_in(db)
        tasks=[];notices=[]
        claims={r['task_id']:r for r in db.execute("SELECT task_id,generation,restore_epoch,lease_until FROM claims WHERE state='active'")}
        rows=db.execute('SELECT id,project_id,assignee,state,revision,generation,data FROM tasks'
            +(' WHERE project_id=?' if project_id is not None else '')+' ORDER BY id',
            (project_id,) if project_id is not None else ())
        for row in rows:
            data=json.loads(row['data'])
            claim=claims.get(row['id']);lease_until=None;lease_state='unknown'
            if (claim is not None and row['state']=='running' and claim['generation']==row['generation']
                    and claim['restore_epoch']==control['restore_epoch']):
                lease_until=claim['lease_until']
                try:lease_state='expired' if _time(lease_until)<=_time(control['observed_at']) else 'current'
                except (TypeError,ValueError,OverflowError):pass
            tasks.append(dict(id=row['id'],project_id=row['project_id'],assignee=row['assignee'],
                state=row['state'],revision=row['revision'],ask=data.get('ask','Task'),done_means=data.get('done_means',''),
                claim_lease_until=lease_until,lease_state=lease_state,worker_liveness='unverified'))
        rows=db.execute('SELECT id,project_id,task_id,sender,recipient,kind,data FROM notices'
            +(' WHERE project_id=?' if project_id is not None else '')+' ORDER BY id',
            (project_id,) if project_id is not None else ())
        for row in rows:
            data=json.loads(row['data'])
            reference=data.get('reference')
            notices.append(dict(id=row['id'],task_id=row['task_id'],sender=row['sender'],recipient=row['recipient'],
                kind=row['kind'],record_state='recorded',delivery_state='unconfirmed',acknowledgement_state='unknown',
                recorded_at=None,supplied_references=[reference] if type(reference) is str else [],
                reference_provenance='reporter_supplied_unverified'))
        ticks={t['runner']:t for t in control['ticks']}
        polls=[]
        for name in sorted(controllers):
            tick=ticks.get(name);policy=expectations.get(name)
            polls.append({**assess_poll(name,tick,policy,control['observed_at'],control['restore_epoch']),
                'supplied_references':tick.get('evidence',[]) if tick else [],
                'reference_provenance':'reporter_supplied_unverified'})
        failures=[dict(kind=f['kind'],target=f['target'],key=f['key'],state=f['state'],at=f['at'],
            sequence=f['seq'],actor=f['actor'],restore_epoch=f['restore_epoch'],supplied_references=f['evidence'],
            reference_provenance='reporter_supplied_unverified',self_reported=f['actor']==f['target'],
            historical=f['restore_epoch']!=control['restore_epoch']) for f in control['failures']
            if f['kind']=='runner_stale' or project_id is None or any(t['id']==f['target'] for t in tasks)]
        observer_fields=('seq','at','actor','restore_epoch','request_id','assessed_at')
        assessment_fields=('controller','poll_state','reason','age_seconds','last_completed_at','request_id',
            'sequence','restore_epoch','cadence_seconds','grace_seconds','incident_state',
            'stale_tick_sequence','recovery_tick_sequence')
        observers=[{**{key:event[key] for key in observer_fields},
            'observations':[{key:row[key] for key in assessment_fields} for row in event['observations']]}
            for event in control['observations']]
        return dict(observed_at=control['observed_at'],restore_epoch=control['restore_epoch'],
            project_id=project_id,project_title=project['title'] if project else None,
            tasks=tasks,notices=notices,controllers=polls,failures=failures,observers=observers)
