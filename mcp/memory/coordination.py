"""Default-off, transactional responsibility state. No chat inference or execution.

Transport authenticates actors and validates referenced work. Source event IDs are
caller-supplied provenance; this store does not verify Matrix messages or approval.
"""
import json
import hashlib
import sqlite3
from contextlib import closing, contextmanager
from datetime import datetime, timezone
from pathlib import Path


class CoordinationError(ValueError):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


class DeliveryConflict(CoordinationError):
    """Permanent external identity conflict; transient delivery errors still retry."""


def text(value, name, limit=240):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise CoordinationError(f'{name} must be nonempty text of at most {limit} characters')
    return value.strip()


def timestamp(value, name):
    value = text(value, name, 64)
    try:
        stamp = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if stamp.tzinfo is None:
            raise ValueError()
        return stamp.astimezone(timezone.utc).isoformat()
    except ValueError as err:
        raise CoordinationError(f'{name} must be a timezone-aware ISO timestamp') from err


def party(value):
    if not isinstance(value, dict):
        raise CoordinationError('party must be an object')
    kind = value.get('kind'); surface = value.get('required_surface')
    if not isinstance(kind,str) or not isinstance(surface,str) or kind not in {'agent', 'human'} or surface not in {'interactive', 'background', 'either'}:
        raise CoordinationError('unknown party kind or required surface')
    result = {'kind':kind, 'id':text(value.get('id'), 'party id'), 'required_surface':surface}
    for key in ['expected_deadline', 'acknowledged_delay_until']:
        result[key] = timestamp(value[key], key) if value.get(key) else None
    return result


def validate_parties(values):
    if not isinstance(values, list) or not 1 <= len(values) <= 20:
        raise CoordinationError('parties must have between 1 and 20 entries')
    result = [party(v) for v in values]
    if len({(v['kind'],v['id']) for v in result}) != len(result):
        raise CoordinationError('duplicate waiting party')
    return result


class CoordinationStore:
    def __init__(self, path, enabled=False):
        self.path = str(path)
        self.enabled = enabled
        self.initialized = False

    def initialize(self):
        """Explicit startup migration; disabled mode never opens or creates a file."""
        if not self.enabled:
            return
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path, timeout=15)) as db:
            db.executescript('''
                BEGIN IMMEDIATE;
                CREATE TABLE IF NOT EXISTS coordination_schema(version INTEGER PRIMARY KEY);
                INSERT OR IGNORE INTO coordination_schema VALUES(1);
                CREATE TABLE IF NOT EXISTS coordination_heads (
                    identity TEXT PRIMARY KEY, work_kind TEXT NOT NULL, work_id TEXT NOT NULL,
                    room_id TEXT NOT NULL, thread_id TEXT NOT NULL,
                    generation INTEGER NOT NULL, owner TEXT NOT NULL, owner_kind TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS coordination_parties (
                    identity TEXT NOT NULL REFERENCES coordination_heads(identity),
                    generation INTEGER NOT NULL, kind TEXT NOT NULL, party_id TEXT NOT NULL,
                    state TEXT NOT NULL CHECK(state IN ('pending','resolved','cancelled')),
                    data TEXT NOT NULL,
                    PRIMARY KEY(identity,generation,kind,party_id));
                CREATE TABLE IF NOT EXISTS coordination_events (
                    identity TEXT NOT NULL, generation INTEGER NOT NULL, source_event TEXT NOT NULL,
                    actor TEXT NOT NULL, party_id TEXT NOT NULL, data TEXT NOT NULL,
                    PRIMARY KEY(identity,generation,source_event,actor,party_id));
                CREATE TABLE IF NOT EXISTS coordination_continuations (
                    delivery_id TEXT PRIMARY KEY,identity TEXT NOT NULL,generation INTEGER NOT NULL,
                    poster TEXT NOT NULL,state TEXT NOT NULL,data TEXT NOT NULL,
                    UNIQUE(identity,generation,poster));
                CREATE TABLE IF NOT EXISTS coordination_outbox (
                    delivery_id TEXT PRIMARY KEY,identity TEXT NOT NULL,valid_generation INTEGER NOT NULL,
                    state TEXT NOT NULL,data TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS coordination_origins (
                    identity TEXT PRIMARY KEY,continuation_origin INTEGER NOT NULL);
                COMMIT;
            ''')
            versions = [r[0] for r in db.execute('SELECT version FROM coordination_schema')]
            if versions != [1]:
                raise CoordinationError('unsupported coordination schema', 409)
        self.initialized = True

    @staticmethod
    def identity(work_kind, work_id, room_id, thread_id):
        if not isinstance(work_kind,str) or work_kind not in {'task', 'relay', 'thread_plan'}:
            raise CoordinationError('unknown work kind')
        values = [work_kind,text(work_id,'work id'),text(room_id,'room id'),text(thread_id,'thread id')]
        if not values[2].startswith('!') or not values[3].startswith('$'):
            raise CoordinationError('Matrix room and thread IDs are required')
        return json.dumps(values, separators=(',', ':'))

    @contextmanager
    def transaction(self, write=False):
        if not self.enabled:
            raise CoordinationError('coordination feature is disabled', 409)
        if not self.initialized:
            raise CoordinationError('coordination store requires explicit initialization', 409)
        # mode=rw prevents accidental creation during a read if the store is removed.
        db = sqlite3.connect(Path(self.path).resolve().as_uri()+'?mode=rw', uri=True,
                             timeout=15, isolation_level=None)
        db.row_factory = sqlite3.Row
        try:
            db.execute('PRAGMA foreign_keys=ON')
            db.execute('BEGIN IMMEDIATE' if write else 'BEGIN')
            yield db
            db.execute('COMMIT')
        except Exception:
            if db.in_transaction:
                db.execute('ROLLBACK')
            raise
        finally:
            db.close()

    @staticmethod
    def generation(value):
        if type(value) is not int or value < 0:
            raise CoordinationError('expected_generation must be a nonnegative integer')
        return value

    @staticmethod
    def snapshot(db, identity, history=False):
        head = db.execute('SELECT * FROM coordination_heads WHERE identity=?', (identity,)).fetchone()
        result = {'generation':head['generation'] if head else 0, 'coordination_waiting_on':[],
                  'grants_authority':False}
        if head:
            rows = db.execute('SELECT * FROM coordination_parties WHERE identity=? ORDER BY generation,kind,party_id', (identity,)).fetchall()
            for row in rows:
                item = {**json.loads(row['data']), 'generation':row['generation'], 'state':row['state']}
                if row['generation'] == head['generation'] and row['state'] == 'pending':
                    result['coordination_waiting_on'].append(item)
            if history:
                result['history'] = [{**json.loads(r['data']), 'generation':r['generation'], 'state':r['state']} for r in rows]
        elif history:
            result['history'] = []
        return result

    def read(self, work_kind, work_id, room_id, thread_id, history=False):
        identity = self.identity(work_kind, work_id, room_id, thread_id)
        if not self.enabled:
            return {'generation':0, 'coordination_waiting_on':[], 'grants_authority':False}
        with self.transaction() as db:
            return self.snapshot(db, identity, history)

    @staticmethod
    def put_party(db, identity, generation, value, source_event, since):
        data = {**value, 'source_event':source_event, 'since':since}
        db.execute('INSERT INTO coordination_parties VALUES(?,?,?,?,?,?) ON CONFLICT(identity,generation,kind,party_id) DO UPDATE SET state=excluded.state,data=excluded.data',
                   (identity,generation,value['kind'],value['id'],'pending',json.dumps(data)))

    def set_wait(self, actor, human, *, work_kind, work_id, room_id, thread_id,
                 owner='', owner_kind='agent', expected_generation=0, parties=None, source_event='', since='',
                 allow_owner_transfer=False, continuation_origin=False, continuation=None):
        if not self.enabled:
            raise CoordinationError('coordination feature is disabled', 409)
        identity = self.identity(work_kind,work_id,room_id,thread_id)
        expected_generation = self.generation(expected_generation)
        actor = text(actor,'actor'); owner = text(owner,'owner')
        if owner_kind not in {'agent','human'}:
            raise CoordinationError('unknown owner kind')
        if not human and (actor != owner or owner_kind != 'agent'):
            raise CoordinationError('only the work owner or a human may set waiting state', 403)
        values = validate_parties(parties)
        source_event = text(source_event,'source event'); since = timestamp(since,'since')
        if not source_event.startswith('$'):
            raise CoordinationError('source event ID required')
        with self.transaction(write=True) as db:
            head = db.execute('SELECT * FROM coordination_heads WHERE identity=?', (identity,)).fetchone()
            if head and (head['owner'] != owner or head['owner_kind'] != owner_kind) and not (human and allow_owner_transfer):
                raise CoordinationError('waiting owner cannot be replaced', 409)
            current = head['generation'] if head else 0
            if current != expected_generation:
                raise CoordinationError('stale waiting generation', 409)
            generation = current + 1
            self.cancel_deliveries(db,identity)
            db.execute('INSERT OR REPLACE INTO coordination_origins VALUES(?,?)',(identity,int(bool(continuation_origin))))
            db.execute('UPDATE coordination_parties SET state=? WHERE identity=? AND state=?', ('cancelled',identity,'pending'))
            db.execute('INSERT INTO coordination_heads VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(identity) DO UPDATE SET generation=excluded.generation,owner=excluded.owner,owner_kind=excluded.owner_kind',
                       (identity,work_kind,work_id,room_id,thread_id,generation,owner,owner_kind))
            for value in values:
                self.put_party(db,identity,generation,value,source_event,since)
            db.execute('INSERT INTO coordination_events VALUES(?,?,?,?,?,?)',
                       (identity,generation,source_event,actor,'',json.dumps({'kind':'wait_set','since':since,
                           'owner':owner,'owner_kind':owner_kind,'previous_owner':head['owner'] if head else None})))
            if not continuation_origin and owner_kind=='agent':
                self.record_continuation(db,identity,generation,owner,source_event,values,continuation)
            return {**self.snapshot(db,identity), 'changed':True}

    def answer(self, actor, human, *, work_kind, work_id, room_id, thread_id,
               expected_generation, party_id, answer_kind, source_event, since, summary='', evidence=None,
               approval_party='', next_parties=None, expected_owner=None):
        if not self.enabled:
            raise CoordinationError('coordination feature is disabled', 409)
        identity = self.identity(work_kind,work_id,room_id,thread_id)
        expected_generation = self.generation(expected_generation)
        actor = text(actor,'actor')
        if not isinstance(party_id,str):
            raise CoordinationError('party id must be text')
        kinds = {'change_list','pass_needing_human','final_completion','cancel','handoff','approved'}
        ignored = {'ack','progress','reaction','unrelated'}
        if not isinstance(answer_kind,str) or answer_kind not in kinds | ignored:
            raise CoordinationError('unknown answer kind')
        with self.transaction(write=True) as db:
            head = db.execute('SELECT * FROM coordination_heads WHERE identity=?', (identity,)).fetchone()
            if not head:
                raise CoordinationError('stale waiting generation', 409)
            if expected_owner is not None and head['owner'] != expected_owner:
                raise CoordinationError('work was reassigned; a human must transfer coordination waiting state', 409)
            owner_cancel = answer_kind == 'cancel' and not party_id and (human or actor == head['owner'])
            row = db.execute('SELECT * FROM coordination_parties WHERE identity=? AND generation=? AND party_id=?',
                             (identity,expected_generation,party_id)).fetchone()
            if not owner_cancel and (not row or (row['kind'] == 'agent' and actor != party_id) or
                    (row['kind'] == 'human' and (not human or actor not in {party_id,'admin'}))):
                raise CoordinationError('answer must address an obligation owned by the authenticated party', 403)
            if answer_kind in ignored:
                if head['generation'] != expected_generation:
                    raise CoordinationError('stale waiting generation', 409)
                return {**self.snapshot(db,identity), 'changed':False}
            source_event = text(source_event,'source event'); since = timestamp(since,'since')
            if not source_event.startswith('$'):
                raise CoordinationError('source event ID required')
            text(summary,'summary',4000)
            if not isinstance(evidence,list) or not 1 <= len(evidence) <= 20:
                raise CoordinationError('a substantive answer requires evidence')
            refs = [text(ref,'evidence',240) for ref in evidence]
            previous = db.execute('SELECT data FROM coordination_events WHERE identity=? AND generation=? AND source_event=? AND actor=? AND party_id=?',
                                  (identity,expected_generation,source_event,actor,party_id)).fetchone()
            event = {'kind':answer_kind,'since':since,'summary':summary,'evidence':refs,
                     'approval_party':approval_party,'next_parties':next_parties}
            if previous:
                if json.loads(previous[0]) != event:
                    raise CoordinationError('source event already records a different answer', 409)
                return {**self.snapshot(db,identity), 'changed':False}
            if head['generation'] != expected_generation:
                raise CoordinationError('stale waiting generation', 409)
            if not owner_cancel and row['state'] != 'pending':
                raise CoordinationError('obligation is no longer pending', 409)
            additions = []
            if answer_kind == 'approved' and (not human or row['kind'] != 'human'):
                raise CoordinationError('only a human principal may record human approval', 403)
            if answer_kind == 'change_list':
                additions = [party({'kind':head['owner_kind'],'id':head['owner'],'required_surface':'interactive'})]
            elif answer_kind == 'pass_needing_human':
                additions = [party({'kind':'human','id':text(approval_party,'approval party'),'required_surface':'interactive'})]
            elif answer_kind == 'handoff':
                additions = validate_parties(next_parties)
            if owner_cancel:
                db.execute('UPDATE coordination_parties SET state=? WHERE identity=? AND generation=? AND state=?',
                           ('cancelled',identity,expected_generation,'pending'))
            else:
                db.execute('UPDATE coordination_parties SET state=? WHERE identity=? AND generation=? AND kind=? AND party_id=?',
                           ('cancelled' if answer_kind == 'cancel' else 'resolved',identity,expected_generation,row['kind'],party_id))
            if additions:
                # A new responsibility cycle fences old replies, even if the same
                # party is asked again. Carry other parties with their original age.
                remaining = db.execute('SELECT data FROM coordination_parties WHERE identity=? AND generation=? AND state=?',
                                       (identity,expected_generation,'pending')).fetchall()
                generation = expected_generation + 1
                db.execute('UPDATE coordination_heads SET generation=? WHERE identity=?', (generation,identity))
                db.execute('UPDATE coordination_parties SET state=? WHERE identity=? AND generation=? AND state=?',
                           ('cancelled',identity,expected_generation,'pending'))
                carried = set()
                for other in remaining:
                    value = json.loads(other['data'])
                    carried.add((value['kind'],value['id']))
                    self.put_party(db,identity,generation,value,value['source_event'],value['since'])
                for value in additions:
                    if (value['kind'],value['id']) not in carried:
                        self.put_party(db,identity,generation,value,source_event,since)
            db.execute('INSERT INTO coordination_events VALUES(?,?,?,?,?,?)',
                       (identity,expected_generation,source_event,actor,party_id,json.dumps(event)))
            if answer_kind=='cancel':
                if owner_cancel:self.cancel_deliveries(db,identity)
                elif not self.snapshot(db,identity)['coordination_waiting_on']:self.cancel_deliveries(db,identity)
            else:
                current=self.snapshot(db,identity)
                self.promote(db,identity,expected_generation,source_event,current['generation'])
                origin=db.execute('SELECT continuation_origin FROM coordination_origins WHERE identity=?',(identity,)).fetchone()
                if additions and head['owner_kind']=='agent' and not (origin and origin[0]):
                    self.record_continuation(db,identity,current['generation'],head['owner'],source_event,
                                             current['coordination_waiting_on'])
            return {**self.snapshot(db,identity), 'changed':True}

    @staticmethod
    def cancel_deliveries(db,identity):
        db.execute("UPDATE coordination_continuations SET state='cancelled' WHERE identity=? AND state IN ('waiting','ready','delivered')",(identity,))
        db.execute("UPDATE coordination_outbox SET state='cancelled' WHERE identity=? AND state IN ('ready','delivered')",(identity,))

    @staticmethod
    def record_continuation(db,identity,generation,poster,last_read,parties,continuation=None):
        external=[p for p in parties if p['id']!=poster]
        if not external:return
        supplied=continuation or {}
        if not isinstance(supplied,dict) or set(supplied)-{'last_read_event','next_action','deadline'}:
            raise CoordinationError('invalid continuation fields')
        last_read=text(supplied.get('last_read_event',last_read),'last read event')
        if not last_read.startswith('$'):raise CoordinationError('last-read Matrix event required')
        next_action=text(supplied.get('next_action',f'Read replies after {last_read}; inspect the substantive answer and respond in the source thread.'),'next action',4000)
        deadlines=[p['expected_deadline'] for p in external if p.get('expected_deadline')]
        deadline=timestamp(supplied['deadline'],'deadline') if supplied.get('deadline') else min(deadlines) if deadlines else None
        delivery='relay_continuation_'+hashlib.sha256(f'{identity}|{generation}|{poster}'.encode()).hexdigest()[:32]
        work_kind,work_id,room_id,thread_id=json.loads(identity)
        data={'delivery_id':delivery,'work_kind':work_kind,'work_id':work_id,'room_id':room_id,'thread_id':thread_id,
              'generation':generation,'target_agent':poster,'last_read_event':last_read,'next_action':next_action,
              'deadline':deadline,'required_surface':'interactive','origin':'continuation','grants_authority':False}
        db.execute('INSERT OR IGNORE INTO coordination_continuations VALUES(?,?,?,?,?,?)',
                   (delivery,identity,generation,poster,'waiting',json.dumps(data)))

    @staticmethod
    def promote(db,identity,generation,trigger,valid_generation):
        rows=db.execute("SELECT * FROM coordination_continuations WHERE identity=? AND generation=? AND state IN ('waiting','ready','delivered')",(identity,generation)).fetchall()
        for row in rows:
            data={**json.loads(row['data']),'trigger_event':trigger,'current_generation':valid_generation}
            db.execute("UPDATE coordination_continuations SET state='ready' WHERE delivery_id=?",(row['delivery_id'],))
            db.execute("INSERT INTO coordination_outbox VALUES(?,?,?,?,?) ON CONFLICT(delivery_id) DO UPDATE SET valid_generation=excluded.valid_generation,data=excluded.data,state='ready'",
                       (row['delivery_id'],identity,valid_generation,'ready',json.dumps(data)))

    def promote_due(self,now):
        if not self.enabled:return
        now=timestamp(now,'now')
        with self.transaction(write=True) as db:
            rows=db.execute("SELECT c.* FROM coordination_continuations c JOIN coordination_heads h ON c.identity=h.identity AND c.generation=h.generation WHERE c.state='waiting'").fetchall()
            for row in rows:
                deadline=json.loads(row['data']).get('deadline')
                if deadline and deadline<=now:self.promote(db,row['identity'],row['generation'],'deadline',row['generation'])

    def deliveries(self,agent):
        if not self.enabled:return []
        with self.transaction() as db:
            rows=db.execute("SELECT o.data FROM coordination_outbox o JOIN coordination_heads h ON o.identity=h.identity AND o.valid_generation=h.generation WHERE o.state='ready' ORDER BY o.delivery_id").fetchall()
            return [d for r in rows if (d:=json.loads(r['data']))['target_agent']==agent]

    def failed_deliveries(self,limit=100):
        if not self.enabled:return []
        with self.transaction() as db:
            rows=db.execute("SELECT data FROM coordination_outbox WHERE state='failed' ORDER BY delivery_id LIMIT ?",
                            (max(1,min(limit,500)),)).fetchall()
            return [json.loads(r['data']) for r in rows]

    def mark_delivered(self,delivery_id):
        with self.transaction(write=True) as db:
            db.execute("UPDATE coordination_outbox SET state='delivered' WHERE delivery_id=? AND state='ready'",(delivery_id,))
            db.execute("UPDATE coordination_continuations SET state='delivered' WHERE delivery_id=? AND state='ready'",(delivery_id,))

    def delivery_valid(self,delivery_id):
        if not self.enabled:return False
        with self.transaction() as db:
            return bool(db.execute("SELECT 1 FROM coordination_outbox o JOIN coordination_heads h ON o.identity=h.identity AND o.valid_generation=h.generation WHERE o.delivery_id=? AND o.state IN ('ready','delivered')",(delivery_id,)).fetchone())

    def guard_delivery(self,delivery_id,action):
        with self.transaction(write=True) as db:
            if not db.execute("SELECT 1 FROM coordination_outbox o JOIN coordination_heads h ON o.identity=h.identity AND o.valid_generation=h.generation WHERE o.delivery_id=? AND o.state IN ('ready','delivered')",(delivery_id,)).fetchone():
                raise CoordinationError('continuation was cancelled or superseded',409)
            return action()

    def drain(self,agent,deliver,now):
        """SQLite lock fences cancellation; deterministic external delivery survives a crash."""
        if not self.enabled:return
        self.promote_due(now)
        with self.transaction(write=True) as db:
            rows=db.execute("SELECT o.* FROM coordination_outbox o JOIN coordination_heads h ON o.identity=h.identity AND o.valid_generation=h.generation WHERE o.state='ready' ORDER BY o.delivery_id").fetchall()
            for row in rows:
                data=json.loads(row['data'])
                if data['target_agent']!=agent:continue
                try:
                    deliver(data)
                except DeliveryConflict:
                    # Only permanent identity conflicts are quarantined. A crash
                    # after an external write must still roll back and retry.
                    data['failure_reason']='continuation delivery identity conflict'
                    db.execute("UPDATE coordination_outbox SET state='failed',data=? WHERE delivery_id=?",
                               (json.dumps(data),row['delivery_id']))
                    db.execute("UPDATE coordination_continuations SET state='failed' WHERE delivery_id=?",
                               (row['delivery_id'],))
                    continue
                db.execute("UPDATE coordination_outbox SET state='delivered' WHERE delivery_id=?",(row['delivery_id'],))
                db.execute("UPDATE coordination_continuations SET state='delivered' WHERE delivery_id=?",(row['delivery_id'],))

    def for_work(self, work_kind, work_id):
        """Current pending obligations across threads; no generation flattening."""
        if not self.enabled:
            return []
        with self.transaction() as db:
            heads = db.execute('SELECT * FROM coordination_heads WHERE work_kind=? AND work_id=? ORDER BY room_id,thread_id', (work_kind,work_id)).fetchall()
            return [{**p, 'room_id':head['room_id'], 'thread_id':head['thread_id']}
                    for head in heads for p in self.snapshot(db,head['identity'])['coordination_waiting_on']]

    def for_party(self, kind, party_id):
        if not self.enabled:
            return []
        with self.transaction() as db:
            rows = db.execute('SELECT p.*, h.work_kind,h.work_id,h.room_id,h.thread_id FROM coordination_parties p JOIN coordination_heads h ON h.identity=p.identity AND h.generation=p.generation WHERE p.kind=? AND p.party_id=? AND p.state=? ORDER BY h.work_kind,h.work_id,h.room_id,h.thread_id',
                              (kind,party_id,'pending')).fetchall()
            return [{**json.loads(r['data']), 'generation':r['generation'], 'state':r['state'],
                     'work_kind':r['work_kind'],'work_id':r['work_id'],'room_id':r['room_id'],'thread_id':r['thread_id']} for r in rows]
