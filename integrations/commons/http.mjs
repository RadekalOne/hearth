/** Bounded REST transport using an existing authenticated Memory token. */
export function commonsProjectHTTP({baseUrl,token,fetchImpl=fetch}){
 const base=new URL(baseUrl);
 if(base.username||base.password||base.search||base.hash||!(base.protocol==='https:'||(base.protocol==='http:'&&['127.0.0.1','localhost'].includes(base.hostname))))throw Error('Invalid Hearth HTTPS origin');
 const paths={journal_list:['GET',''],journal_entry_read:['GET','/entries/'],journal_prediction_create:['POST','/predictions'],journal_outcome_create:['POST','/outcomes'],glossary_list:['GET',''],glossary_entry_read:['GET','/entries/'],glossary_distinction_create:['POST','/distinctions'],glossary_refinement_create:['POST','/refinements'],glossary_application_create:['POST','/applications']};
 return async({name,arguments:args={}})=>{
  const operation=paths[name];if(!operation)throw Error('Unknown glossary operation');
  let suffix=operation[1];
  if(name.endsWith('_entry_read')){if(!/^entry_[a-f0-9]{32}$/.test(args.entry_id??''))throw Error('Invalid entry ID');suffix+=args.entry_id;}
  if(name.endsWith('_list')&&args.cursor)suffix+='?cursor='+encodeURIComponent(args.cursor);
  const response=await fetchImpl(base.href.replace(/\/$/,'')+'/api/commons/'+(name.startsWith('journal_')?'journal':'glossary')+suffix,{method:operation[0],redirect:'error',
   headers:{Authorization:'Bearer '+token,...(operation[0]==='POST'?{'Content-Type':'application/json'}:{})},
   ...(operation[0]==='POST'?{body:JSON.stringify(args)}:{}),signal:AbortSignal.timeout(30000)});
  if(!response.ok)throw Error('Glossary transport HTTP '+response.status);
  return {structuredContent:await response.json()};
 };
}

export const glossaryHTTP=commonsProjectHTTP;
