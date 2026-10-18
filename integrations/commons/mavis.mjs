#!/usr/bin/env node
/** Explicit project command path; ordinary Mavis conversation stays unchanged. */
import {spawn} from 'node:child_process';
import {mkdtemp,writeFile,readFile,rm,rmdir} from 'node:fs/promises';
import {tmpdir,homedir} from 'node:os';
import path from 'node:path';
import {createProjectTurn,runStructuredTurn,runStandingConversation} from './turn.mjs';
import {commonsProjectHTTP} from './http.mjs';
const env=process.env;
const room='!WO2IHWuW71x_ENPhkPb-HDw6nPDa-xIP37yJIeUmFVc';
async function matrixGET(suffix){
 const url=new URL(env.MATRIX_HOMESERVER_URL);
 if(url.protocol!=='https:'||url.username||url.password)throw Error('Invalid Matrix origin');
 const response=await fetch(url.href.replace(/\/$/,'')+'/_matrix/client/v3/'+suffix,{headers:{Authorization:'Bearer '+env.MATRIX_ACCESS_TOKEN},redirect:'error',signal:AbortSignal.timeout(30000)});
 if(!response.ok)throw Error('Matrix provenance HTTP '+response.status);
 return response.json();
}
async function complete(messages){
 const folder=await mkdtemp(path.join(tmpdir(),'hearth-mavis-glossary-'));
 const file=path.join(folder,'messages.json');
 try{
  await writeFile(file,JSON.stringify(messages),{encoding:'utf8',mode:0o600});
  const script='$OutputEncoding=[Text.UTF8Encoding]::new($false); [Console]::OutputEncoding=[Text.UTF8Encoding]::new($false); & "$env:APPDATA\\npm\\mmx.cmd" text chat --model MiniMax-M3 --messages-file $env:HEARTH_MMX_MESSAGES_FILE --output text; exit $LASTEXITCODE';
  const output=await new Promise((resolve,reject)=>{
   const child=spawn('powershell.exe',['-NoProfile','-NonInteractive','-Command',script],{windowsHide:true,env:{...env,HEARTH_MMX_MESSAGES_FILE:file},stdio:['ignore','pipe','pipe'],timeout:120000});
   const chunks=[];let size=0;
   child.stdout.on('data',data=>{size+=data.length;if(size>200000)child.kill();else chunks.push(data);});
   child.stderr.on('data',()=>{});child.on('error',()=>reject(Error('MiniMax CLI could not start')));
   child.on('close',code=>code===0&&size<=200000?resolve(Buffer.concat(chunks).toString('utf8')):reject(Error('MiniMax CLI failed; no save established by its output')));
  });
  return output.replace(/<mm:think>[\s\S]*?<\/mm:think>/g,'').trim();
 }finally{await rm(file,{force:true});await rmdir(folder);}
}
try{
 const standingChat=process.argv.includes('--standing-chat');
 if(standingChat){
  const profile=await readFile(path.join(homedir(),'AI Projects/hearth/secrets/agents/mavis.env'),'utf8');
  for(const line of profile.split(/\r?\n/)){
   const match=/^(MATRIX_HOMESERVER_URL|MATRIX_ACCESS_TOKEN|HEARTH_MEMORY_URL|HEARTH_MEMORY_TOKEN)=(.*)$/.exec(line);
   if(match)env[match[1]]=match[2];
  }
 }
 const callTool=commonsProjectHTTP({baseUrl:env.HEARTH_MEMORY_URL,token:env.HEARTH_MEMORY_TOKEN});
 const who=await matrixGET('account/whoami');
 if(who.user_id!=='@mavis:hearth.radekal.me')throw Error('Mavis identity mismatch');
 if(process.argv.includes('--probe')){
  await callTool({name:process.argv.includes('--journal')?'journal_list':'glossary_list'});console.log('Mavis authenticated glossary read OK; no model call or write.');
 }else{
  const event=await matrixGET('rooms/'+encodeURIComponent(room)+'/event/'+encodeURIComponent(env.HEARTH_EVENT_ID??''));
  if(event.event_id!==env.HEARTH_EVENT_ID)throw Error('Origin event mismatch');
  const turn=createProjectTurn({principal:'mavis',agentId:who.user_id,roomId:room,triggerRoom:env.HEARTH_ROOM_ID,
   humanSenders:['@rad:hearth.radekal.me'],event,enabled:standingChat||env.HEARTH_COMMONS_TOOLS==='1',standingProjects:standingChat?['glossary','journal']:[],callTool});
  if(!turn.authorized){process.exitCode=3;}else{
   // Verify access before any paid completion. No write is performed by this read.
   let contextMessages=[];
   if(standingChat){
    const index=process.argv.indexOf('--messages-file'),file=process.argv[index+1];
    if(index<0||!file)throw Error('Missing host message file');
    const text=await readFile(file,'utf8');if(text.length>200000)throw Error('Oversized host context');
    contextMessages=JSON.parse(text);
    if(!Array.isArray(contextMessages)||contextMessages.length>5||contextMessages.some(m=>!m||!['system','user','assistant'].includes(m.role)||typeof m.content!=='string'))throw Error('Invalid host context');
   }
   const brief='Origin '+event.event_id+' from '+event.sender+':\n'+event.content.body;
   if(!standingChat)await turn.call(turn.tools.some(t=>t.function.name==='journal_prediction_create')?'journal_list':'glossary_list',{});
   // stdout is an operational receipt, never automatically a Commons post.
   console.log(standingChat?await runStandingConversation({turn,brief,contextMessages,complete}):JSON.stringify(await runStructuredTurn({turn,brief,complete})));
  }
 }
}catch{console.error('Mavis glossary turn failed. Inspect canonical glossary records before retrying; a lost response may already have committed.');process.exitCode=1;}
