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


def watcher_state(age, cadence, fields, event_driven=False):
    if fields.get('closeout_verified') is False or fields.get('process_exit') not in (None, 0, '0'):
        return 'failed'
    if cadence is None:
        return 'on-demand' if event_driven else 'unknown'
    if age is None or not math.isfinite(age) or age < 0 or cadence <= 0:
        return 'unknown'
    return 'stalled' if age > cadence * 3 else 'late' if age > cadence * 1.5 else 'ok'


def watchers(rows, registry, now):
    """Exact declared identities only. Runner results belong to their parent."""
    result = []
    for declaration in registry:
        kind = declaration.get('kind')
        cadence = declaration.get('cadence_minutes')
        if declaration.get('active') is not True or kind not in ('recurring', 'event-driven'):
            continue
        if kind == 'recurring' and (type(cadence) not in (int, float) or not math.isfinite(cadence) or cadence <= 0):
            continue
        agent, surface, monitor = (declaration[k].lower() for k in ('agent', 'surface', 'monitor'))
        runner_monitors = declaration.get('receipt_monitors', [])
        names = [monitor, *runner_monitors]
        matched = [(i, m, content) for i, m, content in rows
                   if (m.get('agent', '').lower(), m.get('surface', '').lower()) == (agent, surface)
                   and m.get('monitor') in names]
        matched.sort(key=lambda r: (names.index(r[1]['monitor']), r[1].get('updated_at') or '', r[0]))
        runners = [r for r in matched if r[1]['monitor'] in runner_monitors]
        candidates = runners or matched
        selected = max(candidates, key=lambda r: (timestamp(r[1].get('updated_at')) or float('-inf'), r[0])) if candidates else None
        at = selected[1].get('updated_at') if selected else None
        ts = timestamp(at)
        age = (now - ts) / 60 if ts is not None else None
        fields = receipt(selected[2]) if selected else {}
        result.append({'id': declaration['id'], 'key': f'{agent}@{surface}', 'agent': agent, 'surface': surface,
                       'monitor': monitor, 'active': True, 'kind': kind,
                       'declaration_id': declaration['id'], 'declaration_source': declaration.get('source', ''),
                       'expected_every_minutes': cadence if kind == 'recurring' else None,
                       'age_minutes': round(age, 1) if age is not None else None, 'checkpoint_at': at,
                       'state': watcher_state(age, cadence if kind == 'recurring' else None, fields, kind == 'event-driven'),
                       'receipt': fields, 'receipt_source': selected[0] if selected else None,
                       'source_refs': [r[0] for r in matched] or [declaration['id']],
                       'evidence': [{'id': i, 'monitor': m['monitor'], 'at': m.get('updated_at'), 'receipt': receipt(content)}
                                    for i, m, content in matched]})
    return result


def attention_inbox(inbox, monitors, work):
    items = list(inbox.get('items', []))
    for watcher in monitors:
        if watcher['state'] == 'failed':
            items.append({**watcher, 'kind': 'failed_watcher', 'label': 'Failed watcher needs attention',
                          'title': f"{watcher['agent']} / {watcher['monitor']}",
                          'body': 'The latest runner receipt reports a failure or unverified closeout.'})
    for item in work:
        age = item.get('age_minutes')
        if item['state'] == 'queued' and age is not None and age > 3 * 24 * 60:
            items.append({**item, 'kind': 'overdue_work', 'label': 'Queued for more than 3 days',
                          'body': item.get('title', item['id'])})
    items.sort(key=lambda i: (0 if i['kind'] == 'failed_watcher' else 1 if i['kind'] == 'blocked' else 2,
                              -(i.get('age_minutes') or 0), i.get('id') or i.get('event_id', '')))
    counts = {}
    for item in items:
        counts[item['kind']] = counts.get(item['kind'], 0) + 1
    return {**inbox, 'items': items, 'total': len(items), 'counts': counts, 'queued_threshold_days': 3}


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
        summary = ' '.join(str(relay.get('request') or '').split())[:120]
        title = summary or f"Handoff to {relay.get('target_agent') or 'unassigned'} · {relay['relay_id']}"
        items.append({'id': relay['relay_id'], 'title': title,
                      'state': 'done' if relay.get('state') == 'resolved' else relay.get('state', 'unknown'),
                      'owner': relay.get('target_agent', ''), 'state_since': relay.get('updated_at'),
                      'age_minutes': round((now - ts) / 60, 1) if ts is not None and ts <= now else None,
                      'age_basis': 'relay state update', 'source_refs': [relay['relay_id']],
                      'source': relay.get('source', '')})
    items.sort(key=lambda i: (i['state'] == 'done', -(i.get('age_minutes') or 0), i['id']))
    return items


def memory_health(rows, ids, embeddings, threshold):
    knowledge = [(i, m) for i, m in rows if m.get('record_class', 'knowledge') == 'knowledge']
    # Include superseded knowledge in pair health: duplicate history is useful audit evidence.
    metadata = dict(knowledge)
    count = None
    pairs = []
    if embeddings is not None:
        count = 0
        # Normalize once, rather than repeating vector conversion for every pair.
        vectors = []
        for vector in embeddings:
            values = [float(x) for x in vector]
            norm = math.sqrt(sum(x * x for x in values))
            vectors.append([x / norm for x in values] if norm else None)
        for a in range(len(ids)):
            ma = metadata.get(ids[a], {})
            va = vectors[a]
            for b in range(a + 1, len(ids)):
                mb = metadata.get(ids[b], {})
                if (ma.get('wing'), ma.get('room')) != (mb.get('wing'), mb.get('room')):
                    continue
                vb = vectors[b]
                if va and vb:
                    distance = 1 - sum(x * y for x, y in zip(va, vb))
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
            'source_refs': [i for i, _ in rows],
            'metric_sources': {'knowledge': [i for i, _ in knowledge],
                               'noise': [i for i, _ in rows],
                               'superseded': [i for i, m in rows if m.get('superseded_by')]},
            'availability': 'available' if embeddings is not None else 'Embeddings unavailable'}
