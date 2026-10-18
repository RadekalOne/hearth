/* Trusted identity and persistence come from Hearth; retrieved prose is inert text. */
(() => {
 'use strict';
 const $=id=>document.getElementById(id);
 let canCreate=false,principal='',active=null,cursor=null,mode='predictions',target=null,busy=false,pendingIntent=null;
 const fields={title:'entry-title',decision:'decision',reasoning:'reasoning',prediction:'prediction',falsifier:'falsifier',confidence:'confidence',check_date:'check-date',tradeoffs:'tradeoffs',observed_result:'observed-result',comparison:'comparison',verdict:'verdict',cause_unknown:'cause-unknown',cause:'cause'};
 const titleFor={predictions:'prediction',outcomes:'outcome'};
 const status=text=>{$('status').textContent=text;};
 function element(tag,text,className){const node=document.createElement(tag);node.textContent=text;if(className)node.className=className;return node;}
 async function api(path,body){
  const response=await fetch('/api/commons/journal'+path,{credentials:'same-origin',...(body?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}:{})});
  let value;try{value=await response.json();}catch{throw Error('Hearth returned an unreadable response.');}
  if(!response.ok)throw Error(response.status===401?'Sign in through Hearth to read this journal.':response.status===403?'Shared journal access is not enabled for this account yet.':value.detail||value.error||'Journal request failed.');
  return value;
 }
 async function list(append=false){
  const page=await api(cursor&&append?'?cursor='+encodeURIComponent(cursor):'');
  canCreate=page.can_create===true;$('new-entry').disabled=!canCreate;
  if(!append)$('entries').replaceChildren();
  for(const item of page.entries){
   const button=element('button',item.title,'entry-card');button.type='button';
   button.append(element('small',`${item.record_type} · ${item.author}`));
   button.onclick=()=>!busy&&show(item.entry_id).catch(error=>status(error.message));$('entries').append(button);
  }
  if(!$('entries').children.length)$('entries').append(element('p','No journal records yet.','dim'));
  cursor=page.next_cursor;$('more').hidden=!cursor;
  if(page.unstructured_entries)status('Older unstructured records remain in Commons; they are not presented as typed journal records.');
 }
 async function show(id){
  if(!/^entry_[a-f0-9]{32}$/.test(id))throw Error('Invalid journal entry link.');
  const entry=await api('/entries/'+id);active=entry;
  history.replaceState(null,'','#'+entry.entry_id);
  $('editor').hidden=true;$('welcome').hidden=true;$('record').hidden=false;
  const record=$('record');record.replaceChildren();const data=entry.data;
  record.append(element('div',data.record_type,'eyebrow'),element('h2',data.title||(data.record_type==='correction'?'Author self-correction':'A later outcome')));
  record.append(element('p',`${entry.author} · ${new Date(entry.created_at).toLocaleString()}\n${entry.entry_id}`,'record-meta'));
  const labels=data.record_type==='correction'?{status:'Self-correction status',explanation:'Author explanation'}:data.record_type==='outcome'?{observed_result:'Observed result',comparison:'Comparison with prediction',verdict:'Verdict',cause_unknown:'Cause unknown',cause:'Evidenced cause'}:{decision:'Decision',reasoning:'Reasoning',prediction:'Prediction',falsifier:'Falsifier',confidence:'Confidence',check_date:'Check date (no automatic reminder)',tradeoffs:'Tradeoffs'};
  for(const [field,label]of Object.entries(labels))record.append(element('h3',label),element('p',typeof data[field]==='boolean'?(data[field]?'Yes':'No'):data[field]||'Not recorded','prose'));
  record.append(element('h3','Sources'));const sources=document.createElement('ul');sources.className='sources';
  for(const source of entry.source_refs)sources.append(element('li',source));record.append(sources);
  const actions=document.createElement('div');actions.className='record-actions';
  if(entry.links.length){const parent=element('button','Open original prediction','secondary');parent.type='button';parent.onclick=()=>!busy&&show(entry.links[0]).catch(error=>status(error.message));actions.append(parent);}
  if(canCreate&&data.record_type==='prediction'){
   if(entry.author.replace(/^@/,'').split(':')[0]===principal.replace(/^@/,'').split(':')[0])record.append(element('p','A different participant must record the outcome.','dim'));
   else{const button=element('button','Record later outcome','secondary');button.type='button';button.onclick=()=>edit('outcomes',entry);actions.append(button);}
  }
  if(data.record_type==='correction')record.append(element('p','This is the author’s self-correction. A separately authored outcome remains a separate record.','dim'));
  record.append(actions);
 }
 function edit(kind,entry=null){
  if(!canCreate||busy)return;mode=kind;target=entry?.entry_id||null;
  $('editor').reset();$('editor').hidden=false;$('record').hidden=true;$('welcome').hidden=true;
  $('form-title').textContent=(kind==='predictions'?'New ':'Record an ')+titleFor[kind];
  $('save').textContent='Save '+titleFor[kind];
  const application=kind==='outcomes';
  $('application-fields').hidden=!application;$('application-fields').disabled=!application;
  $('distinction-fields').hidden=application;$('distinction-fields').disabled=application;
  $('check-date').value=new Date().toISOString().slice(0,10);
  $('cause').disabled=true;$('cause-unknown').checked=true;
  status('');$(application?'observed-result':'entry-title').focus();
 }
 async function requestId(payload){
  const bytes=new TextEncoder().encode(JSON.stringify([mode,payload]));
  const digest=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)),b=>b.toString(16).padStart(2,'0')).join('');
  const key='hearth-journal-intent:'+principal;
  if(pendingIntent?.principal===principal&&pendingIntent.digest===digest)return pendingIntent.id;
  let pending;try{pending=JSON.parse(sessionStorage.getItem(key));}catch{}
  const id=pending?.digest===digest&&typeof pending.id==='string'?pending.id:'journal-'+crypto.randomUUID();
  pendingIntent={principal,digest,id};
  try{sessionStorage.setItem(key,JSON.stringify({digest,id}));}catch{}
  return id;
 }
 $('editor').onsubmit=async event=>{
  event.preventDefault();if(busy||!canCreate)return;busy=true;$('save').disabled=true;status('Saving…');
  let confirmed=null;
  const payload={source_refs:$('sources').value.split(/\r?\n/).map(s=>s.trim()).filter(Boolean)};
  for(const name of mode==='outcomes'?['observed_result','comparison','verdict','cause_unknown','cause']:['title','decision','reasoning','prediction','falsifier','confidence','check_date','tradeoffs'])payload[name]=name==='cause_unknown'?$('cause-unknown').checked:$(fields[name]).value;
  if(target)payload.entry_id=target;
  if(mode==='outcomes'&&payload.cause_unknown)payload.cause='';
  $('editor').inert=true;
  try{
   payload.request_id=await requestId(payload);const receipt=await api('/'+mode,payload);
   if(!/^entry_[a-f0-9]{32}$/.test(receipt.entry_id||'')||receipt.author!==principal||!Number.isFinite(Date.parse(receipt.created_at))||!/^[a-f0-9]{64}$/.test(receipt.sha256||'')||typeof receipt.replayed!=='boolean')throw Error('No valid save receipt was returned.');
   confirmed=receipt;
   await list();await show(receipt.entry_id);status('Saved '+receipt.entry_id+(receipt.replayed?' — confirmed the original save.':'.'));
  }catch(error){status(confirmed?'Saved '+confirmed.entry_id+'. The record view could not refresh: '+error.message:'Save not confirmed. '+error.message+' Retry the unchanged form to reuse its request ID.');}
  finally{busy=false;$('save').disabled=false;$('editor').inert=false;}
 };
 $('new-entry').onclick=()=>edit('predictions');
 $('cancel').onclick=()=>{if(busy)return;$('editor').hidden=true;if(active)show(active.entry_id).catch(error=>status(error.message));else $('welcome').hidden=false;};
 $('reload').onclick=()=>list().catch(error=>status(error.message));
 $('more').onclick=()=>list(true).catch(error=>status(error.message));
 $('cause-unknown').onchange=()=>{$('cause').disabled=$('cause-unknown').checked;$('cause').required=!$('cause-unknown').checked;};
 window.addEventListener('hashchange',()=>{if(!busy&&/^#entry_[a-f0-9]{32}$/.test(location.hash))show(location.hash.slice(1)).catch(error=>status(error.message));});
 async function start(){
  const auth=await fetch('/api/auth/status',{credentials:'same-origin'});const session=await auth.json();
  principal=session.principal||'';$('identity').textContent=principal?'Signed in as '+principal:'Sign in to read shared entries.';
  $('preview-notice').hidden=session.local_preview!==true;
  await list();if(/^#entry_[a-f0-9]{32}$/.test(location.hash))await show(location.hash.slice(1));
 }
 start().catch(error=>status(error.message));
})();
