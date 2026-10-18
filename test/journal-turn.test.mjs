import {test} from 'node:test';import assert from 'node:assert/strict';
import {createProjectTurn} from '../integrations/commons/turn.mjs';
import {commonsProjectHTTP} from '../integrations/commons/http.mjs';
test('journal turn is explicitly gated and does not broaden glossary or ambient writes',async()=>{
 const event={type:'m.room.message',event_id:'$journal-fixture',sender:'@rad:test',content:{body:'/journal record a prediction','m.mentions':{user_ids:['@mavis:test']}}};
 const options={principal:'mavis',agentId:'@mavis:test',roomId:'!commons:test',triggerRoom:'!commons:test',humanSenders:['@rad:test'],enabled:true,event,callTool:async()=>({structuredContent:{entry_id:'entry_'+'a'.repeat(32),author:'mavis',created_at:'2026-10-18T00:00:00Z',sha256:'b'.repeat(64),replayed:false}})};
 const turn=createProjectTurn(options);
 assert.ok(turn.authorized);assert.ok(turn.tools.some(t=>t.function.name==='journal_prediction_create'));
 assert.ok(createProjectTurn({...options,event:{...event,content:{...event.content,body:'/journal\trecord'}}}).authorized);
 for(const mentions of ['not-a-mention @mavis:test.extra',{'0':'@mavis:test'},['@mavis:test.extra']]){
  const malformed=createProjectTurn({...options,event:{...event,content:{...event.content,'m.mentions':{user_ids:mentions}}}});
  assert.equal(malformed.authorized,false);
  assert.ok(malformed.tools.every(t=>!t.function.name.endsWith('_create')));
 }
 assert.ok(!turn.tools.some(t=>t.function.name==='glossary_distinction_create'));
 assert.ok(turn.tools.some(t=>t.function.name==='glossary_list'));
 await assert.rejects(turn.call('glossary_distinction_create',{}));
 const ambient=createProjectTurn({...options,event:{...event,sender:'@other:test'}});
 assert.ok(!ambient.authorized);assert.ok(ambient.tools.every(t=>!t.function.name.endsWith('_create')));
 let request;
 const http=commonsProjectHTTP({baseUrl:'https://hearth.test',token:'fixture',fetchImpl:async(url,args)=>{request={url,args};return {ok:true,json:async()=>({entries:[]})};}});
 await http({name:'journal_list'});assert.equal(request.url,'https://hearth.test/api/commons/journal');
 await assert.rejects(http({name:'shell'}));
});
