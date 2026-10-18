import {test} from 'node:test';import assert from 'node:assert/strict';
import {patchStandingRunner,patchStandingMavis} from '../integrations/commons/standing-runtime-patches.mjs';
test('standing runner upgrade installs narrow grant and preserves conversation/other ambient limits',()=>{
 const source=`import {createGlossaryTurn,glossaryReceiptSummary} from "../commons/turn.mjs";\nconst glossary=createGlossaryTurn({principal:'hy4',enabled:true});\nname.startsWith('glossary_')?glossary.call(name,args):ordinary();\nif(glossary.authorized)outcome.content=glossaryReceiptSummary(glossary);\nFor an ambient (unmentioned) turn, do not post through tools, write Memory/files, submit tasks, or resume work; just read relevant context and optionally give one conversational reply.`;
 const result=patchStandingRunner(source);
 assert.match(result,/standingProjects:\['glossary','journal'\]/);assert.match(result,/standingReply/);
 assert.match(result,/do not post through tools, write Memory/);assert.match(result,/ordinary\(\)/);
 assert.throws(()=>patchStandingRunner(result),/anchor|already/);
});
test('Mavis upgrade uses ordinary message-file turn and retains existing post wrapper',()=>{
 const source=`# Condensed Mavis persona\n& $mmxCmd text chat --model MiniMax-M3 --messages-file $msgsFile --output text *> $tmpOut\nPOST_ORIGINAL`;
 const result=patchStandingMavis(source);
 assert.match(result,/--standing-chat --messages-file \$msgsFile/);assert.match(result,/POST_ORIGINAL/);
 assert.match(result,/HEARTH_ROOM_ID -eq/);assert.match(result,/else/);
 assert.throws(()=>patchStandingMavis(result),/anchor|already/);
});
