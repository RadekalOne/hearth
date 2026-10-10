"""Read-only dashboard projections. No execution, authorization or schema changes."""
import json
import math
import re
from datetime import datetime, timezone


def timestamp(value):
    try:
        parsed = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return (parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)).timestamp()
    except (ValueError, TypeError, OverflowError):
        return None


def receipt(content):
    try:
        fields = json.loads(content)
        if not isinstance(fields, dict):
            return {}
    except (ValueError, TypeError):
        fields = {}
        for key in ('process_exit', 'closeout_verified'):
            found = re.search(r'\b' + key + r'\s*[:=]\s*(true|false|-?\d+)\b', str(content), re.I)
            if found:
                raw = found[1].lower()
                fields[key] = raw == 'true' if raw in ('true', 'false') else int(raw)
    safe = {}
    if type(fields.get('process_exit')) is int:
        safe['process_exit'] = fields['process_exit']
    elif isinstance(fields.get('process_exit'), str) and re.fullmatch(r'-?\d{1,8}', fields['process_exit']):
        safe['process_exit'] = int(fields['process_exit'])
    if type(fields.get('closeout_verified')) is bool:
        safe['closeout_verified'] = fields['closeout_verified']
    return safe


def watcher_state(age, cadence, fields):
    if fields.get('closeout_verified') is False or fields.get('process_exit') not in (None, 0, '0'):
        return 'failed'
    if cadence is None:
        return 'on-demand'
    if age is None or not math.isfinite(age) or age < 0 or cadence <= 0:
        return 'unknown'
    return 'stalled' if age > cadence * 3 else 'late' if age > cadence * 1.5 else 'ok'


def work_items(board, relays, now):
    items = []
    transitions = {'draft': {'task_proposed', 'revise', 'release'}, 'ready': {'ready'},
                   'running': {'claim'}, 'review': {'review'}, 'blocked': {'block'}, 'done': {'accept'}}
    for task in board.get('tasks', []):
        state = task.get('state', 'unknown')
        events = [e for e in board.get('activity', []) if e.get('task_id') == task['id']
                  and e.get('kind') in transitions.get(state, set()) and timestamp(e.get('at')) is not None]
        since = task.get('state_since') or (max(events, key=lambda e: timestamp(e['at']))['at'] if events else task.get('updated_at'))
        ts = timestamp(since)
        items.append({'id': task['id'], 'title': task.get('title', task['id']),
                      'state': {'ready': 'queued', 'draft': 'proposed', 'running': 'claimed'}.get(state, state),
                      'source_state': state, 'execution_verified': False,
                      'owner': task.get('assignee', ''), 'state_since': since,
                      'age_minutes': round((now - ts) / 60, 1) if ts is not None and ts <= now else None,
                      'age_basis': 'transition' if task.get('state_since') or events else 'last update; transition unavailable',
                      'project_id': task.get('project_id'), 'source_refs': [task['id']]})
    for relay in relays:
        ts = timestamp(relay.get('updated_at'))
        items.append({'id': relay['relay_id'], 'title': 'Interactive handoff',
                      'state': 'done' if relay.get('state') == 'resolved' else relay.get('state', 'unknown'),
                      'owner': relay.get('target_agent', ''), 'state_since': relay.get('updated_at'),
                      'age_minutes': round((now - ts) / 60, 1) if ts is not None and ts <= now else None,
                      'age_basis': 'relay state update', 'source_refs': [relay['relay_id']],
                      'source': relay.get('source', '')})
    return items


def memory_health(rows, ids, embeddings, threshold):
    knowledge = [(i, m) for i, m in rows if m.get('record_class', 'knowledge') == 'knowledge']
    # Include superseded knowledge in pair health: duplicate history is useful audit evidence.
    metadata = dict(knowledge)
    count = None
    pairs = []
    if embeddings is not None:
        count = 0
        for a in range(len(ids)):
            ma = metadata.get(ids[a], {})
            va = embeddings[a]
            norm_a = math.sqrt(sum(float(x) ** 2 for x in va))
            for b in range(a + 1, len(ids)):
                mb = metadata.get(ids[b], {})
                if (ma.get('wing'), ma.get('room')) != (mb.get('wing'), mb.get('room')):
                    continue
                vb = embeddings[b]
                norm_b = math.sqrt(sum(float(x) ** 2 for x in vb))
                if norm_a and norm_b:
                    distance = 1 - sum(float(x) * float(y) for x, y in zip(va, vb)) / (norm_a * norm_b)
                    if distance <= threshold:
                        count += 1
                        pairs.append([ids[a], ids[b]])
    total = len(rows)
    return {'knowledge_count': len(knowledge), 'total_count': total,
            'noise_ratio': (total - len(knowledge)) / total if total else 0,
            'superseded_count': sum(bool(m.get('superseded_by')) for _, m in rows),
            'near_duplicate_pair_count': count, 'near_duplicate_pairs': pairs,
            'duplicate_coverage': {'complete': embeddings is not None and len(ids) == len(knowledge),
                                   'scanned': len(ids), 'total': len(knowledge), 'threshold': threshold},
            'source_refs': [i for i, _ in rows], 'availability': 'available' if embeddings is not None else 'Embeddings unavailable'}
