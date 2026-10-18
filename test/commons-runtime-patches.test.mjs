import assert from 'node:assert/strict';
import {test} from 'node:test';
import fs from 'node:fs';
import path from 'node:path';
import {tmpdir} from 'node:os';
import {execFileSync} from 'node:child_process';
import {patchPilot,patchHy4,patchMavis,patchMavisMention} from '../integrations/commons/runtime-patches.mjs';
import {patchJournalRunner,patchJournalMavis} from '../integrations/commons/runtime-patches.mjs';

test('journal upgrade requires installed bridge and fails closed on drift',()=>{
 const source=`import {createGlossaryTurn,glossaryReceiptSummary} from '../commons/turn.mjs';\nconst glossary=createGlossaryTurn({});\nname.startsWith('glossary_')?glossary.call(name,args):ordinary();`;
 const result=patchJournalRunner(source);
 assert.match(result,/createProjectTurn/);assert.match(result,/glossary\|journal/);assert.match(result,/ordinary\(\)/);
 assert.throws(()=>patchJournalRunner(result),/anchor/);
 assert.throws(()=>patchJournalRunner('drift'),/anchor/);
 const mavis=patchJournalMavis(patchMavisMention('# Condensed Mavis persona for mention-wake.'));
 assert.ok(mavis.includes('/(?:glossary|journal)'));
 assert.throws(()=>patchJournalMavis(mavis),/anchor/);
});
test('runtime patches preserve existing dispatch and fail closed against drift',()=>{
 const source=`import fs from "node:fs";\n    const tools = [...memoryTools, ...(inCommons ? commonsTools() : [])];\n        callWorkspaceTool: inCommons ? commonsHandler(archive) : undefined,\n          { role: "system", content: systemPrompt(PROFILES[PROFILE].name)\n    if (outcome.content.trim() === "__SILENT__") {`;
 const result=patchPilot(source);
 assert.match(result,/createGlossaryTurn/);assert.match(result,/\.\.\.glossary.tools/);
 assert.match(result,/glossary.call\(name,args\)/);assert.match(result,/commonsHandler\(archive\)\(name,args\)/);
 assert.match(result,/outcome.content=glossaryReceiptSummary/);
 assert.throws(()=>patchPilot(result),/anchor/);
 assert.throws(()=>patchPilot('drift'),/anchor/);
 assert.throws(()=>patchHy4('drift'),/anchor/);
 const mavis=patchMavis('  # Pre-fetch recent room history for context');
 assert.match(mavis,/HEARTH_COMMONS_TOOLS/);assert.match(mavis,/--project-turn/);
 assert.match(mavis,/exit \$LASTEXITCODE/);
});
test('active Mavis mention route delegates only explicit human glossary commands',()=>{
 const result=patchMavisMention('# Condensed Mavis persona for mention-wake.\nORIGINAL');
 assert.match(result,/HEARTH_SENDER -eq '@rad:hearth.radekal.me'/);
 assert.match(result,/mavis-hearth-campfire-handler.ps1/);
 assert.ok(result.indexOf('mavis-hearth-campfire-handler.ps1')<result.indexOf('ORIGINAL'));
 assert.throws(()=>patchMavisMention(result),/anchor|already/);
});
test('Windows mention route preserves ordinary turns and invokes only the bounded handler',{skip:process.platform!=='win32'},()=>{
 const root=fs.mkdtempSync(path.join(tmpdir(),'commons-mention-route-'));
 const wrapper=path.join(root,'mention.ps1'),handler=path.join(root,'mavis-hearth-campfire-handler.ps1');
 try{
  fs.writeFileSync(handler,"Write-Output 'ROUTED'; exit 0\n");
  fs.writeFileSync(wrapper,patchJournalMavis(patchMavisMention("# Condensed Mavis persona for mention-wake.\nWrite-Output 'ORIGINAL'\n")));
  for(const [sender,body,expected]of [['@rad:hearth.radekal.me','/journal\tdraft','ROUTED'],['@other:test','/journal draft','ORIGINAL'],['@rad:hearth.radekal.me','/glossary draft','ROUTED'],['@rad:hearth.radekal.me','\n/glossary draft','ROUTED'],['@other:test','/glossary draft','ORIGINAL'],['@rad:hearth.radekal.me','hello\n/glossary quoted','ORIGINAL'],['@rad:hearth.radekal.me','> /glossary quoted','ORIGINAL']]){
   const output=execFileSync('powershell.exe',['-NoProfile','-NonInteractive','-File',wrapper],{windowsHide:true,encoding:'utf8',env:{...process.env,HEARTH_SENDER:sender,HEARTH_BODY:body}});
   assert.equal(output.trim(),expected);
  }
 }finally{for(const file of [wrapper,handler])if(fs.existsSync(file))fs.unlinkSync(file);fs.rmdirSync(root);}
});
