"""Typed operational events over the existing immutable record journal.

Ticks prove only a controller poll completed. Failures are separate from model
attempt incidents and never change task/run state or count as termination proof.
"""
import hashlib
import json
from .store import RecordError, require, safe_payload, text


class ControlJournal:
    def __init__(self, store):
        self.store = store

    @staticmethod
    def decode(row):
        return {**json.loads(row['data']), 'seq':row['seq'], 'at':row['at'], 'actor':row['actor']}

    @staticmethod
    def entity(parts):
        return 'control_' + hashlib.sha256(safe_payload(parts).encode()).hexdigest()

    def append(self, db, actor, entity, action, data):
        self.store.audit(db, actor, entity, action, data)
        return self.decode(db.execute('SELECT * FROM audit_events WHERE seq=last_insert_rowid()').fetchone())

    @staticmethod
    def validate(expected_seq, evidence):
        if type(expected_seq) is not int or expected_seq < 0:
            raise RecordError('expected sequence must be a nonnegative integer')
        if not isinstance(evidence, list) or not evidence or any(not isinstance(v, str) or not v.strip() for v in evidence):
            raise RecordError('operational events require evidence references')
        safe_payload(evidence)

    def tick(self, actor, *, request_id, expected_seq, expected_epoch, evidence):
        require(actor, {'controller'})
        self.validate(expected_seq, evidence)
        text(request_id, 'poll request id', 128)
        with self.store.transaction() as db:
            epoch = db.execute('SELECT restore_epoch FROM record_meta WHERE id=1').fetchone()[0]
            if expected_epoch != epoch:
                raise RecordError('runner tick restore epoch conflict')
            entity = self.entity(['runner_tick', actor.id, epoch])
            rows = db.execute("SELECT * FROM audit_events WHERE entity_id=? AND action='runner_tick' ORDER BY seq DESC", (entity,)).fetchall()
            data = dict(runner=actor.id, restore_epoch=epoch, request_id=request_id,
                        expected_seq=expected_seq, evidence=evidence)
            # Search older cycles too: a retried old request must not become a new tick.
            for row in rows:
                if json.loads(row['data'])['request_id'] == request_id:
                    if row['actor'] != actor.id or json.loads(row['data']) != data:
                        raise RecordError('poll request identity conflict')
                    return self.decode(row)
            if expected_seq != (rows[0]['seq'] if rows else 0):
                raise RecordError('runner tick sequence conflict')
            return self.append(db, actor, entity, 'runner_tick', data)

    def failure(self, actor, *, kind, target, key, expected_seq, expected_epoch, state, evidence):
        require(actor, {'controller'})
        self.validate(expected_seq, evidence)
        if kind not in {'missed_start', 'runner_stale', 'dispatch_blocked'} or state not in {'open', 'recovered'}:
            raise RecordError('unknown control failure kind or state')
        text(target, 'failure target', 240)
        text(key, 'failure key', 128)
        with self.store.transaction() as db:
            epoch = db.execute('SELECT restore_epoch FROM record_meta WHERE id=1').fetchone()[0]
            # Restored journals retain sequences; sequence equality alone cannot
            # distinguish a new observation from an old in-flight write.
            if expected_epoch != epoch:
                raise RecordError('control failure restore epoch conflict')
            entity = self.entity(['control_failure', kind, target, key])
            row = db.execute("SELECT * FROM audit_events WHERE entity_id=? AND action='control_failure' ORDER BY seq DESC LIMIT 1", (entity,)).fetchone()
            data = dict(kind=kind, target=target, key=key, state=state, evidence=evidence,
                        expected_seq=expected_seq, restore_epoch=epoch)
            if row is not None and row['actor'] == actor.id and json.loads(row['data']) == data:
                return self.decode(row)
            if expected_seq != (row['seq'] if row else 0) or row is None and state != 'open':
                raise RecordError('failure sequence conflict or recovery without a failure')
            if kind != 'runner_stale':
                task = self.store.row(db, 'tasks', target)
                if state == 'open' and (task['state'] != 'ready' or kind == 'missed_start' and task['attempts'] != 0):
                    raise RecordError('pre-launch failure requires eligible queued work')
                if state == 'open':
                    self.store._eligible(db, task)
            return self.append(db, actor, entity, 'control_failure', data)

    def snapshot(self):
        with self.store.transaction() as db:
            epoch = db.execute('SELECT restore_epoch FROM record_meta WHERE id=1').fetchone()[0]
            ticks, failures, seen = [], [], set()
            for row in db.execute("SELECT * FROM audit_events WHERE action IN ('runner_tick','control_failure') ORDER BY seq DESC"):
                if row['entity_id'] in seen:
                    continue
                seen.add(row['entity_id'])
                data = self.decode(row)
                if row['action'] == 'control_failure':
                    failures.append(data)
                elif data['restore_epoch'] == epoch:
                    ticks.append(data)
            return dict(restore_epoch=epoch, observed_at=self.store.now().isoformat(), ticks=ticks, failures=failures)
