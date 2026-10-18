/** Exact-anchor upgrades of the already installed glossary handlers. Stage only. */
import {patchJournalRunner} from './runtime-patches.mjs';
function replace(source,before,after){if(source.split(before).length!==2)throw Error('Standing runtime anchor missing or ambiguous');return source.replace(before,after);}
export function patchStandingRunner(source){
 source=patchJournalRunner(source);
 source=replace(source,'createProjectTurn,glossaryReceiptSummary','createProjectTurn,glossaryReceiptSummary,standingReply');
 source=replace(source,'const glossary=createProjectTurn({',"const glossary=createProjectTurn({standingProjects:['glossary','journal'],");
 source=replace(source,'if(glossary.authorized)outcome.content=glossaryReceiptSummary(glossary);',"if(glossary.authorized)outcome.content=standingReply(glossary,outcome.content);");
 return replace(source,'For an ambient (unmentioned) turn, do not post through tools, write Memory/files, submit tasks, or resume work; just read relevant context and optionally give one conversational reply.',
  'For an ambient (unmentioned) turn, standing permission allows only the exposed glossary/journal tools and at most one sourced contribution. Otherwise do not post through tools, write Memory/files, submit tasks, or resume unrelated work; optionally give one conversational reply.');
}
export function patchStandingMavis(source){
 if(source.includes('--standing-chat'))throw Error('Standing route already installed');
 // Remove only the prior installed command detour. Ordinary post/delegation remains.
 if(source.includes('# Connected glossary mention routing')){
  const start=source.indexOf('# Connected glossary mention routing'),end=source.indexOf('# Condensed Mavis persona',start);
  if(end<0)throw Error('Mention route anchor missing');source=source.slice(0,start)+source.slice(end);
 }
 if(source.includes('  # Explicit glossary command selection only;')){
  const start=source.indexOf('  # Explicit glossary command selection only;'),end=source.indexOf('  # Pre-fetch recent room history',start);
  if(end<0)throw Error('Campfire route anchor missing');source=source.slice(0,start)+source.slice(end);
 }
 const original='& $mmxCmd text chat --model MiniMax-M3 --messages-file $msgsFile --output text *> $tmpOut';
 return replace(source,original,`if ($env:HEARTH_ROOM_ID -eq '!WO2IHWuW71x_ENPhkPb-HDw6nPDa-xIP37yJIeUmFVc') {
        & node (Join-Path $PSScriptRoot 'hearth\\integrations\\commons\\mavis.mjs') --standing-chat --messages-file $msgsFile *> $tmpOut
      } else {
        ${original}
      }`);
}
