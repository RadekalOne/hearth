import assert from 'node:assert/strict';
import {test} from 'node:test';
import {createGlossaryTurn,runStructuredTurn} from '../integrations/commons/turn.mjs';
const room='!commons:test',principal='kimi3',human='@rad:test',agent='@kimi3:test';
const event={event_id:'$origin',sender:human,type:'m.room.message',content:{body:'/glossary Draft a distinction', 'm.mentions':{user_ids:[agent]}}};
const config={principal,agentId:agent,roomId:room,humanSenders:[human],event,triggerRoom:room,enabled:true};
const receipt={entry_id:'entry_'+'a'.repeat(32),author:principal,created_at:'2026-10-18T00:00:00Z',sha256:'b'.repeat(64),replayed:false};
const args={title:'Fixture',distinction:'A',discriminating_example:'B',unresolved_edge_case:'C',source_refs:['fixture']};
test('only verified human direct command grants glossary writes; host binds retry IDs',async()=>{
 const calls=[];const turn=createGlossaryTurn({...config,callTool:async request=>{calls.push(request);return {structuredContent:receipt};}});
 assert.equal(turn.authorized,true);
 assert.ok(turn.tools.every(t=>!t.function.name.startsWith('commons_')));
 assert.ok(!turn.tools.find(t=>t.function.name==='glossary_distinction_create').function.parameters.properties.request_id);
 await turn.call('glossary_distinction_create',args);await turn.call('glossary_distinction_create',args);
 assert.equal(calls[0].arguments.request_id,calls[1].arguments.request_id);
 assert.equal(turn.receipts.length,1);
 await assert.rejects(turn.call('glossary_distinction_create',{...args,title:'Changed'}),/one contribution/);
 for(const changes of [{triggerRoom:'!other:test'},{event:{...event,sender:'@agent:test'}},{event:{...event,content:{body:'/glossary go'}}},{event:{...event,content:{...event.content,body:'> /glossary quoted'}}},{event:{...event,content:{...event.content,body:'Example:\n```\n/glossary quoted\n```'}}},{enabled:false}]){
  const denied=createGlossaryTurn({...config,...changes,callTool:async()=>assert.fail('transport called')});
  assert.equal(denied.authorized,false);
  await assert.rejects(denied.call('glossary_distinction_create',args));
 }
});
test('spoofed authors, model IDs, unknown names and failed receipts never establish a save',async()=>{
 const turn=createGlossaryTurn({...config,callTool:async()=>({structuredContent:{...receipt,author:'someone-else'}})});
 await assert.rejects(turn.call('glossary_distinction_create',{...args,request_id:'model'}),/Unexpected/);
 await assert.rejects(turn.call('glossary_distinction_create',{...args,author:'other'}),/Unexpected/);
 await assert.rejects(turn.call('glossary_distinction_create',args),/receipt/);
 assert.equal(turn.receipts.length,0);
 await assert.rejects(turn.call('commons_entry_create',{}),/Unknown/);
});
test('structured Mavis path executes bounded operations and reports only actual receipts',async()=>{
 const turn=createGlossaryTurn({...config,callTool:async()=>({structuredContent:receipt})});
 const outputs=[JSON.stringify({operation:'glossary_distinction_create',arguments:args}),JSON.stringify({done:'Saved a million entries'})];
 const result=await runStructuredTurn({turn,brief:'fixture',complete:async()=>outputs.shift()});
 assert.equal(result.receipts.length,1);assert.doesNotMatch(result.summary,/million/);
 const readTurn=createGlossaryTurn({...config,event:{...event,content:{body:'hello'}},callTool:async()=>({structuredContent:{entries:[]}})});
 await assert.rejects(runStructuredTurn({turn:readTurn,brief:'fixture',complete:async()=>assert.fail()}),/authorized/);
 await assert.rejects(runStructuredTurn({turn,brief:'fixture',complete:async()=>'{broken'}),/JSON/);
 const endless=createGlossaryTurn({...config,callTool:async()=>({structuredContent:{entries:[]}})});let count=0;
 await assert.rejects(runStructuredTurn({turn:endless,brief:'fixture',complete:async()=>{count++;return JSON.stringify({operation:'glossary_list',arguments:{}});}}),/limit/);
 assert.equal(count,6);
});
