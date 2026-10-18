/** Exact-anchor candidate generation. This module never writes a live runtime. */
function replace(source,before,after){
 if(source.split(before).length!==2)throw Error('Runtime anchor missing or ambiguous; reconcile current source before activation');
 return source.replace(before,after);
}
const imported='import {createGlossaryTurn,glossaryReceiptSummary} from "../commons/turn.mjs";\n';
function receiptReply(source){return replace(source,'    if (outcome.content.trim() === "__SILENT__") {',`    if(glossary.authorized)outcome.content=glossaryReceiptSummary(glossary);
    if (outcome.content.trim() === "__SILENT__") {`);}
export function patchPilot(source){
 source=replace(source,'import fs from "node:fs";',imported+'import fs from "node:fs";');
 source=replace(source,'    const tools = [...memoryTools, ...(inCommons ? commonsTools() : [])];',`    const glossary=createGlossaryTurn({principal:PROFILE,agentId:agentEnv.MATRIX_USER_ID,roomId:config.commonsRoomId,
      humanSenders:config.humanSenders,event,triggerRoom:trigger.roomId,enabled:inCommons,
      callTool:request=>clients.memory.callTool(request)});
    const tools = [...memoryTools, ...(inCommons ? commonsTools() : []), ...glossary.tools];`);
 source=replace(source,'        callWorkspaceTool: inCommons ? commonsHandler(archive) : undefined,',`        callWorkspaceTool: (name,args)=>name.startsWith('glossary_')?glossary.call(name,args).then(JSON.stringify):commonsHandler(archive)(name,args),`);
 source=replace(source,'content: systemPrompt(PROFILES[PROFILE].name)',"content: glossary.policy + '\\n' + systemPrompt(PROFILES[PROFILE].name)");
 return receiptReply(source);
}
export function patchHy4(source){
 source=replace(source,'import fs from "node:fs";',imported+'import fs from "node:fs";');
 source=replace(source,'    const tools = ambientTurn ?',`    const glossary=createGlossaryTurn({principal:'hy4',agentId:agentEnv.MATRIX_USER_ID,roomId:config.commonsRoomId,
      humanSenders:config.humanSenders,event,triggerRoom:trigger.roomId,enabled:trigger.roomId===config.commonsRoomId,
      callTool:request=>clients.memory.callTool(request)});
    const baseTools = ambientTurn ?`);
 source=replace(source,'    const workspaceHandler=createWorkspaceHandler(',`    const tools=[...baseTools,...glossary.tools];
    const workspaceHandler=createWorkspaceHandler(`);
 source=replace(source,'callWorkspaceTool: (name,args)=>/^(team_|project_|task_submit)/.test(name)?teamHandler(name,args):workspaceHandler(name,args),',"callWorkspaceTool: (name,args)=>name.startsWith('glossary_')?glossary.call(name,args).then(JSON.stringify):/^(team_|project_|task_submit)/.test(name)?teamHandler(name,args):workspaceHandler(name,args),");
 source=replace(source,'content: (config.teamMode?teamPolicy:systemPrompt())',"content: glossary.policy + '\\n' + (config.teamMode?teamPolicy:systemPrompt())");
 return receiptReply(source);
}
export function patchMavis(source){
 return replace(source,'  # Pre-fetch recent room history for context',`  # Explicit glossary command selection only; the Node host re-fetches and verifies
  # the exact event, human sender and direct mention before any model call/write.
  if ($sender -eq '@rad:hearth.radekal.me' -and $body -match '\\A(?:[ \\t]*\\r?\\n)*/glossary(?:[ \\t]|$)') {
    $env:HEARTH_COMMONS_TOOLS = '1'
    & node (Join-Path $PSScriptRoot 'hearth\\integrations\\commons\\mavis.mjs') --project-turn
    if ($LASTEXITCODE -ne 3) { exit $LASTEXITCODE }
  }

  # Pre-fetch recent room history for context`);
}
