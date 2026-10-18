import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createProjectTurn,runStructuredTurn,standingReply,runStandingConversation} from '../integrations/commons/turn.mjs';
const event={event_id:'$ordinary',type:'m.room.message',sender:'@glm53:test',content:{body:'This distinction may be useful.'}};
const config={principal:'kimi3',agentId:'@kimi3:test',roomId:'!commons:test',triggerRoom:'!commons:test',humanSenders:['@rad:test'],enabled:true,standingProjects:['glossary','journal'],event};
const args={title:'Fixture',distinction:'A',discriminating_example:'B',unresolved_edge_case:'C',source_refs:['fixture:ordinary']};
const receipt={entry_id:'entry_'+'a'.repeat(32),author:'kimi3',created_at:'2026-10-18T00:00:00Z',sha256:'b'.repeat(64),replayed:false};
test('trusted standing grant enables scoped ordinary turns with stable event retries',async()=>{
 const calls=[];const options={...config,callTool:async request=>{calls.push(request);return {structuredContent:receipt};}};
 const turn=createProjectTurn(options);assert.equal(turn.authorized,true);assert.equal(turn.standing,true);
 assert.ok(turn.tools.some(t=>t.function.name==='journal_prediction_create'));
 await turn.call('glossary_distinction_create',args);
 await createProjectTurn(options).call('glossary_distinction_create',args);
 assert.equal(calls[0].arguments.request_id,calls[1].arguments.request_id);
 await assert.rejects(turn.call('journal_prediction_create',{}));
 await assert.rejects(turn.call('commons_entry_create',{}));
 for(const change of [{triggerRoom:'!other:test'},{principal:'intruder'},{agentId:'@other:test'},{event:{...event,sender:'@kimi3:test'}},{enabled:false}]){
  assert.equal(createProjectTurn({...options,...change}).authorized,false);
 }
 assert.throws(()=>createProjectTurn({...options,standingProjects:['shell']}));
 const glossary=createProjectTurn({...options,standingProjects:['glossary']});
 assert.ok(!glossary.tools.some(t=>t.function.name==='journal_prediction_create'));
});
test('standing structured turns preserve ordinary conversation without claiming a save',async()=>{
 const turn=createProjectTurn({...config,callTool:async()=>assert.fail('No tool needed')});
 const result=await runStructuredTurn({turn,brief:'hello',complete:async()=>JSON.stringify({done:'A normal conversational reply.'})});
 assert.equal(result.reply,'A normal conversational reply.');assert.equal(result.receipts.length,0);
 assert.equal(standingReply(turn,result.reply),result.reply);
 assert.match(standingReply({standing:true,receipts:[receipt]},'<<POST>>Hello<<END>>'),/Hello\n\nCommitted Commons records: entry_.*<<END>>/);
});
test('explicit commands keep project-specific receipt-only behavior under standing permission',()=>{
 const command=createProjectTurn({...config,event:{...event,sender:'@rad:test',content:{body:'/journal record', 'm.mentions':{user_ids:['@kimi3:test']}}},callTool:async()=>{}});
 assert.equal(command.standing,false);assert.equal(command.authorized,true);
 assert.ok(!command.tools.some(t=>t.function.name==='glossary_distinction_create'));
 assert.equal(standingReply(command,'Saved it.'),'No contribution confirmed.');
});
test('project preflight failure permits conversation-only fallback, never a write retry',async()=>{
 const turn=createProjectTurn({...config,callTool:async()=>{throw Error('HTTP 503');}});let count=0;
 const reply=await runStandingConversation({turn,brief:'hello',contextMessages:[],complete:async messages=>{count++;assert.match(messages.at(-1).content,/unavailable/);return 'Normal conversation.';}});
 assert.equal(reply,'Normal conversation.');assert.equal(count,1);assert.equal(turn.receipts.length,0);
 let writeCompletions=0;
 const failed=createProjectTurn({...config,callTool:async({name})=>{if(name.endsWith('_create'))throw Error('Lost write response');return {structuredContent:{entries:[]}};}});
 await assert.rejects(runStandingConversation({turn:failed,brief:'fixture',contextMessages:[],complete:async()=>{writeCompletions++;return JSON.stringify({operation:'glossary_distinction_create',arguments:args});}}),/Lost write response/);
 assert.equal(writeCompletions,1);
});
