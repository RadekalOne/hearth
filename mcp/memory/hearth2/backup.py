"""Versioned, logical work-record backup. Operator-only restore to a new path.

Bundles are data, never code or file paths. A checksum detects corruption; the
operator must separately establish the source's trust. No credentials are copied.
"""
import hashlib
import json
import os
import sqlite3
import tempfile
import uuid
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from .schema import Schema, TABLES, open_existing
from .store import RecordError, Store, safe_payload, timestamp, action_manifest, manifest_hash

MAX_BYTES = 64 * 1024 * 1024
MAX_ROWS = 100000
JSON_COLUMNS = {'data', 'closeout', 'termination_evidence', 'usage', 'estimated_cost', 'actual_charge'}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()


def digest(tables):
    return hashlib.sha256(canonical(tables)).hexdigest()


def validate_rows(tables):
    if not isinstance(tables, dict) or set(tables) != set(TABLES):
        raise RecordError('backup table set is incomplete or unknown')
    count = 0
    for name, rows in tables.items():
        if not isinstance(rows, list):
            raise RecordError('backup rows must be a list')
        count += len(rows)
        if count > MAX_ROWS:
            raise RecordError('backup row limit exceeded')
        for row in rows:
            if not isinstance(row, dict):
                raise RecordError('backup row must be an object')
            safe_payload(row)
            for key in JSON_COLUMNS & row.keys():
                if row[key] is not None:
                    try:
                        safe_payload(json.loads(row[key]))
                    except (ValueError, TypeError) as error:
                        raise RecordError('invalid or credential-bearing JSON column') from error


def validate_domain(tables):
    """A trusted bundle can still be damaged; validate state, not just its digest."""
    plans = {r['id']: r for r in tables['plans']}
    tasks = {r['id']: r for r in tables['tasks']}
    claims = {r['id']: r for r in tables['claims']}
    runs = {r['id']: r for r in tables['runs']}
    states = {'ready', 'running', 'held', 'review', 'reviewed', 'accepted', 'failed', 'revision_required', 'needs_decision'}
    for plan in plans.values():
        if plan['state'] not in {'draft', 'approved', 'declined', 'revision_requested'}:
            raise RecordError('invalid plan state')
        action_manifest(json.loads(plan['data']))
        if plan['state'] == 'approved' and not any(
                d['plan_id'] == plan['id'] and d['state'] == 'consumed' and d['action'] == 'approve'
                and json.loads(d['data']).get('manifest_hash') == manifest_hash(plan) for d in tables['decisions']):
            raise RecordError('approved plan lacks matching decision')
    for task in tasks.values():
        if task['state'] not in states or type(task['attempts']) is not int or not 0 <= task['attempts'] <= 3 or type(task['revision']) is not int or task['revision'] < 1 or type(task['generation']) is not int or task['generation'] < 0:
            raise RecordError('invalid task state or revision')
        plan = plans.get(task['plan_id'])
        if plan is None or task['project_id'] != plan['project_id']:
            raise RecordError('task plan relationship is invalid')
        action = action_manifest(json.loads(plan['data'])).get(task['action_id'])
        payload = json.loads(task['data'])
        if action is None or any(payload.get(k) != action[k] for k in ['recipient', 'ask', 'done_means', 'inputs', 'return']) or task['assignee'] != action['recipient']:
            raise RecordError('task differs from its approved action')
        edges = [e for e in tables['dependencies'] if e['task_id'] == task['id']]
        actual = {}
        for edge in edges:
            parent = tasks.get(edge['parent_id'])
            if parent is None or parent['plan_id'] != task['plan_id']:
                raise RecordError('invalid dependency plan')
            actual[parent['action_id']] = edge['gate']
        if actual != action['requires']:
            raise RecordError('dependency gates differ from action manifest')
        history = sorted([r for r in runs.values() if r['task_id'] == task['id']], key=lambda r: r['attempt'])
        if [r['attempt'] for r in history] != list(range(1, task['attempts'] + 1)):
            raise RecordError('attempt history is incomplete')
        if task['state'] in {'review', 'reviewed', 'accepted', 'revision_required', 'needs_decision'}:
            if not history:
                raise RecordError('completed state has no run')
            run = history[-1]
            closeout = json.loads(run['closeout']) if run['closeout'] is not None else None
            if run['ended_at'] is None or run['exit_status'] != 0 or run['containment_state'] != 'verified_empty' or Store._closeout_validation(closeout, task, run) != 'valid' or closeout['status'] != 'done':
                raise RecordError('completed state lacks successful run evidence')
        if task['state'] in {'reviewed', 'accepted'}:
            review = payload.get('review', {})
            if review.get('verdict') != 'pass' or not review.get('evidence') or review.get('reviewer') == task['assignee'] or review.get('family') == json.loads(history[-1]['data']).get('family'):
                raise RecordError('reviewed state lacks independent review')
        if task['state'] == 'accepted' and not any(a['entity_id'] == task['id'] and a['action'] == 'result_accepted' for a in tables['audit_events']):
            raise RecordError('accepted state lacks acceptance audit')
        if task['state'] in {'running', 'held'} and not any(c['task_id'] == task['id'] and c['state'] == ('active' if task['state'] == 'running' else 'held') and c['generation'] == task['generation'] for c in claims.values()):
            raise RecordError('active task lacks matching current claim')
        if task['state'] == 'ready' and task['attempts'] >= 3:
            raise RecordError('exhausted task cannot be ready')
    for claim in claims.values():
        run = runs.get(claim['run_id'])
        if claim['state'] not in {'active', 'held', 'closed'} or run is None or run['claim_id'] != claim['id'] or run['task_id'] != claim['task_id'] or run['attempt'] != claim['attempt']:
            raise RecordError('claim/run identity mismatch')
        timestamp(claim['lease_until'])
    for run in runs.values():
        if run['claim_id'] not in claims or run['task_id'] not in tasks:
            raise RecordError('run has no claim/task')
        if timestamp(run['deadline_at']) <= timestamp(run['started_at']) or run['ended_at'] is not None and timestamp(run['ended_at']) < timestamp(run['started_at']):
            raise RecordError('invalid run times')
        if run['usage_state'] not in {'unknown', 'measured'} or run['usage_state'] == 'unknown' and run['usage'] is not None:
            raise RecordError('invalid usage state')
        if run['containment_state'] not in {'unconfirmed', 'verified_empty'} or run['closeout_validation'] not in {'missing', 'invalid', 'valid'}:
            raise RecordError('invalid run evidence state')
        if run['containment_state'] == 'verified_empty' and (run['termination_evidence'] is None or not json.loads(run['termination_evidence']).get('references')):
            raise RecordError('verified termination lacks evidence')
    for decision in tables['decisions']:
        if decision['plan_id'] not in plans or decision['project_id'] != plans[decision['plan_id']]['project_id'] or decision['state'] not in {'pending', 'consumed', 'held'}:
            raise RecordError('invalid decision relationship or state')
        timestamp(decision['expires_at'])
        if decision['state'] == 'consumed' and (decision['action'] not in {'approve', 'decline', 'ask'} or decision['consumed_at'] is None or timestamp(decision['consumed_at']) >= timestamp(decision['expires_at']) or not json.loads(decision['data']).get('source')):
            raise RecordError('consumed decision lacks valid evidence')


def fsync_dir(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def publish(stage, destination):
    # link is atomic and refuses an existing destination, including symlinks.
    os.link(stage, destination)
    fsync_dir(Path(destination).parent)


def export_record(source: Path, destination: Path):
    source, destination = Path(source), Path(destination)
    if source.resolve() == destination.resolve():
        raise RecordError('export destination cannot be the database')
    if destination.exists() or destination.is_symlink():
        raise RecordError('export refuses an existing destination')
    with closing(sqlite3.connect(source.resolve().as_uri() + '?mode=ro', uri=True,
                                timeout=15, isolation_level=None)) as db:
        db.execute('BEGIN')
        Schema.validate(db)
        meta = db.execute('SELECT instance_id,restore_epoch FROM record_meta WHERE id=1').fetchone()
        db.row_factory = sqlite3.Row
        tables = {name: [dict(r) for r in db.execute(f'SELECT * FROM {name}')] for name in TABLES}
        validate_rows(tables)
        validate_domain(tables)
        manifest = {'format': 'hearth2-work-record', 'format_version': 1, 'schema_version': 1,
                    'instance_id': meta[0], 'restore_epoch': meta[1],
                    'exported_at': datetime.now(timezone.utc).isoformat(),
                    'counts': {name: len(rows) for name, rows in tables.items()}, 'sha256': digest(tables)}
        db.execute('COMMIT')
    encoded = canonical({'manifest': manifest, 'tables': tables})
    if len(encoded) > MAX_BYTES:
        raise RecordError('backup byte limit exceeded')
    fd, filename = tempfile.mkstemp(prefix='.hearth2-export-', dir=destination.parent)
    stage = Path(filename)
    try:
        with os.fdopen(fd, 'wb') as output:
            output.write(encoded)
            output.flush()
            os.fsync(output.fileno())
        publish(stage, destination)
    finally:
        stage.unlink(missing_ok=True)
    return manifest


def strict_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise RecordError('duplicate JSON key')
        result[key] = value
    return result


def read_bundle(bundle):
    with Path(bundle).open('rb') as source:
        raw = source.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise RecordError('backup byte limit exceeded')
    try:
        data = json.loads(raw, object_pairs_hook=strict_pairs,
                          parse_constant=lambda _: (_ for _ in ()).throw(RecordError('non-finite JSON')))
        if not isinstance(data, dict) or set(data) != {'manifest', 'tables'}:
            raise RecordError('invalid bundle envelope')
        manifest, tables = data['manifest'], data['tables']
        if not isinstance(manifest, dict) or manifest.get('format') != 'hearth2-work-record' or type(manifest.get('format_version')) is not int or manifest['format_version'] != 1 or manifest.get('schema_version') != 1:
            raise RecordError('unsupported backup version')
        timestamp(manifest['exported_at'])
        validate_rows(tables)
        validate_domain(tables)
        if manifest['sha256'] != digest(tables) or manifest['counts'] != {k: len(v) for k, v in tables.items()}:
            raise RecordError('backup checksum or row counts differ')
        return manifest, tables
    except (ValueError, TypeError, KeyError, AttributeError, UnicodeError, RecursionError) as error:
        raise RecordError('invalid or corrupt backup') from error


def restore_record(bundle: Path, target: Path, *, controller_stopped: bool):
    if controller_stopped is not True:
        raise RecordError('restore requires an explicitly stopped controller')
    target = Path(target)
    if target.exists() or target.is_symlink():
        raise RecordError('restore requires a new, absent database path')
    manifest, tables = read_bundle(bundle)
    fd, filename = tempfile.mkstemp(prefix='.hearth2-restore-', dir=target.parent)
    os.close(fd)
    stage = Path(filename)
    try:
        Schema.initialize(stage, enabled=True)
        with closing(open_existing(stage)) as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('PRAGMA defer_foreign_keys=ON')
            for name in TABLES:
                allowed = [r[1] for r in db.execute(f'PRAGMA table_info({name})')]
                for row in tables[name]:
                    if set(row) != set(allowed):
                        raise RecordError('backup columns do not match schema')
                    columns = ','.join(allowed)
                    placeholders = ','.join('?' for _ in allowed)
                    db.execute(f'INSERT INTO {name}({columns}) VALUES({placeholders})', [row[k] for k in allowed])
            if db.execute('PRAGMA foreign_key_check').fetchall():
                raise RecordError('backup contains dangling relationships')
            # Cross-project links can be valid FKs while violating application policy.
            if db.execute('''SELECT 1 FROM tasks t JOIN plans p ON p.id=t.plan_id
                             WHERE t.project_id<>p.project_id LIMIT 1''').fetchone() or db.execute('''
                             SELECT 1 FROM dependencies d JOIN tasks t ON t.id=d.task_id
                             JOIN tasks p ON p.id=d.parent_id WHERE t.project_id<>p.project_id LIMIT 1''').fetchone():
                raise RecordError('backup contains cross-project relationships')
            epoch = uuid.uuid4().hex
            db.execute('UPDATE record_meta SET restore_epoch=? WHERE id=1', (epoch,))
            active = db.execute("SELECT id,task_id,run_id,generation FROM claims WHERE state IN ('active','held')").fetchall()
            for claim_id, task_id, run_id, generation in active:
                db.execute("UPDATE tasks SET state='held',revision=revision+1,generation=generation+1 WHERE id=?", (task_id,))
                generation = db.execute('SELECT generation FROM tasks WHERE id=?', (task_id,)).fetchone()[0]
                db.execute("UPDATE claims SET state='held',generation=? WHERE id=?", (generation, claim_id))
                # Epoch stays original on historical claims, invalidating every old writer.
                db.execute("UPDATE runs SET containment_state='unconfirmed' WHERE id=?", (run_id,))
            db.execute("UPDATE tasks SET state='held',revision=revision+1 WHERE state='running'")
            db.execute("UPDATE decisions SET state='held',revision=revision+1 WHERE state='pending'")
            db.execute('INSERT INTO audit_events(actor,entity_id,action,at,data) VALUES(?,?,?,?,?)',
                       ('restore-operator', 'record', 'restored', datetime.now(timezone.utc).isoformat(),
                        safe_payload({'source_instance': manifest['instance_id'], 'source_digest': manifest['sha256'],
                                      'held_runs': len(active), 'new_epoch': epoch})))
            if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise RecordError('restored database integrity check failed')
            db.execute('COMMIT')
        with stage.open('rb') as stream:
            os.fsync(stream.fileno())
        publish(stage, target)
        return {'target': str(target), 'schema_version': 1, 'held_runs': len(active), 'restore_epoch': epoch}
    except sqlite3.DatabaseError as error:
        raise RecordError('backup violates database constraints') from error
    finally:
        stage.unlink(missing_ok=True)
        for suffix in ['-journal', '-wal', '-shm']:
            Path(str(stage) + suffix).unlink(missing_ok=True)
