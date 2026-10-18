#!/usr/bin/env node
/** Prepare an upgrade of the installed glossary bridge. Never installs/restarts. */
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
import {patchStandingRunner,patchStandingMavis} from './standing-runtime-patches.mjs';
const argv=process.argv.slice(2),options={};
for(let i=0;i<argv.length;i+=2){
 if(!['--pilots','--hy4','--mavis-root','--output'].includes(argv[i])||!argv[i+1]||options[argv[i]])throw Error('Supply each of --pilots ROOT --hy4 ROOT --mavis-root ROOT --output NEW_FOLDER once');
 options[argv[i]]=path.resolve(argv[i+1]);
}
if(Object.keys(options).length!==4)throw Error('All four staging paths are required');
const output=options['--output'];if(fs.existsSync(output))throw Error('Output must be a new review folder');
const here=path.dirname(fileURLToPath(import.meta.url)),sha=bytes=>createHash('sha256').update(bytes).digest('hex');
const roots={pilots:options['--pilots'],hy4:options['--hy4'],mavis:path.join(options['--mavis-root'],'hearth')};
const targets=[
 ['pilots',roots.pilots,'integrations/model-pilots/runner.mjs',patchStandingRunner],
 ['hy4',roots.hy4,'integrations/hy4/runner.mjs',patchStandingRunner],
 ['mavis',options['--mavis-root'],'mavis-hearth-campfire-handler.ps1',patchStandingMavis],
 ['mavis',options['--mavis-root'],'mavis-hearth-mention-handler.ps1',patchStandingMavis]
];
// Validate all current sources before creating candidates. Drift fails closed.
const edits=targets.map(([label,root,relative,transform])=>{
 const destination=path.join(root,relative),before=fs.readFileSync(destination);
 return {destination,relative:path.join(label,relative),before,after:Buffer.from(transform(before.toString('utf8')))};
});
for(const [label,root]of Object.entries(roots))for(const name of ['client.mjs','turn.mjs','http.mjs',...(label==='mavis'?['mavis.mjs']:[])]){
 const destination=path.join(root,'integrations/commons',name);
 edits.push({destination,relative:path.join(label,'integrations/commons',name),before:fs.readFileSync(destination),after:fs.readFileSync(path.join(here,name))});
}
const files=[];
for(const edit of edits){
 const candidate=path.join(output,edit.relative);fs.mkdirSync(path.dirname(candidate),{recursive:true});fs.writeFileSync(candidate,edit.after);
 files.push({destination:edit.destination,candidate:edit.relative,before_sha256:sha(edit.before),after_sha256:sha(edit.after)});
}
fs.writeFileSync(path.join(output,'manifest.json'),JSON.stringify({schema:'hearth.commons.runtime-candidates.v1',files},null,2)+'\n');
console.log(JSON.stringify({staged_files:files.length,manifest:path.join(output,'manifest.json'),live_files_changed:0}));
