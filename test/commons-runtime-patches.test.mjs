import assert from 'node:assert/strict';
import {test} from 'node:test';
import {patchPilot,patchHy4,patchMavis} from '../integrations/commons/runtime-patches.mjs';
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
