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
        error = re.search(r'(?:^|\n)\s*error\s*[:=]\s*([^\n]*)', str(content), re.I)
        if error:
            fields['error'] = error[1]
    safe = {}
    if type(fields.get('process_exit')) is int:
        safe['process_exit'] = fields['process_exit']
    elif isinstance(fields.get('process_exit'), str) and re.fullmatch(r'-?\d{1,8}', fields['process_exit']):
        safe['process_exit'] = int(fields['process_exit'])
    if type(fields.get('closeout_verified')) is bool:
        safe['closeout_verified'] = fields['closeout_verified']
    # Classify current failures only; recovery notes are not error evidence.
    failed = safe.get('closeout_verified') is False or safe.get('process_exit') not in (None, 0)
    error = fields.get('error')
    if failed and (fields.get('reason') == 'auth_expired' or (isinstance(error, str) and re.search(
            r'(?:oauth|authentication|auth|login|sign.in)\s+(?:session\s+)?(?:expired|expiration)|token (?:has )?expired',
            error, re.I))):
        safe['reason'] = 'auth_expired'
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


def default_human_action(item):
    kind = item.get('kind')
    agent = item.get('agent') or item.get('owner') or item.get('sender') or 'the assigned agent'
    ask = f'Ask {agent} in the task thread if anything is unclear.'
    if kind == 'auth_expired':
        machine = 'desktop PC' if 'desktop' in item.get('surface','') else 'laptop' if 'laptop' in item.get('surface','') else 'listed machine'
        command = 'claude' if agent == 'claude' else 'codex login' if agent == 'codex' else f'{agent} sign-in command'
        return {'steps':[f'On the {machine}, open PowerShell and run: {command}.',
                         'For Claude, type /login. Complete sign-in in the browser, then type /exit.' if agent=='claude' else 'Complete sign-in in the browser and return to PowerShell.',
                         f'Open Task Scheduler on the {machine}, select the existing {agent} sweep or heartbeat task, and click Run once.'],
                'after':'The next successful runner receipt clears this sign-in item. Other work can wait until then.', 'ask':ask}
    if kind in {'overdue_work','unclaimed_task','claim_expired','dispatch_required'}:
        steps = ['Open Codex on the laptop and paste: drain your inbox.'] if agent=='codex' else ['Open Claude Cowork and paste: drain your inbox.'] if agent=='claude' else [f'Open an interactive session for {agent} and ask it to drain its Hearth inbox.']
        return {'steps':steps, 'after':f'{agent} will check the queued work and report what it can pick up. Dispatching does not approve a merge or deployment.', 'ask':ask}
    steps = {'approval':['Open the linked task and read the plan.', 'Reply in that thread with Approve or Request changes, and say what you want changed.'],
             'question':['Open the linked thread and read the question.', 'Reply there with your answer, or ask the agent to explain the choices.'],
             'blocked':['Open the linked thread and read what is missing.', 'Ask the agent for the exact click or command it needs before changing anything.'],
             'failed_watcher':['Click View details to inspect the latest runner receipt.', f'Ask {agent} to diagnose the failure and give you the exact recovery steps.'],
             'failed_continuation':['Click View details to inspect the failed handoff.', f'Ask {agent} to reconcile the conflicting handoff and retry it.']}.get(kind,['Open the linked task and ask the agent for the next step.'])
    return {'steps':steps, 'after':'The agent will respond in the thread. This can wait unless the task states a deadline.', 'ask':ask}


def attention_inbox(inbox, monitors, work, failures=None):
    items = list(inbox.get('items', []))
    for watcher in monitors:
        if watcher['state'] == 'failed':
            if watcher.get('receipt',{}).get('reason') == 'auth_expired':
                existing = next((i for i in items if i['kind']=='auth_expired' and
                                 (i['agent'],i['surface'].split(' (')[0])==(watcher['agent'],watcher['surface'].split(' (')[0])), None)
                if existing:
                    existing['source_refs'] = sorted(set(existing['source_refs'] + watcher['source_refs']))
                    existing['auth_receipts'].append(f"{watcher.get('receipt_source') or watcher['id']}|{watcher.get('checkpoint_at')}")
                    continue
                items.append({**watcher, 'id':f"auth_{watcher['agent']}_{watcher['surface'].split(' (')[0]}", 'kind':'auth_expired',
                              'auth_receipts':[f"{watcher.get('receipt_source') or watcher['id']}|{watcher.get('checkpoint_at')}"],
                              'title':f"Sign {watcher['agent']} back in on {watcher['surface'].split(' (')[0]}",
                              'label':'Sign-in expired', 'body':'The runner needs a fresh sign-in.'})
                continue
            items.append({**watcher, 'kind': 'failed_watcher', 'label': 'Failed watcher needs attention',
                          'title': f"{watcher['agent']} / {watcher['monitor']}",
                          'body': 'The latest runner receipt reports a failure or unverified closeout.'})
    for item in work:
        age = item.get('age_minutes')
        if item.get('state') == 'claim_expired':
            items.append({**item,'kind':'claim_expired','label':f"Claim expired, last state {item['last_state']}",
                          'body':item.get('title',item['id'])})
        if item['state'] == 'queued' and age is not None and age > 3 * 24 * 60:
            items.append({**item, 'kind': 'overdue_work', 'label': 'Queued for more than 3 days',
                          'body': item.get('title', item['id'])})
    for failure in failures or []:
        items.append({**failure,'kind':'failed_continuation','id':failure['delivery_id'],
                      'title':'Failed handoff to '+failure['target_agent'],'owner':failure['target_agent'],
                      'state':'failed','label':'Handoff needs recovery','body':failure.get('failure_reason','Delivery failed'),
                      'source_refs':[failure['delivery_id'],failure['thread_id']]})
    for item in items:
        item.setdefault('human_action', default_human_action(item))
    items.sort(key=lambda i: (0 if i['kind'] in {'failed_watcher','auth_expired','failed_continuation'} else 1 if i['kind'] in {'blocked','claim_expired'} else 2,
                              -(i.get('age_minutes') or 0), i.get('id') or i.get('event_id', '')))
    counts = {}
    for item in items:
        counts[item['kind']] = counts.get(item['kind'], 0) + 1
    return {**inbox, 'items': items, 'total': len(items), 'counts': counts, 'queued_threshold_days': 3}


def coordination_items(parties, now):
    items=[]
    for value in parties:
        key=[value[k] for k in ('work_kind','work_id','room_id','thread_id','kind','id')]
        import hashlib
        item={**value,'kind':'coordination_wait','id':'wait_'+hashlib.sha256(json.dumps(key).encode()).hexdigest()[:32],
              'party_kind':value['kind'],'party_id':value['id'],'state':'pending','revision':value['generation'],
              'title':f"Response needed for {value['work_id']}",'label':'Waiting for a response',
              'body':'An explicit responsibility handoff is waiting for its addressed party.',
              'source_refs':[value['source_event'],value['thread_id'],value['work_id']],
              'owner':value['id'],'event_id':value['source_event']}
        ts=timestamp(value['since']);item['age_minutes']=round(max(0,now-ts)/60,1) if ts is not None else None
        if value['kind']=='human':item.setdefault('human_action',default_human_action(item))
        items.append(item)
    return items


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
        items.append({'id': task['id'], 'revision':task.get('revision',0), 'title': task.get('title', task['id']),
                      'state': {'ready': 'queued', 'draft': 'proposed', 'running': 'claimed'}.get(state, state),
                      'source_state': state, 'execution_verified': False,
                      'owner': task.get('assignee', ''), 'state_since': since,
                      'age_minutes': round((now - ts) / 60, 1) if ts is not None and ts <= now else None,
                      'age_basis': 'transition' if task.get('state_since') or events else 'last update; transition unavailable',
                      'project_id': task.get('project_id'), 'source_refs': [task['id']]})
        if task.get('claim_expired'):
            items[-1].update(state='claim_expired',last_state=state,claim_until=task.get('claim_until'))
    for relay in relays:
        ts = timestamp(relay.get('updated_at'))
        summary = ' '.join(str(relay.get('request') or '').split())[:120]
        title = summary or f"Handoff to {relay.get('target_agent') or 'unassigned'} · {relay['relay_id']}"
        items.append({'id': relay['relay_id'], 'revision':relay.get('transition_generation',0), 'title': title,
                      'state': 'done' if relay.get('state') == 'resolved' else relay.get('state', 'unknown'),
                      'owner': relay.get('target_agent', ''), 'state_since': relay.get('updated_at'),
                      'age_minutes': round((now - ts) / 60, 1) if ts is not None and ts <= now else None,
                      'age_basis': 'relay state update', 'source_refs': [relay['relay_id']],
                      'source': relay.get('source', ''),'required_surface':relay.get('required_surface','interactive')})
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
