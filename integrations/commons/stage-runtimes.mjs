#!/usr/bin/env node
/** Stage reviewable files only. Does not install, launch models or restart. */
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
import {patchPilot,patchHy4,patchMavis} from './runtime-patches.mjs';
const argv=process.argv.slice(2),options={};
for(let i=0;i<argv.length;i+=2){if(!['--pilots','--hy4','--mavis-root','--output'].includes(argv[i])||!argv[i+1])throw Error('Supply --pilots ROOT --hy4 ROOT --mavis-root ROOT --output NEW_FOLDER');options[argv[i]]=path.resolve(argv[i+1]);}
if(Object.keys(options).length!==4)throw Error('All four staging paths are required');
const output=options['--output'];if(fs.existsSync(output))throw Error('Output must be a new review folder');
const sha=bytes=>createHash('sha256').update(bytes).digest('hex');
const here=path.dirname(fileURLToPath(import.meta.url));
const targets=[['pilots',options['--pilots'],'integrations/model-pilots/runner.mjs',patchPilot],['hy4',options['--hy4'],'integrations/hy4/runner.mjs',patchHy4],['mavis',options['--mavis-root'],'mavis-hearth-campfire-handler.ps1',patchMavis]];
const files=[];
function stage(destination,relative,bytes,before){
 const candidate=path.join(output,relative);fs.mkdirSync(path.dirname(candidate),{recursive:true});fs.writeFileSync(candidate,bytes);
 files.push({destination,candidate:relative,before_sha256:before===null?null:sha(before),after_sha256:sha(bytes)});
}
// Validate every source before creating candidates. Drift fails closed.
const edits=targets.map(([label,root,relative,transform])=>{const target=path.join(root,relative),before=fs.readFileSync(target);return {label,root,relative,target,before,after:transform(before.toString('utf8'))};});
for(const edit of edits){
 stage(edit.target,path.join(edit.label,edit.relative),Buffer.from(edit.after),edit.before);
 const root=edit.label==='mavis'?path.join(edit.root,'hearth'):edit.root;
 for(const name of ['client.mjs','turn.mjs','http.mjs',...(edit.label==='mavis'?['mavis.mjs']:[])]){
  const destination=path.join(root,'integrations/commons',name);
  stage(destination,path.join(edit.label,'integrations/commons',name),fs.readFileSync(path.join(here,name)),fs.existsSync(destination)?fs.readFileSync(destination):null);
 }
}
fs.writeFileSync(path.join(output,'manifest.json'),JSON.stringify({schema:'hearth.commons.runtime-candidates.v1',files},null,2)+'\n');
console.log(JSON.stringify({staged_files:files.length,manifest:path.join(output,'manifest.json'),live_files_changed:0}));
