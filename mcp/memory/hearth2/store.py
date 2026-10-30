"""Transactional work-record authority. Transport supplies trusted principals.

Workers cannot turn payload fields into authority. Controller operations are
not exposed to workers; future transport must enforce that distinction.
"""
import json
import hashlib
import re
import sqlite3
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from .schema import Schema, TABLES, open_existing


class RecordError(ValueError):
    pass


@dataclass(frozen=True)
class Principal:
    id: str
    kind: str


def text(value, name, limit=12000):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise RecordError(f'invalid {name}')
    return value.strip()


def timestamp(value):
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if parsed.tzinfo is None:
            raise ValueError()
        return parsed.astimezone(timezone.utc)
    except (ValueError, TypeError, AttributeError) as error:
        raise RecordError('timestamp must include timezone') from error


def safe_payload(value):
    """Reject structured credential fields and recognizable secrets, without echo."""
    forbidden = {'password', 'credential', 'private_key', 'api_key', 'access_token',
                 'authorization', 'cookie', 'claim_secret', 'broker_grant'}
    def inspect(item):
        if isinstance(item, dict):
            for key, val in item.items():
                if not isinstance(key, str) or key.lower().replace('-', '_') in forbidden:
                    raise RecordError('credential-bearing field is not allowed')
                inspect(val)
        elif isinstance(item, list):
            for val in item:
                inspect(val)
        elif isinstance(item, str) and (re.search(r'\bsk-[A-Za-z0-9_-]{20,}', item)
                                      or '-----BEGIN ' in item and 'PRIVATE KEY-----' in item):
            raise RecordError('credential-like content is not allowed')
    inspect(value)
    try:
        encoded = json.dumps(value, allow_nan=False, separators=(',', ':'), sort_keys=True)
    except (TypeError, ValueError) as error:
        raise RecordError('payload must be finite JSON') from error
    if len(encoded.encode()) > 1_000_000:
        raise RecordError('payload too large')
    return encoded


def require(actor, kinds):
    if not isinstance(actor, Principal) or actor.kind not in kinds or not actor.id:
        raise RecordError('principal is not authorized for this operation')


def identifier(prefix):
    return prefix + '_' + uuid.uuid4().hex


def action_manifest(payload):
    actions = payload.get('actions', {})
    if not isinstance(actions, dict) or len(actions) > 1000:
        raise RecordError('actions must be an explicit bounded manifest')
    fields = {'recipient', 'ask', 'done_means', 'inputs', 'return', 'requires'}
    for key, action in actions.items():
        text(key, 'action id', 120)
        if not isinstance(action, dict) or set(action) != fields:
            raise RecordError('each approved action requires its complete handoff and dependencies')
        for field in fields - {'inputs', 'requires'}:
            text(action[field], field)
        if not isinstance(action['inputs'], list) or not action['inputs'] or any(not isinstance(v, str) or not v.strip() for v in action['inputs']):
            raise RecordError('action inputs require source references')
        if not isinstance(action['requires'], dict) or any(dep not in actions or gate not in {'output', 'reviewed', 'accepted'} for dep, gate in action['requires'].items()):
            raise RecordError('invalid action dependency gate')
    visiting, visited = set(), set()
    def visit(key):
        if key in visiting:
            raise RecordError('cyclic action dependencies')
        if key in visited:
            return
        visiting.add(key)
        for parent in actions[key]['requires']:
            visit(parent)
        visiting.remove(key)
        visited.add(key)
    for key in actions:
        visit(key)
    return actions


def manifest_hash(plan):
    return hashlib.sha256(safe_payload(action_manifest(json.loads(plan['data']))).encode()).hexdigest()


class Store:
    def __init__(self, path, *, clock=None, lease_seconds=900, deadline_seconds=7200):
        self.path = path
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        for value in (lease_seconds, deadline_seconds):
            if type(value) is not int or not 1 <= value <= 7200:
                raise RecordError('timing must be integer seconds between 1 and 7200')
        self.lease_seconds, self.deadline_seconds = lease_seconds, deadline_seconds

    def now(self):
        value = self.clock()
        if not isinstance(value, datetime) or value.tzinfo is None:
            raise RecordError('clock must return an aware datetime')
        return value.astimezone(timezone.utc)

    def runner_tick(self, actor, **payload):
        from .control import ControlJournal
        return ControlJournal(self).tick(actor, **payload)

    def control_failure(self, actor, **payload):
        from .control import ControlJournal
        return ControlJournal(self).failure(actor, **payload)

    def control_snapshot(self):
        from .control import ControlJournal
        return ControlJournal(self).snapshot()

    @contextmanager
    def transaction(self):
        db = open_existing(self.path)
        try:
            db.execute('BEGIN IMMEDIATE')
            Schema.validate(db)
            db.row_factory = sqlite3.Row
            yield db
            db.execute('COMMIT')
        except BaseException:
            if db.in_transaction:
                db.execute('ROLLBACK')
            raise
        finally:
            db.close()

    @staticmethod
    def row(db, table, key, *, column='id'):
        if table not in TABLES or column not in {'id', 'agent'}:
            raise RecordError('unknown record type')
        r = db.execute(f'SELECT * FROM {table} WHERE {column}=?', (key,)).fetchone()
        if r is None:
            raise RecordError('record not found')
        return dict(r)

    def audit(self, db, actor, entity, action, data=None):
        db.execute('INSERT INTO audit_events(actor,entity_id,action,at,data) VALUES(?,?,?,?,?)',
                   (actor.id, entity, action, self.now().isoformat(), safe_payload(data or {})))

    def create_project(self, actor, payload):
        require(actor, {'human', 'controller'})
        data = safe_payload(payload)
        key = identifier('project')
        with self.transaction() as db:
            db.execute('INSERT INTO projects VALUES(?,?,?,?,?)', (key, text(payload.get('title'), 'title', 200), 'idea', 1, data))
            self.audit(db, actor, key, 'project_created')
            return self.row(db, 'projects', key)

    def create_plan(self, actor, project_id, payload):
        require(actor, {'human', 'controller'})
        text(payload.get('content_ref'), 'content_ref')
        action_manifest(payload)
        data, key = safe_payload(payload), identifier('plan')
        with self.transaction() as db:
            self.row(db, 'projects', project_id)
            revision = db.execute('SELECT COALESCE(MAX(revision),0)+1 FROM plans WHERE project_id=?', (project_id,)).fetchone()[0]
            db.execute('INSERT INTO plans VALUES(?,?,?,?,?)', (key, project_id, revision, 'draft', data))
            self.audit(db, actor, key, 'plan_created', {'revision': revision})
            return self.row(db, 'plans', key)

    def create_task(self, actor, payload):
        require(actor, {'human', 'controller'})
        for name in ['recipient', 'ask', 'done_means', 'return']:
            text(payload.get(name), name)
        inputs = payload.get('inputs')
        if not isinstance(inputs, list) or not inputs or any(not isinstance(v, str) or not v.strip() for v in inputs):
            raise RecordError('inputs must identify at least one source')
        deps = payload.get('dependencies', [])
        if not isinstance(deps, list) or any(not isinstance(v, str) for v in deps) or len(set(deps)) != len(deps):
            raise RecordError('invalid dependencies')
        key, data = identifier('task'), safe_payload(payload)
        with self.transaction() as db:
            plan = self.row(db, 'plans', payload.get('plan_id'))
            if plan['project_id'] != payload.get('project_id'):
                raise RecordError('plan belongs to another project')
            action_id = text(payload.get('action_id'), 'action id', 120)
            actions = action_manifest(json.loads(plan['data']))
            action = actions.get(action_id)
            if action is None or any(payload.get(field) != action[field] for field in ['recipient', 'ask', 'done_means', 'inputs', 'return']):
                raise RecordError('task differs from the plan action manifest')
            if db.execute('SELECT 1 FROM tasks WHERE plan_id=? AND action_id=?', (plan['id'], action_id)).fetchone():
                raise RecordError('plan action already has a task')
            parents = [self.row(db, 'tasks', dep) for dep in deps]
            if any(parent['project_id'] != plan['project_id'] or parent['plan_id'] != plan['id'] for parent in parents):
                raise RecordError('dependency belongs to another project or plan')
            if {parent['action_id'] for parent in parents} != set(action['requires']):
                raise RecordError('task dependencies differ from approved action gates')
            db.execute('INSERT INTO tasks VALUES(?,?,?,?,?,?,1,0,0,?)',
                       (key, plan['project_id'], plan['id'], action_id, payload['recipient'], 'ready', data))
            db.executemany('INSERT INTO dependencies VALUES(?,?,?)',
                           [(key, parent['id'], action['requires'][parent['action_id']]) for parent in parents])
            self.audit(db, actor, key, 'task_created')
            return self.row(db, 'tasks', key)

    def set_role(self, human_principal, agent, payload):
        require(human_principal, {'human'})
        agent = text(agent, 'agent', 200)
        for key in ['model', 'family', 'role']:
            text(payload.get(key), key, 200)
        data = safe_payload(payload)
        with self.transaction() as db:
            old = db.execute('SELECT * FROM role_grants WHERE agent=?', (agent,)).fetchone()
            changed = old is not None and any(old[k] != payload[k] for k in ['model', 'family', 'role'])
            state = 'paused' if changed else ('active' if old is None else old['state'])
            if not changed and payload.get('confirm') is True:
                state = 'active'
            revision = old['revision'] + 1 if old else 1
            db.execute('INSERT OR REPLACE INTO role_grants VALUES(?,?,?,?,?,?,?)',
                       (agent, payload['model'], payload['family'], payload['role'], state, revision, data))
            self.audit(db, human_principal, agent, 'role_changed', {'state': state, 'revision': revision})
            return self.row(db, 'role_grants', agent, column='agent')

    def create_decision(self, actor, plan_id, *, intended_subject, expires_at):
        require(actor, {'human', 'controller'})
        intended_subject = text(intended_subject, 'intended subject', 240)
        expiry = timestamp(expires_at)
        if expiry <= self.now():
            raise RecordError('decision must expire in the future')
        with self.transaction() as db:
            plan = self.row(db, 'plans', plan_id)
            if plan['state'] != 'draft' or db.execute("SELECT 1 FROM decisions WHERE plan_id=? AND state='pending'", (plan_id,)).fetchone():
                raise RecordError('only a draft plan without a pending decision can receive a card')
            key = identifier('decision')
            db.execute('INSERT INTO decisions VALUES(?,?,?,?,?,?,1,NULL,NULL,?)',
                       (key, plan['project_id'], plan_id, intended_subject, expiry.isoformat(), 'pending', safe_payload({'manifest_hash': manifest_hash(plan)})))
            self.audit(db, actor, key, 'decision_created')
            return self.row(db, 'decisions', key)

    def record_decision(self, principal, decision_id, expected_revision, action, source):
        require(principal, {'human'})
        text(source, 'decision evidence')
        if action not in {'approve', 'decline', 'ask'}:
            raise RecordError('unknown decision action')
        try:
            with self.transaction() as db:
                decision = self.row(db, 'decisions', decision_id)
                plan = self.row(db, 'plans', decision['plan_id'])
                latest = db.execute('SELECT MAX(revision) FROM plans WHERE project_id=?', (plan['project_id'],)).fetchone()[0]
                if (decision['intended_subject'] != principal.id or decision['state'] != 'pending'
                        or type(expected_revision) is not int or expected_revision != decision['revision']
                        or timestamp(decision['expires_at']) <= self.now() or plan['revision'] != latest
                        or json.loads(decision['data']).get('manifest_hash') != manifest_hash(plan)):
                    raise RecordError('decision identity, revision, expiry or single-use check failed')
                data = safe_payload({'source': source, 'actor': principal.id, 'manifest_hash': manifest_hash(plan)})
                db.execute("UPDATE decisions SET state='consumed',action=?,consumed_at=?,revision=revision+1,data=? WHERE id=?",
                           (action, self.now().isoformat(), data, decision_id))
                state = {'approve': 'approved', 'decline': 'declined', 'ask': 'revision_requested'}[action]
                if action == 'approve':
                    prior = db.execute("SELECT id FROM plans WHERE project_id=? AND state='approved' AND id<>?", (plan['project_id'], plan['id'])).fetchall()
                    for approved in prior:
                        db.execute("UPDATE plans SET state='superseded' WHERE id=?", (approved['id'],))
                        self.audit(db, principal, approved['id'], 'plan_superseded',
                                   {'replacement_plan': plan['id'], 'decision_id': decision_id})
                db.execute('UPDATE plans SET state=? WHERE id=?', (state, plan['id']))
                self.audit(db, principal, decision_id, 'decision_consumed', {'action': action, 'source': source})
                return self.row(db, 'decisions', decision_id)
        except RecordError:
            # The rejection cannot commit domain mutations from the failed transaction.
            with self.transaction() as db:
                self.audit(db, principal, decision_id, 'decision_rejected')
            raise

    def snapshot(self, project_id=None):
        with self.transaction() as db:
            result = {name: [dict(r) for r in db.execute(f'SELECT * FROM {name}')] for name in TABLES}
            if project_id is not None:
                self.row(db, 'projects', project_id)
                # Never silently return cross-project records through a project view.
                task_ids = {t['id'] for t in result['tasks'] if t['project_id'] == project_id}
                incident_ids = {i['id'] for i in result['incidents'] if i['task_id'] in task_ids}
                for name, rows in result.items():
                    if name == 'projects':
                        result[name] = [r for r in rows if r['id'] == project_id]
                    elif name in {'plans', 'tasks', 'decisions', 'notices'}:
                        result[name] = [r for r in rows if r['project_id'] == project_id]
                    elif name in {'runs', 'claims', 'dependencies', 'incidents'}:
                        result[name] = [r for r in rows if r['task_id'] in task_ids]
                    elif name == 'incident_attempts':
                        result[name] = [r for r in rows if r['incident_id'] in incident_ids]
                    elif name in {'scorecard_events', 'audit_events'}:
                        result[name] = []  # Global audit/count queries require full view.
            return result

    def _eligible(self, db, task):
        plan = self.row(db, 'plans', task['plan_id'])
        role = self.row(db, 'role_grants', task['assignee'], column='agent')
        if plan['state'] != 'approved' or role['state'] != 'active':
            raise RecordError('task-bound approved plan and active role required')
        approvals = db.execute("SELECT data FROM decisions WHERE plan_id=? AND state='consumed' AND action='approve'", (plan['id'],)).fetchall()
        if not any(json.loads(a[0]).get('manifest_hash') == manifest_hash(plan) for a in approvals):
            raise RecordError('plan action manifest lacks matching human approval')
        edges = db.execute('SELECT p.state,d.gate FROM dependencies d JOIN tasks p ON p.id=d.parent_id WHERE d.task_id=?', (task['id'],)).fetchall()
        allowed = {'output': {'review', 'reviewed', 'accepted'}, 'reviewed': {'reviewed', 'accepted'}, 'accepted': {'accepted'}}
        if any(edge[0] not in allowed[edge[1]] for edge in edges):
            raise RecordError('dependency has not reached its approved gate')
        return role

    def claim(self, runner, task_id, *, expected_revision, request_id):
        require(runner, {'controller'})
        text(request_id, 'request id', 64)
        with self.transaction() as db:
            return self._claim(db, runner, task_id, expected_revision=expected_revision, request_id=request_id)

    def _claim(self, db, runner, task_id, *, expected_revision, request_id, expected_role_revision=None):
        from datetime import timedelta
        require(runner, {'controller'})
        text(request_id, 'request id', 64)
        if expected_role_revision is not None and (type(expected_role_revision) is not int or expected_role_revision < 1):
            raise RecordError('invalid preflight role revision')
        existing = db.execute('SELECT * FROM runs WHERE request_id=?', (request_id,)).fetchone()
        epoch = db.execute('SELECT restore_epoch FROM record_meta WHERE id=1').fetchone()[0]
        if existing:
            claim = self.row(db, 'claims', existing['claim_id'])
            if existing['task_id'] != task_id or claim['runner'] != runner.id or claim['restore_epoch'] != epoch:
                raise RecordError('request identity conflict')
            # A replay acknowledges the same live claim, never permission
            # to relaunch completed, held, expired or superseded work.
            live, task, run = self._live_claim(db, runner, claim)
            if expected_role_revision is not None and json.loads(run['data'])['role_revision'] != expected_role_revision:
                raise RecordError('role changed since native preflight')
            return claim
        task = self.row(db, 'tasks', task_id)
        role = self._eligible(db, task)
        if expected_role_revision is not None and role['revision'] != expected_role_revision:
            raise RecordError('role changed since native preflight')
        if task['state'] != 'ready' or type(expected_revision) is not int or task['revision'] != expected_revision or task['attempts'] >= 3:
            raise RecordError('task is not claimable at that revision')
        now = self.now()
        claim_id, run_id = identifier('claim'), identifier('run')
        attempt, generation = task['attempts'] + 1, task['generation'] + 1
        lease_until = (now + timedelta(seconds=min(self.lease_seconds, self.deadline_seconds))).isoformat()
        deadline_at = (now + timedelta(seconds=self.deadline_seconds)).isoformat()
        db.execute('INSERT INTO claims VALUES(?,?,?,?,?,?,?,?,?,?)',
                   (claim_id, task_id, run_id, runner.id, attempt, generation, epoch, lease_until, 'active', '{}'))
        db.execute('''INSERT INTO runs(id,task_id,claim_id,attempt,request_id,started_at,deadline_at,
                      closeout_validation,containment_state,usage_state,data)
                      VALUES(?,?,?,?,?,?,?,'missing','unconfirmed','unknown',?)''',
                   (run_id, task_id, claim_id, attempt, request_id, now.isoformat(), deadline_at,
                    safe_payload({'model': role['model'], 'family': role['family'],
                                  'role_revision': role['revision'], 'rules_version': '1.0'})))
        db.execute("UPDATE tasks SET state='running',revision=revision+1,generation=?,attempts=? WHERE id=?", (generation, attempt, task_id))
        self.audit(db, runner, task_id, 'claimed', {'run_id': run_id, 'attempt': attempt, 'generation': generation})
        return self.row(db, 'claims', claim_id)

    def _live_claim(self, db, runner, supplied):
        require(runner, {'controller'})
        claim = self.row(db, 'claims', supplied.get('id'))
        task = self.row(db, 'tasks', claim['task_id'])
        run = self.row(db, 'runs', claim['run_id'])
        epoch = db.execute('SELECT restore_epoch FROM record_meta WHERE id=1').fetchone()[0]
        fields = ['task_id', 'run_id', 'attempt', 'generation', 'restore_epoch']
        if (any(supplied.get(k) != claim[k] for k in fields) or claim['runner'] != runner.id
                or claim['state'] != 'active' or claim['restore_epoch'] != epoch
                or task['state'] != 'running' or task['generation'] != claim['generation']
                or task['attempts'] != claim['attempt'] or timestamp(claim['lease_until']) <= self.now()
                or timestamp(run['deadline_at']) <= self.now()):
            raise RecordError('stale, expired or foreign claim')
        role = self._eligible(db, task)
        meta = json.loads(run['data'])
        if role['revision'] != meta['role_revision'] or role['model'] != meta['model']:
            raise RecordError('role changed since launch')
        return claim, task, run

    def renew(self, runner, claim, *, lease_until):
        until = timestamp(lease_until)
        with self.transaction() as db:
            current, task, run = self._live_claim(db, runner, claim)
            if until <= self.now() or until < timestamp(current['lease_until']) or until > timestamp(run['deadline_at']):
                raise RecordError('invalid renewal bound')
            db.execute('UPDATE claims SET lease_until=? WHERE id=?', (until.isoformat(), current['id']))
            self.audit(db, runner, task['id'], 'lease_renewed')
            return self.row(db, 'claims', current['id'])

    def _incident(self, db, task, run_id, state):
        old = db.execute('SELECT id FROM incidents WHERE task_id=?', (task['id'],)).fetchone()
        key = old[0] if old else identifier('incident')
        if old:
            db.execute('UPDATE incidents SET state=? WHERE id=?', (state, key))
        else:
            db.execute('INSERT INTO incidents VALUES(?,?,?,?)', (key, task['id'], state, '{}'))
        db.execute('INSERT OR IGNORE INTO incident_attempts VALUES(?,?)', (key, run_id))

    @staticmethod
    def _closeout_validation(closeout, task, run):
        if closeout is None:
            return 'missing'
        names = {'task', 'attempt', 'status', 'produced', 'changed', 'unblocked',
                 'memory-used', 'checks-run', 'next'}
        if not isinstance(closeout, dict) or not names.issubset(closeout):
            return 'invalid'
        if closeout['task'] != task['id'] or closeout['attempt'] != run['attempt']:
            return 'invalid'
        if closeout['status'] not in {'done', 'partial', 'failed', 'invalid-task', 'needs-decision'}:
            return 'invalid'
        checks = closeout['checks-run']
        if not isinstance(checks, list) or any(not isinstance(c, dict) or
                not isinstance(c.get('name'), str) or not c['name'].strip() or
                type(c.get('passed')) is not bool or not isinstance(c.get('evidence'), str)
                or not c['evidence'].strip() for c in checks):
            return 'invalid'
        if closeout['status'] == 'done' and (not checks or not all(c['passed'] for c in checks)
                                             or not closeout['produced'] or closeout['produced'] == 'nothing'):
            return 'invalid'
        if not closeout['memory-used'] or not closeout['next']:
            return 'invalid'
        return 'valid'

    def record_run(self, runner, claim, receipt):
        require(runner, {'controller'})
        with self.transaction() as db:
            return self._record_run(db, runner, claim, receipt)

    def _record_run(self, db, runner, claim, receipt):
        import math
        safe_payload(receipt)
        required = {'ended_at', 'exit_status', 'closeout', 'containment_state', 'termination_evidence', 'usage'}
        if not isinstance(receipt, dict) or not required.issubset(receipt):
            raise RecordError('incomplete run receipt')
        ended = timestamp(receipt['ended_at'])
        exit_status = receipt['exit_status']
        if exit_status is not None and type(exit_status) is not int:
            raise RecordError('exit status must be an integer or unknown')
        containment = receipt['containment_state']
        evidence = receipt['termination_evidence']
        if containment not in {'verified_empty', 'unconfirmed'} or not isinstance(evidence, list) or any(not isinstance(v, str) or not v.strip() for v in evidence):
            raise RecordError('invalid containment evidence')
        if containment == 'verified_empty' and not evidence:
            raise RecordError('verified-empty status requires controller evidence')
        usage = receipt['usage']
        if not isinstance(usage, dict) or usage.get('state') not in {'unknown', 'measured'}:
            raise RecordError('usage state must be explicit')
        units = usage.get('units')
        if usage['state'] == 'unknown' and units is not None:
            raise RecordError('unknown usage must remain null')
        if usage['state'] == 'measured' and (not isinstance(units, dict) or not units or
                any(type(v) not in {int, float} or not math.isfinite(v) or v < 0 for v in units.values())):
            raise RecordError('usage measurements must be finite nonnegative numbers')
        for cost in ['estimated_cost', 'actual_charge']:
            charge = usage.get(cost)
            if charge is not None and (not isinstance(charge, dict) or
                    type(charge.get('amount')) not in {int, float} or not math.isfinite(charge['amount']) or
                    charge['amount'] < 0 or not isinstance(charge.get('currency'), str) or
                    not isinstance(charge.get('source'), str) or not charge['source'].strip()):
                raise RecordError('cost requires measured amount, currency and source')
        current, task, run = self._live_claim(db, runner, claim)
        if ended < timestamp(run['started_at']) or ended > self.now():
            raise RecordError('run end must be between start and current time')
        validation = self._closeout_validation(receipt['closeout'], task, run)
        data = json.loads(run['data'])
        data['receipt_controller'] = runner.id
        db.execute("""UPDATE runs SET ended_at=?,exit_status=?,closeout=?,closeout_validation=?,
            containment_state=?,termination_evidence=?,usage_state=?,usage=?,estimated_cost=?,actual_charge=?,data=? WHERE id=?""",
            (ended.isoformat(), exit_status, safe_payload(receipt['closeout']), validation,
             containment, safe_payload({'controller': runner.id, 'references': evidence}),
             usage['state'], safe_payload(units) if units is not None else None,
             safe_payload(usage['estimated_cost']) if usage.get('estimated_cost') is not None else None,
             safe_payload(usage['actual_charge']) if usage.get('actual_charge') is not None else None,
             safe_payload(data), run['id']))
        success = (validation == 'valid' and receipt['closeout']['status'] == 'done'
                   and exit_status == 0 and containment == 'verified_empty')
        if containment != 'verified_empty' or exit_status is None:
            # A verified-empty process group does not prove a successful exit.
            state, claim_state = 'held', 'held'
            self._incident(db, task, run['id'], 'held')
        elif validation == 'valid' and receipt['closeout']['status'] == 'needs-decision':
            # Preserve this run as history, but do not turn a human wait into
            # a failure/retry. The controller must not claim it again.
            state, claim_state = 'needs_decision', 'closed'
            if exit_status != 0:
                self._incident(db, task, run['id'], 'escalated')
        elif success:
            state, claim_state = 'review', 'closed'
            db.execute("UPDATE incidents SET state='recovered' WHERE task_id=?", (task['id'],))
        else:
            state, claim_state = ('ready' if task['attempts'] < 3 else 'failed'), 'closed'
            self._incident(db, task, run['id'], 'open' if task['attempts'] < 3 else 'escalated')
        db.execute('UPDATE claims SET state=? WHERE id=?', (claim_state, current['id']))
        db.execute('UPDATE tasks SET state=?,revision=revision+1 WHERE id=?', (state, task['id']))
        self.audit(db, runner, task['id'], 'run_receipt', {'run_id': run['id'], 'validation': validation, 'state': state})
        return self.row(db, 'runs', run['id'])

    def append_notice(self, actor, payload, *, claim):
        safe_payload(payload)
        with self.transaction() as db:
            current, task, run = self._live_claim(db, actor, claim)
            if payload.get('task_id') != task['id']:
                raise RecordError('notice task differs from claim')
            recipient = text(payload.get('recipient'), 'recipient', 240)
            kind = payload.get('kind')
            if kind not in {'interface_changed', 'finished', 'blocked', 'collision', 'question'}:
                raise RecordError('invalid notice kind')
            text(payload.get('reference'), 'notice evidence')
            key = identifier('notice')
            db.execute('INSERT INTO notices VALUES(?,?,?,?,?,?,?)',
                       (key, task['project_id'], task['id'], actor.id, recipient, kind,
                        safe_payload({**payload, 'generation': current['generation']})))
            self.audit(db, actor, task['id'], 'notice_added')
            return self.row(db, 'notices', key)

    def record_review(self, reviewer, task_id, expected_revision, verdict, evidence):
        require(reviewer, {'worker'})
        if verdict not in {'pass', 'changes'} or not isinstance(evidence, list) or not evidence or any(not isinstance(v, str) or not v.strip() for v in evidence):
            raise RecordError('review needs a verdict and evidence')
        with self.transaction() as db:
            task = self.row(db, 'tasks', task_id)
            role = self.row(db, 'role_grants', reviewer.id, column='agent')
            run = db.execute('SELECT * FROM runs WHERE task_id=? ORDER BY attempt DESC LIMIT 1', (task_id,)).fetchone()
            if task['state'] != 'review' or type(expected_revision) is not int or task['revision'] != expected_revision or run is None:
                raise RecordError('task is not awaiting this review')
            producer = json.loads(run['data'])
            if reviewer.id == task['assignee'] or role['family'] == producer['family'] or role['state'] != 'active':
                raise RecordError('independent active reviewer required')
            data = json.loads(task['data'])
            count = data.get('review_count', 0) + 1
            data.update(review_count=count, review={'reviewer': reviewer.id, 'family': role['family'], 'model': role['model'], 'verdict': verdict, 'evidence': evidence})
            state = 'reviewed' if verdict == 'pass' else ('revision_required' if count == 1 else 'needs_decision')
            db.execute('UPDATE tasks SET state=?,revision=revision+1,data=? WHERE id=?', (state, safe_payload(data), task_id))
            self.audit(db, reviewer, task_id, 'reviewed', {'verdict': verdict, 'evidence': evidence})
            db.execute('INSERT INTO scorecard_events VALUES(?,?,?,?,?)',
                       (identifier('count'), reviewer.id, 'review', run['id'], safe_payload({'verdict': verdict})))
            return self.row(db, 'tasks', task_id)

    def accept_result(self, human_principal, task_id, expected_revision, evidence):
        require(human_principal, {'human'})
        if not isinstance(evidence, list) or not evidence or any(not isinstance(v, str) or not v.strip() for v in evidence):
            raise RecordError('human acceptance requires evidence')
        with self.transaction() as db:
            task = self.row(db, 'tasks', task_id)
            self._eligible(db, task)
            if task['state'] != 'reviewed' or type(expected_revision) is not int or task['revision'] != expected_revision:
                raise RecordError('independent review required before acceptance')
            db.execute("UPDATE tasks SET state='accepted',revision=revision+1 WHERE id=?", (task_id,))
            self.audit(db, human_principal, task_id, 'result_accepted', {'evidence': evidence})
            return self.row(db, 'tasks', task_id)

    def answer_task(self, human, task_id, *, expected_revision, run_id, answer, evidence):
        """Answer a run's question within existing authority, never approve new scope."""
        require(human, {'human'})
        answer = text(answer, 'human answer')
        if not isinstance(evidence, list) or not evidence or any(not isinstance(v, str) or not v.strip() for v in evidence):
            raise RecordError('human answer requires evidence references')
        safe_payload(evidence)
        with self.transaction() as db:
            task = self.row(db, 'tasks', task_id)
            self._eligible(db, task)
            run = db.execute('SELECT * FROM runs WHERE task_id=? ORDER BY attempt DESC LIMIT 1', (task_id,)).fetchone()
            if (task['state'] != 'needs_decision' or type(expected_revision) is not int
                    or task['revision'] != expected_revision or task['attempts'] >= 3
                    or run is None or run['id'] != run_id):
                raise RecordError('task is not awaiting this answer or has no attempts remaining')
            claim = self.row(db, 'claims', run['claim_id'])
            closeout = json.loads(run['closeout']) if run['closeout'] else None
            data = json.loads(task['data'])
            if (data.get('review_count', 0) >= 2 or claim['state'] != 'closed'
                    or run['ended_at'] is None or run['exit_status'] is None
                    or run['containment_state'] != 'verified_empty'
                    or self._closeout_validation(closeout, task, run) != 'valid'
                    or closeout['status'] != 'needs-decision'):
                raise RecordError('verified run question required; review disagreements need a separate decision')
            plan = self.row(db, 'plans', task['plan_id'])
            approval = db.execute("SELECT * FROM decisions WHERE plan_id=? AND state='consumed' AND action='approve' AND intended_subject=?",
                                  (plan['id'], human.id)).fetchone()
            if approval is None or json.loads(approval['data']).get('manifest_hash') != manifest_hash(plan):
                raise RecordError('answer must come from the approving human')
            entry = {'run_id': run_id, 'actor': human.id, 'answer': answer,
                     'evidence': evidence, 'at': self.now().isoformat(), 'revision': expected_revision}
            data.setdefault('human_answers', []).append(entry)
            db.execute("UPDATE tasks SET state='ready',revision=revision+1,data=? WHERE id=?", (safe_payload(data), task_id))
            self.audit(db, human, task_id, 'human_answered', entry)
            return self.row(db, 'tasks', task_id)

    def reconcile(self, controller, run_id, *, termination_evidence, outcome):
        require(controller, {'controller'})
        if outcome not in {'failed', 'unknown', 'completed'}:
            raise RecordError('unknown reconciliation outcome')
        if not isinstance(termination_evidence, list) or any(not isinstance(v, str) or not v.strip() for v in termination_evidence):
            raise RecordError('termination evidence must contain references')
        if outcome in {'failed', 'completed'} and not termination_evidence:
            raise RecordError('verified termination evidence is required before retry')
        with self.transaction() as db:
            run = self.row(db, 'runs', run_id)
            task = self.row(db, 'tasks', run['task_id'])
            claim = self.row(db, 'claims', run['claim_id'])
            if task['generation'] != claim['generation'] or claim['state'] not in {'active', 'held'}:
                raise RecordError('run is not the current reconciliation target')
            closeout = json.loads(run['closeout']) if run['closeout'] else None
            valid_closeout = self._closeout_validation(closeout, task, run) == 'valid'
            human_wait = (valid_closeout and closeout['status'] == 'needs-decision'
                          and run['exit_status'] is not None)
            if outcome == 'unknown':
                db.execute("UPDATE claims SET state='held' WHERE id=?", (claim['id'],))
                db.execute("UPDATE tasks SET state='held',revision=revision+1 WHERE id=?", (task['id'],))
            else:
                if outcome == 'completed':
                    if (run['ended_at'] is None or run['exit_status'] != 0 or not valid_closeout
                            or closeout['status'] not in {'done', 'needs-decision'}):
                        raise RecordError('completed reconciliation requires an existing successful receipt')
                    state = 'needs_decision' if human_wait else 'review'
                else:
                    state = 'needs_decision' if human_wait else ('ready' if task['attempts'] < 3 else 'failed')
                db.execute("UPDATE claims SET state='closed' WHERE id=?", (claim['id'],))
                db.execute('UPDATE tasks SET state=?,revision=revision+1,generation=generation+1 WHERE id=?', (state, task['id']))
                reconciled_at = self.now().isoformat()
                db.execute("UPDATE runs SET ended_at=COALESCE(ended_at,?),containment_state='verified_empty',termination_evidence=? WHERE id=?",
                           (reconciled_at, safe_payload({'controller': controller.id,
                            'references': termination_evidence, 'reconciled_at': reconciled_at}), run_id))
            incident = db.execute('SELECT id FROM incidents WHERE task_id=?', (task['id'],)).fetchone()
            incident_id = incident[0] if incident else identifier('incident')
            state = 'recovered' if outcome == 'completed' else ('held' if outcome == 'unknown' else ('escalated' if human_wait or task['attempts'] >= 3 else 'open'))
            if incident:
                db.execute('UPDATE incidents SET state=? WHERE id=?', (state, incident_id))
            else:
                db.execute('INSERT INTO incidents VALUES(?,?,?,?)', (incident_id, task['id'], state, '{}'))
            db.execute('INSERT OR IGNORE INTO incident_attempts VALUES(?,?)', (incident_id, run_id))
            self.audit(db, controller, task['id'], 'run_reconciled', {'run_id': run_id, 'outcome': outcome})
            return self.row(db, 'tasks', task['id'])


    def revise_task(self, controller, task_id, expected_revision, revision_note):
        require(controller, {'controller'})
        text(revision_note, 'revision evidence')
        with self.transaction() as db:
            task = self.row(db, 'tasks', task_id)
            self._eligible(db, task)
            data = json.loads(task['data'])
            if (task['state'] != 'revision_required' or type(expected_revision) is not int
                    or task['revision'] != expected_revision
                    or task['attempts'] >= 3 or data.get('review_count') != 1):
                raise RecordError('only the first requested revision may be resubmitted')
            data['revision_note'] = revision_note
            db.execute("UPDATE tasks SET state='ready',revision=revision+1,data=? WHERE id=?", (safe_payload(data), task_id))
            self.audit(db, controller, task_id, 'revision_requested', {'reference': revision_note})
            return self.row(db, 'tasks', task_id)
