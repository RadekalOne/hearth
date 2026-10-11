/* Dashboard first slice. Read-only projections; existing human actions remain intact. */
'use strict';
const stateName = s => ({'on-demand':'Event-driven',ok:'On schedule',queued:'Queued',claimed:'Claimed',running:'Running',review:'Review',blocked:'Blocked',done:'Done',proposed:'Proposed',failed:'Failed',stalled:'Stalled',late:'Late',unknown:'Unconfirmed'})[s] || s;
const stateTone = s => ['failed','stalled','blocked'].includes(s) ? 'bad' : s==='late' ? 'warn' : '';
const sliceResult = promise => promise.then(value=>({ok:true,value}), error=>{if(error instanceof AuthRequired)throw error;return {ok:false};});
function sliceHeading(view,title,note) {
  clear(view).append(h('div',{class:'slice-heading'},h('p',{class:'eyebrow',text:'Hearth / workspace'}),h('h1',{text:title}),h('p',{class:'takeaway',text:note})),h('p',{class:'load-status',role:'status',text:''}));
}
function loadFailure(view,results) {view.querySelector('.load-status').textContent=results.some(r=>!r.ok)?'Failed to load':'';}
function sourceLinks(refs,context={}) {
  return h('div',{class:'source-refs'},...(refs||[]).map(ref=> {
    const click=()=>inspectSliceSource(ref,context);
    return h('button',{class:'link mono',text:ref,onClick:click});
  }));
}
async function inspectSliceSource(ref,context) {
  if(ref.startsWith('drawer_'))return openDrawer(ref);
  if(ref.startsWith('checkpoint_')||ref.startsWith('watcher_'))return openWatcherReceipt(ref,context);
  if(ref.startsWith('$'))return openActivity(context.room_id||context.last_post_room_id,ref);
  try {
    if(ref.startsWith('task_')) {const board=await api('/api/work');const task=board.tasks.find(t=>t.id===ref);if(task)return openWorkTask(task,board);}
    if(ref.startsWith('relay_')) {const {panel}=inspectionPanel('Relay evidence');panel.lastChild.remove();panel.append(detailFields(['Relay',ref],['State',context.state],['Updated',context.state_since],['Source',context.source||'Unconfirmed']));return;}
    throw Error('Source unavailable');
  } catch(error) {if(error instanceof AuthRequired)return;const {panel}=inspectionPanel('Source evidence');panel.lastChild.textContent='Failed to load';}
}
function openWatcherReceipt(ref,w) {
  const {panel}=inspectionPanel('Watcher receipt');panel.lastChild.remove();
  const reason=w.state==='failed'?'The receipt reports an unsuccessful process exit or an unverified closeout.':
    w.state==='stalled'?'Receipt age exceeds 3× the expected cadence.':
    w.state==='late'?'Receipt age exceeds 1.5× the expected cadence.':
    w.state==='ok'?'Receipt age is within 1.5× the expected cadence.':
    w.state==='on-demand'?'Explicit event-driven evidence; no recurring cadence is expected.':'Cadence or receipt time is unconfirmed.';
  panel.append(h('span',{class:`pill ${stateTone(w.state)}`,text:stateName(w.state)}),h('p',{text:reason}),
    detailFields(['Selected evidence',ref],['Receipt source',w.receipt_source||ref],['Monitor',w.monitor||'Unconfirmed'],['Receipt time',when(w.checkpoint_at)||'Unconfirmed'],
      ['Receipt age',minutes(w.age_minutes)],['Expected cadence',w.expected_every_minutes?minutes(w.expected_every_minutes):'Unconfirmed / event-driven'],
      ['process_exit',String(w.receipt?.process_exit??'Unconfirmed')],['closeout_verified',String(w.receipt?.closeout_verified??'Unconfirmed')]),
    h('button',{class:'link',text:'Inspect separate surface activity',onClick:()=>openSurface(w)}));
  if(w.declaration_id)panel.append(h('h3',{text:'Watcher declaration'}),detailFields(['Registry id',w.declaration_id],['Kind',w.kind],['Active',String(w.active)],['Source',w.declaration_source]));
  if(w.evidence?.length) {
    panel.append(h('h3',{text:'Parent and runner evidence'}),h('p',{class:'dim',text:'The latest runner result determines the merged status; newer parent or chat activity does not clear a failed runner.'}));
    for(const entry of w.evidence)panel.append(h('article',{class:'evidence-card'},detailFields(['Checkpoint',entry.id],['Monitor',entry.monitor],['Updated',when(entry.at)],['process_exit',String(entry.receipt.process_exit??'Unconfirmed')],['closeout_verified',String(entry.receipt.closeout_verified??'Unconfirmed')])));
  }
}
function durableAttentionRow(item) {
  const inspect=()=>inspectSliceSource(item.source_refs[0],item);
  const failed=item.kind==='failed_watcher';
  return h('div',{class:`inbox-item ${item.kind}`},
    h('div',{class:'kind'},failed?'Failed watcher':'Overdue queue',h('small',{text:item.label})),
    h('div',null,h('div',{class:'who',text:failed?`${item.agent} @ ${item.surface}`:item.owner||'Unassigned'}),
      h('button',{class:'link inspect-link body',text:item.title||item.body,onClick:inspect})),
    h('div',{class:'meta'},`${failed?'receipt':'queued'} ${minutes(item.age_minutes)}`,h('br'),h('button',{class:'link',text:'View details',onClick:inspect})));
}
function watcherRow(w) {
  return h('div',{class:'watcher-row'},h('div',null,h('strong',{text:w.agent}),h('span',{class:'dim',text:` / ${w.surface}`}),h('p',{text:w.monitor||'Observed activity'})),
    h('span',{class:`pill ${stateTone(w.state)}`,text:stateName(w.state)}),
    h('span',{class:'watcher-age',text:w.state==='on-demand'?'Event-driven':`${minutes(w.age_minutes)} since receipt`}),sourceLinks(w.source_refs,w));
}
async function renderNow(view) {
  sliceHeading(view,'Now','Checking what needs your attention.');
  const waiting=section('Waiting on you','Failures first, then oldest. Every item links to its evidence.',null,h('div',{class:'reserved-body'}));
  const awake=section('Who is awake','Active declared monitors only. Runner results fold into their parent; probes and one-shot records are excluded.',null,h('div',{class:'reserved-body'}));
  view.append(waiting,awake);
  const [inbox,surfaces]=await Promise.all([sliceResult(api('/api/inbox')),sliceResult(api('/api/surfaces'))]);
  loadFailure(view,[inbox,surfaces]);
  const watchers=surfaces.ok?(surfaces.value.watchers||surfaces.value.surfaces||[]):[];
  const attention=watchers.filter(w=>['failed','stalled','late'].includes(w.state)).sort((a,b)=>({failed:0,stalled:1,late:2}[a.state])-({failed:0,stalled:1,late:2}[b.state])||(b.age_minutes||0)-(a.age_minutes||0));
  const totals=Object.fromEntries(['failed','stalled','late'].map(s=>[s,attention.filter(w=>w.state===s).length]));
  view.querySelector('.takeaway').textContent=inbox.ok&&surfaces.ok?`${plural(inbox.value.open_total??inbox.value.total,'item')} waiting${inbox.value.acknowledged_total?` · ${inbox.value.acknowledged_total} acknowledged`:''} · ${plural(totals.failed,'failed watcher')} · ${plural(totals.stalled,'stalled watcher')} · ${plural(totals.late,'late watcher')}.`:'Some attention data is unavailable.';
  const inboxBody=clear(waiting.querySelector('.reserved-body'));
  if(inbox.ok) {
    if(inbox.value.element_url)elementBase=inbox.value.element_url;
    const row=item=>{
      const card=['failed_watcher','overdue_work'].includes(item.kind)?durableAttentionRow(item):inboxRow(item);
      const evidence=sourceLinks(item.source_refs||[item.event_id],item);evidence.prepend(h('span',{class:'dim',text:'Evidence ids:'}));
      const result=h('div',{class:'inbox-with-source'},card,evidence);
      if(inbox.value.can_acknowledge) {
        const button=h('button',{class:'small secondary',text:item.acknowledged?'Reopen':'Acknowledge',onClick:async()=>{
          button.disabled=true;
          try {
            await api('/api/inbox/acknowledgement',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({kind:item.kind,item_id:item.id||item.event_id,state_key:item.state_key,acknowledged:!item.acknowledged})});
            clear(view);await renderNow(view);
          }catch(error){button.disabled=false;view.querySelector('.load-status').textContent=error.status===409?'This item changed. Refresh before acknowledging or reopening it.':'Could not update the item. Refresh and try again.';}
        }});
        let actions=card.querySelector('.actions');
        if(!actions){actions=h('div',{class:'actions'});card.append(h('div',{class:'actions-row'},actions));}
        const details=card.querySelector('.meta button');
        if(details){details.className='small secondary';actions.prepend(details);}
        actions.append(button);
        if(item.acknowledged)card.append(h('p',{class:'acknowledgement-meta dim',text:`Acknowledged by ${item.acknowledged_by||'you'} · ${when(item.acknowledged_at)||'Time unavailable'}`}));
      }
      return result;
    };
    const open=inbox.value.items.filter(i=>!i.acknowledged),acknowledged=inbox.value.items.filter(i=>i.acknowledged);
    if(!open.length)inboxBody.append(h('p',{class:'empty',text:'Nothing is waiting on you right now.'}));
    inboxBody.append(...open.map(row));
    if(acknowledged.length)inboxBody.append(h('details',{class:'acknowledged-items'},h('summary',{text:`Acknowledged (${acknowledged.length})`}),...acknowledged.map(row)));
  }
  const watcherBody=clear(awake.querySelector('.reserved-body'));
  if(surfaces.ok) {
    watcherBody.append(...attention.map(watcherRow));
    if(!attention.length)watcherBody.append(h('p',{class:'empty',text:'No watchers need attention.'}));
    const ordinary=watchers.filter(w=>w.state==='ok');
    const other=watchers.filter(w=>['on-demand','unknown'].includes(w.state));
    if(ordinary.length)watcherBody.append(h('details',null,h('summary',{text:`${ordinary.length} on schedule`}),...ordinary.map(watcherRow)));
    if(other.length)watcherBody.append(h('details',null,h('summary',{text:'Event-driven and unconfirmed'}),...other.map(watcherRow)));
  }
}
async function renderWorkSlice(view) {
  sliceHeading(view,'Work','Checking the work lifecycle.');
  const card=section('Work lifecycle','Queued work has not started. The current work store records claims; execution is unverified.',null,h('div',{class:'reserved-body'}));
  view.append(card,h('a',{class:'utility-link',href:'#projects',text:'Open project workspace'}));
  const result=await sliceResult(api('/api/dashboard/work'));loadFailure(view,[result]);
  if(!result.ok)return;
  const items=result.value.items;
  const open=items.filter(i=>i.state!=='done'),done=items.filter(i=>i.state==='done');
  view.querySelector('.takeaway').textContent=`${plural(open.length,'open item')} · ${plural(done.length,'done item')}.`;
  const body=clear(card.querySelector('.reserved-body'));
  const stages=['queued','claimed','running','review','blocked','done'];
  for(const stage of Object.keys(result.value.counts||{}))if(!stages.includes(stage))stages.push(stage);
  const counts=h('div',{class:'stage-counts','aria-label':'Lifecycle stage counts'});
  for(const stage of stages) {
    const count=result.value.counts?.[stage]??items.filter(i=>i.state===stage).length;
    counts.append(h('button',{class:'stage-count','aria-label':`${stateName(stage)}: ${count}`,onClick:()=>{
      const {panel}=inspectionPanel(stateName(stage)+' sources');panel.lastChild.remove();
      const sources=items.filter(i=>i.state===stage);if(!sources.length)panel.append(h('p',{text:'No items in this stage.'}));
      for(const item of sources)panel.append(h('p',{text:item.title}),sourceLinks(item.source_refs,item));
    }},h('span',{text:stateName(stage)}),h('strong',{text:count.toLocaleString()})));
  }
  body.append(counts);
  const workTable=rows=>table([
    {label:'Item',cell:i=>h('div',null,h('strong',{text:i.title}),sourceLinks(i.source_refs,i))},
    {label:'State',cell:i=>h('span',{class:`pill ${stateTone(i.state)}`,text:stateName(i.state)})},
    {label:'Age',cell:i=>h('span',{title:i.age_basis,text:minutes(i.age_minutes)})},
    {label:'Owner',cell:i=>i.owner||'Unassigned'},
    {label:'Since',cell:i=>when(i.state_since)||'Unconfirmed'},
  ],rows);
  if(open.length)body.append(workTable(open));
  else body.append(h('p',{class:'empty',text:items.length?'No open work is recorded.':'No work is recorded.'}));
  if(done.length)body.append(h('details',{class:'completed-work'},h('summary',{text:plural(done.length,'done item')}),workTable(done)));
}
async function renderMemorySlice(view) {
  sliceHeading(view,'Memory','Knowledge only by default.');
  const card=section('Memory health','Knowledge only. Noise is diary, import and archive records as a share of all drawers.',null,h('div',{class:'reserved-body health-grid'}));
  view.append(card);
  const health=await sliceResult(api('/api/dashboard/memory-health'));loadFailure(view,[health]);
  if(health.ok) {
    const data=health.value;
    view.querySelector('.takeaway').textContent=`${plural(data.knowledge_count,'knowledge drawer')} · ${(100*data.noise_ratio).toFixed(1)}% noise · ${plural(data.superseded_count,'superseded record')}.`;
    const metrics=[['Knowledge only',data.knowledge_count,'knowledge'],['Noise ratio',`${(100*data.noise_ratio).toFixed(1)}%`,'noise'],['Superseded',data.superseded_count,'superseded'],['Near-duplicate pairs',data.near_duplicate_pair_count??'Unavailable','pairs']];
    const grid=clear(card.querySelector('.reserved-body'));
    for(const [label,value,key] of metrics)grid.append(h('div',{class:'health-metric'},h('p',{class:'dim',text:label}),h('strong',{text:typeof value==='number'?value.toLocaleString():value}),h('button',{class:'link',text:'View source drawers',onClick:()=>{
      const {panel}=inspectionPanel(label+' sources');panel.lastChild.remove();
      panel.append(h('p',{text:key==='noise'?'Noise is nonknowledge drawers divided by all drawers; these are the denominator records.':'Counts derived from these source records.'}));
      if(key==='pairs') {
        panel.append(h('p',{text:data.near_duplicate_pair_count===null?'Embeddings unavailable.':`${plural(data.near_duplicate_pairs.length,'pair')} found in ${plural(data.duplicate_coverage.scanned,'scanned knowledge drawer')}.`}));
        for(const pair of data.near_duplicate_pairs)panel.append(h('article',{class:'evidence-card'},sourceLinks(pair)));
      } else panel.append(sourceLinks(data.metric_sources?.[key]||[]));
    }})));
    card.append(h('p',{class:'coverage',text:data.duplicate_coverage.complete?'Duplicate scan covers all knowledge drawers.':`Duplicate scan covers ${data.duplicate_coverage.scanned} of ${data.duplicate_coverage.total} knowledge drawers; the pair count is a lower bound.`}));
  }
  const browser=h('div',{class:'memory-browser'});view.append(browser);
  try {await renderMemory(browser);}catch(error){if(error instanceof AuthRequired)throw error;view.querySelector('.load-status').textContent='Failed to load';}
}
VIEWS.now=renderNow;VIEWS.overview=renderNow;VIEWS.work=renderWorkSlice;VIEWS.memory=renderMemorySlice;
const sliceTabs=[...document.querySelectorAll('#tabs a')];
for(const tab of sliceTabs) {
  tab.setAttribute('role','tab');tab.setAttribute('aria-controls','view');
  tab.addEventListener('keydown',event=>{
    const idx=sliceTabs.indexOf(tab);let next;
    if(event.key==='ArrowRight')next=(idx+1)%sliceTabs.length;
    if(event.key==='ArrowLeft')next=(idx+sliceTabs.length-1)%sliceTabs.length;
    if(event.key==='Home')next=0;if(event.key==='End')next=sliceTabs.length-1;
    if(next!==undefined){event.preventDefault();sliceTabs[next].focus();}
  });
}
function updateSliceTabs() {for(const tab of sliceTabs){const selected=tab.dataset.route===currentRoute()||(tab.dataset.route==='now'&&currentRoute()==='overview');tab.setAttribute('aria-selected',String(selected));tab.setAttribute('tabindex',selected?'0':'-1');tab.classList.toggle('active',selected);}}
window.addEventListener('hashchange',updateSliceTabs);updateSliceTabs();
