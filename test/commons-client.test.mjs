import assert from 'node:assert/strict';
import {existsSync} from 'node:fs';
import {spawn} from 'node:child_process';
import {createInterface} from 'node:readline';
import {once} from 'node:events';
import {fileURLToPath} from 'node:url';
import test from 'node:test';

const target = new URL('../integrations/commons/client.mjs', import.meta.url);
async function adapter(options) {
  assert.ok(existsSync(target), 'Commons runtime adapter has not been implemented');
  const {createCommonsAdapter} = await import(target.href);
  return createCommonsAdapter(options);
}
const payload = {collection:'glossary',kind:'distinction',content:'A real discriminating example.',
  source_refs:['event:adapter-fixture'],links:[],request_id:'adapter-first'};

test('ambient adapters never expose or dispatch contribution operations', async () => {
  const client = await adapter({principal:'kimi3',callTool:async()=>{throw Error('Transport must not run');}});
  assert.deepEqual(client.tools.map(t=>t.function.name), ['commons_files_list','commons_files_read']);
  await assert.rejects(client.call('commons_entry_create',payload), /authorized project/i);
  await assert.rejects(client.call('shell',{command:'whoami'}), /unknown/i);
});

test('every configured runtime identity receives a real committed receipt', async t => {
  assert.ok(existsSync(target), 'Commons runtime adapter has not been implemented');
  const child = spawn(process.env.HEARTH_TEST_PYTHON || 'python',
    ['-u',fileURLToPath(new URL('./commons_fixture.py',import.meta.url))],
    {stdio:['ignore','pipe','pipe']});
  const lines = createInterface({input:child.stdout});
  const firstLine = once(lines,'line');
  let diagnostics=''; child.stderr.on('data',c=>{diagnostics+=c;});
  const startup = setTimeout(()=>child.kill(),15000);
  child.on('error',()=>{});
  t.after(()=>{clearTimeout(startup);lines.close();child.kill();});
  const [line] = await Promise.race([firstLine,once(child,'exit').then(()=>{throw Error('Fixture failed: '+diagnostics);})]);
  clearTimeout(startup);
  const {port} = JSON.parse(line);
  for (const principal of ['codex','kimi3','glm53','hy4','mavis']) {
    const client = await adapter({principal,authorizedProject:true,callTool:async request=>{
      const response = await fetch(`http://127.0.0.1:${port}/`,{method:'POST',
        headers:{'Content-Type':'application/json',Authorization:`Bearer fixture-${principal}`},
        body:JSON.stringify(request)});
      return response.json();
    }});
    const receipt = await client.call('commons_entry_create',payload);
    assert.equal(receipt.author,principal);
    const read = await client.call('commons_files_read',{entry_id:receipt.entry_id});
    assert.equal(read.content,'A real discriminating example.');
    assert.equal(read.author,principal);
    const retry = await client.call('commons_entry_create',payload);
    assert.equal(retry.entry_id,receipt.entry_id);
    assert.equal(retry.replayed,true);
    await assert.rejects(client.call('commons_entry_create',{...payload,author:'rad'}), /unexpected/i);
  }
});

test('failed, malformed and wrong-author receipts never become successful saves', async () => {
  const valid={entry_id:'entry_'+'a'.repeat(32),author:'hy4',created_at:'2026-10-17T15:00:00+00:00',sha256:'b'.repeat(64),replayed:false};
  for (const response of [
    {isError:true,content:[{type:'text',text:'Store unavailable'}]},
    {content:[{type:'text',text:'I saved it, trust me'}]},
    {structuredContent:{...valid,author:'rad'}},
    {structuredContent:{...valid,created_at:'yesterday'}},
    {structuredContent:{...valid,sha256:'fake'}},
  ]) {
    const client=await adapter({principal:'hy4',authorizedProject:true,callTool:async()=>response});
    await assert.rejects(client.call('commons_entry_create',payload));
  }
});

test('typed glossary tools are explicit, project-scoped and require real author receipts',async()=>{
 const receipt={entry_id:'entry_'+'c'.repeat(32),author:'kimi3',created_at:'2026-10-17T15:00:00+00:00',sha256:'d'.repeat(64),replayed:false};
 const draft={title:'Synthetic',distinction:'Evidence discriminates.',discriminating_example:'A second sensor rules out noise.',unresolved_edge_case:'Shared faults.',source_refs:['fixture'],request_id:'glossary-fixture'};
 const ambient=await adapter({principal:'kimi3',includeGlossary:true,callTool:async()=>{throw Error('must not run');}});
 assert.ok(ambient.tools.some(t=>t.function.name==='glossary_entry_read'));
 assert.ok(!ambient.tools.some(t=>t.function.name==='glossary_distinction_create'));
 await assert.rejects(ambient.call('glossary_distinction_create',draft),/authorized project/i);
 const seen=[];
 const project=await adapter({principal:'kimi3',includeGlossary:true,authorizedProject:true,callTool:async request=>{seen.push(request);return {structuredContent:receipt};}});
 assert.equal((await project.call('glossary_distinction_create',draft)).author,'kimi3');
 assert.deepEqual(seen[0].arguments,draft);
 await assert.rejects(project.call('glossary_distinction_create',{...draft,author:'mavis'}),/unexpected/i);
 const wrong=await adapter({principal:'kimi3',includeGlossary:true,authorizedProject:true,callTool:async()=>({structuredContent:{...receipt,author:'mavis'}})});
 await assert.rejects(wrong.call('glossary_distinction_create',draft),/receipt/i);
 const hidden=await adapter({principal:'kimi3',authorizedProject:true,callTool:async()=>{throw Error('must not run');}});
 await assert.rejects(hidden.call('glossary_distinction_create',draft),/unknown/i);
});
