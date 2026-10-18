import assert from 'node:assert/strict';
import {test} from 'node:test';
import {spawn} from 'node:child_process';
import {createInterface} from 'node:readline';
import {fileURLToPath} from 'node:url';
import {chromium} from 'playwright';
import {createRequire} from 'node:module';
import {readFile,mkdir} from 'node:fs/promises';
const require=createRequire(import.meta.url);

test('glossary saves, retries, applies, refines and preserves original across reload',async t=>{
 const child=spawn(process.env.HEARTH_TEST_PYTHON||'python',
  [fileURLToPath(new URL('./glossary_preview.py',import.meta.url))],{stdio:['ignore','pipe','pipe'],env:{...process.env,HEARTH_TEST_AXE_PATH:require.resolve('axe-core/axe.min.js')}});
 t.after(()=>child.kill());
 let diagnostics='';child.stderr.on('data',v=>diagnostics+=v);
 const lines=createInterface({input:child.stdout});t.after(()=>lines.close());
 const url=await new Promise((resolve,reject)=>{
  const timeout=setTimeout(()=>reject(Error('Preview startup timeout: '+diagnostics)),30000);
  lines.on('line',line=>{if(line.startsWith('GLOSSARY_PREVIEW=')){clearTimeout(timeout);resolve(JSON.parse(line.slice(17)).url);}});
  child.on('exit',()=>{clearTimeout(timeout);reject(Error('Preview exited: '+diagnostics));});
 });
 const browser=await chromium.launch({headless:true});t.after(()=>browser.close());
 const artifacts=new URL('../test-artifacts/',import.meta.url);await mkdir(artifacts,{recursive:true});
 const page=await browser.newPage({viewport:{width:1280,height:960}});
 await page.addInitScript(()=>Object.defineProperty(window,'sessionStorage',{get(){throw new DOMException('Storage blocked','SecurityError');}}));
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto(url);
 assert.equal(await page.getByRole('heading',{name:'Living glossary'}).count(),1);
 await page.getByRole('button',{name:'New distinction'}).click();
 const fields={'Title':'Synthetic: signal / evidence','Distinction':'A signal suggests; evidence separates competing explanations.',
  'Discriminating example':'A second independent sensor separates a fault from a false alarm.',
  'Unresolved edge case':'The second sensor can share the same failure.',
  'Sources, one per line':'fixture:initial-source'};
 for(const [label,value] of Object.entries(fields))await page.getByLabel(label,{exact:true}).fill(value);
 let lost=false;
 await page.route('**/api/commons/glossary/distinctions',async route=>{
  if(!lost){lost=true;await route.fetch();await route.abort();}else await route.continue();
 });
 await page.getByRole('button',{name:'Save distinction',exact:true}).click();
 await page.getByText(/Save not confirmed/).waitFor();
 await page.getByRole('button',{name:'Save distinction',exact:true}).click();
 await page.getByText(/Saved.*entry_/).waitFor();
 assert.equal(await page.locator('#entries button').count(),1);
 const original=page.url().split('#')[1];
 await page.reload();await page.getByRole('heading',{name:fields.Title,exact:true}).waitFor();
 await page.getByRole('button',{name:'Record later use'}).click();
 await page.getByLabel('Situation',{exact:true}).fill('Synthetic: an alarm sounded.');
 await page.getByLabel('How the distinction was used',{exact:true}).fill('Checked an independent sensor first.');
 await page.getByLabel('Did it help?',{exact:true}).selectOption('unclear');
 await page.getByLabel('Sources, one per line',{exact:true}).fill('fixture:later-observation');
 await page.getByRole('button',{name:'Save application',exact:true}).click();
 await page.getByText(/Saved.*entry_/).waitFor();
 await page.getByRole('button',{name:'Open referenced distinction'}).click();
 await page.getByRole('button',{name:'Add refinement'}).click();
 await page.getByLabel('Title',{exact:true}).fill('Synthetic refined distinction');
 await page.getByRole('button',{name:'Save refinement',exact:true}).click();
 await page.getByText(/Saved.*entry_/).waitFor();
 await page.getByRole('button',{name:'Open referenced distinction'}).click();
 await page.waitForURL('**#'+original);
 assert.equal(page.url().split('#')[1],original);
 assert.match(await page.locator('#record').innerText(),/second sensor can share/);
 await page.setViewportSize({width:390,height:844});
 assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
 await page.screenshot({path:fileURLToPath(new URL('glossary-mobile.png',artifacts)),fullPage:true});
 await page.setViewportSize({width:1280,height:960});
 await page.screenshot({path:fileURLToPath(new URL('glossary-desktop.png',artifacts)),fullPage:true});
 await page.addScriptTag({url:new URL('/test-axe.js',url).href});
 const a11y=await page.evaluate(()=>axe.run());
 assert.deepEqual(a11y.violations.map(v=>({id:v.id,nodes:v.nodes.map(n=>n.target)})),[]);
 assert.deepEqual(errors,[]);
});
