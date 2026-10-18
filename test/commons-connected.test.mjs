import assert from 'node:assert/strict';
import {test} from 'node:test';
import {spawn} from 'node:child_process';
import {createInterface} from 'node:readline';
import {fileURLToPath} from 'node:url';
import {createGlossaryTurn,runStructuredTurn} from '../integrations/commons/turn.mjs';
import {glossaryHTTP} from '../integrations/commons/http.mjs';
test('five identities connect through real app; models are fixtures, records are real commits',async t=>{
 const child=spawn(process.env.HEARTH_TEST_PYTHON||'python',[fileURLToPath(new URL('./glossary_preview.py',import.meta.url))],{stdio:['ignore','pipe','pipe']});
 t.after(()=>child.kill());let diagnostics='';child.stderr.on('data',v=>diagnostics+=v);
 const lines=createInterface({input:child.stdout});t.after(()=>lines.close());
 const url=await new Promise((resolve,reject)=>{const timer=setTimeout(()=>reject(Error('Startup timeout '+diagnostics)),30000);
  lines.on('line',line=>{if(line.startsWith('GLOSSARY_PREVIEW=')){clearTimeout(timer);resolve(JSON.parse(line.slice(17)).url);}});
  child.on('error',reject);child.on('exit',()=>{clearTimeout(timer);reject(Error('Fixture stopped '+diagnostics));});});
 const baseUrl=new URL(url).origin,room='!commons:test',human='@rad:test';let first=null;
 for(const principal of ['codex','kimi3','glm53','hy4','mavis']){
  const agentId='@'+principal+':test';
  const event={event_id:'$fixture-'+principal,type:'m.room.message',sender:human,content:{body:'/glossary synthetic test', 'm.mentions':{user_ids:[agentId]}}};
  const options={principal,agentId,roomId:room,triggerRoom:room,humanSenders:[human],event,enabled:true,callTool:glossaryHTTP({baseUrl,token:'fixture-'+principal})};
  const turn=createGlossaryTurn(options);
  const args={title:'Synthetic '+principal,distinction:'Signal suggests; evidence separates explanations.',discriminating_example:'Check an independent sensor.',unresolved_edge_case:'Sensors may share a fault.',source_refs:['fixture:connected']};
  if(principal==='mavis'){
   const outputs=[JSON.stringify({operation:'glossary_distinction_create',arguments:args}),JSON.stringify({done:'fixture'})];
   const result=await runStructuredTurn({turn,brief:'fixture',complete:async()=>outputs.shift()});assert.equal(result.receipts[0].author,principal);
  }else{
   const receipt=await turn.call('glossary_distinction_create',args);assert.equal(receipt.author,principal);
   assert.equal((await turn.call('glossary_distinction_create',args)).entry_id,receipt.entry_id);
  }
  first??=turn.receipts[0].entry_id;
  const restarted=createGlossaryTurn(options);
  assert.equal((await restarted.call('glossary_distinction_create',args)).entry_id,turn.receipts[0].entry_id);
  await assert.rejects(createGlossaryTurn(options).call('glossary_distinction_create',{...args,title:'Changed draft after restart'}),/HTTP 400/);
  assert.equal((await turn.call('glossary_entry_read',{entry_id:first})).author,'codex');
 }
 const reader=glossaryHTTP({baseUrl,token:'fixture-codex'});
 assert.equal((await reader({name:'glossary_list'})).structuredContent.entries.length,5);
 await assert.rejects(glossaryHTTP({baseUrl,token:'invalid'})({name:'glossary_list'}),/HTTP 401/);
});
