"""Script-free human status page. Stored evidence is text, never active markup."""
from html import escape


STYLE='''
:root{color-scheme:light;font-family:system-ui,sans-serif;background:#f4f5f7;color:#172234}
*{box-sizing:border-box}body{margin:0}main{max-width:1080px;margin:auto;padding:40px 24px 64px}
header{border-bottom:1px solid #d2d8df;padding-bottom:24px;margin-bottom:28px}
h1{font-size:2rem;margin:8px 0}h2{font-size:1.25rem;margin:0 0 16px}h3{font-size:1rem;margin:0 0 12px}
p{line-height:1.55;margin:8px 0}.eyebrow{font-size:.8rem;letter-spacing:.1em;text-transform:uppercase;color:#52637a}
.muted{color:#52637a;font-size:.9rem}.refresh{display:inline-block;margin-top:12px;color:#174d8e;text-underline-offset:3px}
section{margin-top:32px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,300px),1fr));gap:16px}
article{background:#fff;border:1px solid #d2d8df;border-radius:12px;padding:20px;min-width:0}
.badge{display:inline-block;font-size:.85rem;font-weight:650;border-radius:6px;padding:5px 9px;background:#e9edf2;color:#31445b;margin:0 4px 8px 0}
.recent{background:#e4f2e9;color:#215d38}.stale,.open{background:#fff0d9;color:#784400}.unknown{background:#e9edf2;color:#31445b}
.notice{border-left:4px solid #7796bf}.failure{border-left:4px solid #af7527}
details{border-top:1px solid #e1e5ea;margin-top:18px;padding-top:12px}summary{cursor:pointer;color:#174d8e;font-weight:600}
summary:focus-visible,a:focus-visible{outline:3px solid #366cc2;outline-offset:4px}
dl{margin:14px 0 0;font-size:.85rem}dt{color:#52637a;margin-top:10px}dd{margin:3px 0;overflow-wrap:anywhere}
ul{padding-left:20px}li{line-height:1.5;overflow-wrap:anywhere}code,time{overflow-wrap:anywhere}
.empty{padding:20px;background:#fff;border:1px dashed #b3bfcc;border-radius:8px}
footer{margin-top:36px;border-top:1px solid #d2d8df;padding-top:16px}
@media(max-width:520px){main{padding:24px 16px 40px}h1{font-size:1.7rem}article{padding:16px}}
'''

_REASONS={
    'no_completed_poll':'No completed poll recorded in this restore period.',
    'timing_not_configured':'Timing expectation not configured; freshness is unknown.',
    'poll_time_in_future':'Poll timestamp is in the future; check the clock evidence.',
    'poll_time_unusable':'Poll timestamp cannot be assessed.',
    'poll_overdue':'Last completed poll is older than its cadence plus grace.',
    'within_expected_window':'A completed poll was recorded within its expected window.',
}
_TASKS={'ready':'Ready','running':'Running (claim recorded)','review':'Awaiting independent review','reviewed':'Awaiting human acceptance',
    'accepted':'Accepted','needs_decision':'Needs a decision','held':'Held for reconciliation','revision_required':'Changes requested'}


def _e(value):return escape(str(value),quote=True)


def _details(fields,references):
    pairs=''.join('<dt>'+_e(k)+'</dt><dd>'+_e(v if v is not None else 'Not recorded')+'</dd>' for k,v in fields)
    refs='<h4>Reporter-supplied references (unverified)</h4><ul>'+''.join('<li>'+_e(v)+'</li>' for v in references)+'</ul>' if references else '<p>No reporter-supplied references recorded.</p>'
    return '<details><summary>Inspect record &amp; supplied references</summary><h4>Recorded fields</h4><dl>'+pairs+'</dl>'+refs+'</details>'


def render_status(value):
    polls=[]
    for row in value['controllers']:
        state=row['poll_state'];label={'recent':'Poll recent','stale':'Poll overdue','unknown':'Poll status unknown'}[state]
        timing=('Every '+str(row['cadence_seconds'])+'s + '+str(row['grace_seconds'])+'s grace') if row['cadence_seconds'] is not None else 'No timing expectation configured'
        fields=(('Last completed poll',row['last_completed_at']),('Assessed at',value['observed_at']),
            ('Expected timing',timing),('Age in seconds',row['age_seconds']),('Poll request',row['request_id']),
            ('Journal sequence',row['sequence']),('Restore period',row['restore_epoch']))
        polls.append('<article><h3>'+_e(row['controller'])+'</h3><span class="badge '+state+'">'+label+'</span><p>'
            +_e(_REASONS[row['reason']])+'</p><p class="muted">'+_e(timing)+'</p>'+_details(fields,row['supplied_references'])+'</article>')
    tasks=[]
    names={t['id']:t['ask'] for t in value['tasks']}
    for row in value['tasks']:
        lease=''
        if row['state']=='running':
            lease='<p class="muted">Worker liveness is unverified.</p><p>'+{
                'current':'Claim lease current','expired':'Claim lease expired','unknown':'Claim lease unknown'}[row['lease_state']]+'</p>'
            if row['claim_lease_until'] is not None:lease+='<p>Lease expiry: <time>'+_e(row['claim_lease_until'])+'</time></p>'
        tasks.append('<article><h3>'+_e(row['ask'])+'</h3><span class="badge">'+_e(_TASKS.get(row['state'],row['state']))
            +'</span><p>Assigned to '+_e(row['assignee'])+'</p><p class="muted">Done when: '+_e(row['done_means'])+'</p>'
            +lease+_details((('Task record',row['id']),('Record revision',row['revision']),('Persisted state',row['state'])),[])+'</article>')
    notices=[]
    for row in value['notices']:
        received=row['delivery_state']=='received'
        delivery='<span class="badge unknown">Receipt recorded</span>' if received else '<span class="badge unknown">Delivery unconfirmed</span>'
        qualification=('Received by the intended named session. Understanding remains unknown. A receipt does not complete the task.'
            if received else 'Stored here. Receipt by the intended session has not been confirmed.')
        fields=(('Notice record',row['id']),('Task record',row['task_id']),('Recorded by',row['sender']),
            ('Recording time',row['recorded_at']),('Intended session',row.get('intended_session')),
            ('Acknowledgement','Receipt recorded' if received else 'Unknown'),('Understanding','Unknown'),
            ('Receipt principal',row.get('receipt_actor')),('Receipt recorded at',row.get('acknowledged_at')),
            ('Receipt journal sequence',row.get('acknowledgement_sequence')),('Delivery identity',row.get('delivery_id')),
            ('Notice content digest',row.get('notice_digest')),('Receipt restore period',row.get('receipt_restore_epoch')))
        historical='<p class="muted">Receipt retained from a previous restore period; no fresh delivery is inferred.</p>' if row.get('receipt_historical') else ''
        notices.append('<article class="notice"><h3>'+_e(names.get(row['task_id'],'Task notice'))+'</h3>'
            '<span class="badge">Recorded</span>'+delivery
            +'<p>'+_e(row['kind'].replace('_',' '))+' · To '+_e(row['recipient'])+'</p>'
            +'<p class="muted">'+qualification+'</p>'+historical+_details(fields,row['supplied_references'])+'</article>')
    failures=[]
    for row in value['failures']:
        period='Historical · previous restore period' if row['historical'] else 'Current restore period'
        recovery='Recovery reported' if row['state']=='recovered' else 'Open'
        attribution='<span class="badge unknown">Self-reported</span>' if row['self_reported'] else ''
        failures.append('<article class="failure"><h3>'+_e(row['kind'].replace('_',' '))+' · '+_e(row['target'])+'</h3>'
            '<span class="badge '+('open' if row['state']=='open' else 'unknown')+'">'+recovery+'</span>'+attribution
            +'<p class="muted">'+period+'</p><p>Recovery reports are not independent health verification.</p>'
            +_details((('Reported at',row['at']),('Reported by',row['actor']),
                ('Incident key',row['key']),('Journal sequence',row['sequence']),('Restore period',row['restore_epoch'])),row['supplied_references'])+'</article>')
    observers=[]
    for event in value.get('observers',[]):
        historical=event['restore_epoch']!=value['restore_epoch']
        for row in event['observations']:
            state=row['incident_state']
            label=('Overdue incident open' if state=='open' else
                'Polling resumed' if state=='recovered' and row['poll_state']=='recent' else
                'Prior polling resumption' if state=='recovered' else 'No overdue incident recorded')
            badge='open' if state=='open' else 'unknown'
            fields=(('Observer identity',event['actor']),('Last observer check',event['at']),
                ('Assessed at',event['assessed_at']),('Observer journal sequence',event['seq']),
                ('Observer request',event['request_id']),('Restore period',event['restore_epoch']),
                ('Last completed poll',row['last_completed_at']),('Assessed poll sequence',row['sequence']),
                ('Age at check in seconds',row['age_seconds']),('Cadence in seconds',row['cadence_seconds']),
                ('Grace in seconds',row['grace_seconds']),('Stale incident poll sequence',row['stale_tick_sequence']),
                ('Recovery poll sequence',row['recovery_tick_sequence']))
            observers.append('<article><h3>'+_e(row['controller'])+' · '+_e(event['actor'])+'</h3>'
                +'<span class="badge '+badge+'">'+label+'</span>'
                +('<p>Historical · previous restore period</p>' if historical else '')
                +'<p>'+_e(_REASONS[row['reason']])+'</p><p>Server journal assessment of polling, not worker health verification.</p>'
                +_details(fields,[])+'</article>')
    def section(title,cards,empty,description=''):
        return '<section><h2>'+title+'</h2>'+('<p class="muted">'+description+'</p>' if description else '')+(
            '<div class="grid">'+''.join(cards)+'</div>' if cards else '<p class="empty">'+empty+'</p>')+'</section>'
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>Hearth · Work status</title><link rel="stylesheet" href="/api/hearth2/status/style.css"></head><body><main>'
        '<header><div class="eyebrow">Hearth · Work record</div><h1>Work status</h1><p>'+_e(value['project_title'] or 'All projects')+'</p>'
        '<p class="muted">Assessed at <time>'+_e(value['observed_at'])+'</time>. Refresh to reassess.</p><a class="refresh" href="">Refresh status</a></header>'
        +section('Assigned work',tasks,'No tasks in this view.')
        +section('Notices & delivery',notices,'No notices recorded. Delivery has not been established.')
        +section('Controller polling',polls,'No controllers configured. Poll status is unknown.','Instance-wide, including when a project is selected. A recent poll does not prove work succeeded or a notice arrived.')
        +section('Independent poll observations',observers,'No observer checks recorded. Independent polling assessment is unknown.','Stored checks are separate from controller claims. A new poll needs a new observer check to record resumption. Check times do not prove an observer process is still running.')
        +section('Reported failures',failures,'No failure reports recorded. This does not prove every component is healthy.','Open reports change only after an explicit recovery report; a new poll does not close them.')
        +'<footer class="muted">Read-only snapshot. No delivery acknowledgement or independent outage detector runs from this page.</footer></main></body></html>')
