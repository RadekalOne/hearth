import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import { readFile, mkdir, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import { chromium } from 'playwright';
import axe from 'axe-core';

const root = resolve('mcp/memory/static');
const watchers = ['failed', 'stalled', 'late', 'ok', 'on-demand', 'unknown'].map((state, i) => ({
  key: `agent${i}@laptop`, agent: `agent${i}`, surface: 'laptop', monitor: i === 4 ? 'mention listener' : 'hourly sweep',
  state, age_minutes: [2,240,120,30,10000,null][i], expected_every_minutes: i === 4 ? null : 60,
  source_refs: [i===5?'watcher_fixture_5':`checkpoint_fixture_${i}`], receipt: state === 'failed' ? { process_exit: 1 } : {},
}));
const items = ['queued', 'claimed', 'running', 'review', 'blocked', 'done'].map((state, i) => ({
  id: `task_fixture_${i}`, title: ['Dashboard design', 'Memory audit', 'Fixture checks', 'Layout review', 'Missing receipt', 'Source reconciliation'][i],
  state, owner: 'codex', age_minutes: i * 30, source_refs: [`task_fixture_${i}`], age_basis: 'transition',
}));
items.unshift(
  {id:'relay_overdue',title:'Review the dashboard design',state:'queued',owner:'codex',age_minutes:10000,source_refs:['relay_overdue'],age_basis:'relay state update'},
  {id:'relay_auth',title:'Investigate authorization receipts',state:'queued',owner:'codex',age_minutes:6000,source_refs:['relay_auth'],age_basis:'relay state update'},
);
const inbox = { total: 3, items: [
  {...watchers[0],kind:'failed_watcher',title:'agent0 / hourly sweep',body:'Latest runner receipt failed.',label:'Failed watcher needs attention'},
  {id:'relay_overdue',kind:'overdue_work',title:'Review the dashboard design',body:'Review the dashboard design',label:'Queued for more than 3 days',owner:'codex',state:'queued',state_since:'2026-10-01T00:00:00Z',age_minutes:10000,source_refs:['relay_overdue']},
  {kind:'blocked', sender:'codex', label:'Missing receipt', body:'Review the failed runner receipt.',event_id:'$fixture', room_id:'!fixture:test', room:'Agent Tasks', age_minutes:140, source_refs:['$fixture']}], element_url:'https://hearth.test' };
const health = {knowledge_count:741,total_count:3057,noise_ratio:2316/3057,superseded_count:12,near_duplicate_pair_count:4,
  duplicate_coverage:{complete:false,scanned:250,total:741},source_refs:['drawer_fixture','drawer_other','drawer_unrelated'],
  metric_sources:{knowledge:['drawer_fixture','drawer_other'],noise:['drawer_fixture','drawer_other','drawer_unrelated'],superseded:['drawer_other']},near_duplicate_pairs:[['drawer_fixture','drawer_other']]};
const drawer={drawer_id:'drawer_fixture',wing:'Hearth',room:'design',record_class:'knowledge',content:'Fixture knowledge',is_current:true};
let eventRoom;
let mode = 'normal';
let taxonomyWings = [];
let ackItems;let staleAck=false;
const server = createServer(async (req,res) => {
  const path = new URL(req.url, 'http://local').pathname;
  if(path==='/api/activity/event')eventRoom=new URL(req.url,'http://local').searchParams.get('room_id');
  const api = {
    '/api/auth/status': {authenticated:true,principal:'fixture-human',auth_enabled:false},
    '/api/inbox': mode === 'ack' ? {...inbox,items:ackItems,can_acknowledge:true,open_total:ackItems.filter(i=>!i.acknowledged).length,acknowledged_total:ackItems.filter(i=>i.acknowledged).length} : mode === 'empty' ? {...inbox,total:0,items:[]} : inbox,
    '/api/surfaces': {surfaces:[],watchers:mode==='empty'?[]:watchers},
    '/api/dashboard/work': {items:mode==='empty'?[]:items,counts:Object.fromEntries(['queued','claimed','running','review','blocked','done'].map(s=>[s,mode==='empty'?0:items.filter(i=>i.state===s).length]))},
    '/api/dashboard/memory-health': mode==='empty'?{...health,knowledge_count:0,total_count:0,noise_ratio:0,superseded_count:0,near_duplicate_pair_count:0,duplicate_coverage:{complete:true,scanned:0,total:0},source_refs:[]}:health,
    '/api/taxonomy': {total_drawers:741,wings:taxonomyWings},
    '/api/recent': {entries:mode==='empty'?[]:[drawer]}, '/api/health': {},
    '/api/drawer/drawer_fixture':drawer,
    '/api/activity/event':{event:{room_id:'!fixture:test',event_id:'$fixture',body:'Blocked item evidence',sender:'fixture'},related:[]},
  };
  if (path.startsWith('/api/')) {
    if(path==='/api/inbox/acknowledgement'&&req.method==='POST'){
      let body='';for await(const chunk of req)body+=chunk;
      const update=JSON.parse(body);const item=ackItems.find(i=>(i.id||i.event_id)===update.item_id);
      if(staleAck){res.writeHead(409,{'Content-Type':'application/json'});res.end('{"error":"Item changed"}');return;}
      assert.equal(update.state_key,item.state_key);item.acknowledged=update.acknowledged;item.acknowledged_by='fixture-human';item.acknowledged_at='2026-10-10T20:00:00Z';
      res.writeHead(200,{'Content-Type':'application/json'});res.end('{"ok":true}');return;
    }
    res.writeHead(mode==='error' && path!=='/api/auth/status' ? 503 : 200, {'Content-Type':'application/json'});
    res.end(JSON.stringify(api[path] || {})); return;
  }
  try {
    const file=path==='/'?'index.html':path.replace('/static/','');
    const content=await readFile(resolve(root,file));
    res.writeHead(200, {'Content-Type':file.endsWith('.js')?'text/javascript':file.endsWith('.css')?'text/css':'text/html'});res.end(content);
  } catch {res.writeHead(404);res.end();}
});

test('Now/Work/Memory fixtures, keyboard tabs and responsive layouts', async () => {
  await new Promise(r=>server.listen(0,'127.0.0.1',r));
  let browser;
  try {
    browser=await chromium.launch({headless:true});
    const page=await browser.newPage({colorScheme:'light'});
    const errors=[]; page.on('pageerror', e=>errors.push(e.message));
    await page.goto(`http://127.0.0.1:${server.address().port}/`);
    await page.getByRole('heading',{name:'Now',exact:true}).waitFor();
    assert.equal(await page.getByRole('tab',{name:'Now',exact:true}).getAttribute('class'),'active');
    for (const width of [400,1280]) {
      await page.setViewportSize({width,height:900});
      for(const route of ['now','work','memory']) {
        await page.goto(`http://127.0.0.1:${server.address().port}/#${route}`);
        await page.getByRole('heading',{name:route[0].toUpperCase()+route.slice(1),exact:true}).waitFor();
        assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,`${route} overflow at ${width}`);
        if(route==='now') {
          await page.locator('.watcher-row').getByText('Failed',{exact:true}).waitFor();
          assert.match(await page.locator('.takeaway').textContent(),/1 late watcher\./);
          await page.locator('.inbox-with-source').getByText('Review the dashboard design',{exact:true}).waitFor();
          assert.equal(await page.locator('.inbox-with-source').count(),3);
          assert.equal(await page.locator('.watcher-row:visible').count(),3);
          await page.getByText('Event-driven and unconfirmed').click();
          await page.getByText('mention listener',{exact:true}).waitFor();
        }
        if(route==='work') {
          await page.getByRole('button',{name:'Queued: 3',exact:true}).waitFor();
          await page.getByText('Investigate authorization receipts',{exact:true}).waitFor();
          assert.equal(await page.locator('.stage-counts button').count(),6);
          assert.equal(await page.getByText('Source reconciliation',{exact:true}).isVisible(),false);
          await page.getByText('1 done item',{exact:true}).click();
          await page.getByText('Source reconciliation',{exact:true}).waitFor();
          await page.getByText('1 done item',{exact:true}).click();
        }
        if(route==='memory') await page.getByText('Knowledge only',{exact:true}).waitFor();
        const contrast=await page.evaluate(()=>{
          const vars=getComputedStyle(document.documentElement);
          const luminance=hex=>{const rgb=hex.trim().replace('#','').match(/.{2}/g).map(v=>parseInt(v,16)/255).map(v=>v<=.04045?v/12.92:((v+.055)/1.055)**2.4);return rgb[0]*.2126+rgb[1]*.7152+rgb[2]*.0722;};
          const bg=luminance(vars.getPropertyValue('--card'));
          return Object.fromEntries(['--text','--dim','--accent','--warn','--bad','--control-border'].map(v=>{const fg=luminance(vars.getPropertyValue(v));return [v,(Math.max(bg,fg)+.05)/(Math.min(bg,fg)+.05)];}));
        });
        assert.ok(Object.entries(contrast).every(([v,r])=>r>=(v==='--control-border'?3:4.5)),`Light contrast below AA: ${JSON.stringify(contrast)}`);
        await page.addScriptTag({content:axe.source});
        const audit=await page.evaluate(async()=>await axe.run(document.querySelector('#dashboard'),{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21aa','wcag22aa']}}));
        assert.deepEqual(audit.violations.map(v=>({id:v.id,nodes:v.nodes.map(n=>n.target)})),[],`${route} light theme AA violations`);
        if(process.env.SCREENSHOT_DIR) {
          await mkdir(process.env.SCREENSHOT_DIR,{recursive:true});
          await page.screenshot({path:resolve(process.env.SCREENSHOT_DIR,`${route}-${width}.png`),fullPage:true});
          await writeFile(resolve(process.env.SCREENSHOT_DIR,`${route}-${width}-audit.json`),JSON.stringify({route,width,theme:'light',engine:audit.testEngine,violations:audit.violations,contrast},null,2));
        }
      }
    }
    const originalTitle=inbox.items[1].title;
    inbox.items[1].title='Interactive Codex: inspect task '+ '$'+'a'.repeat(64);
    for(const width of [375,400]) {
      await page.setViewportSize({width,height:900});
      await page.goto(`http://127.0.0.1:${server.address().port}/#now`);
      await page.getByText(inbox.items[1].title,{exact:true}).waitFor();
      assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,`Long handoff evidence id overflow at ${width}`);
    }
    inbox.items[1].title=originalTitle;
    await page.getByRole('tab',{name:'Now',exact:true}).focus();
    await page.keyboard.press('ArrowRight');
    assert.equal(await page.evaluate(()=>document.activeElement.textContent),'Work');
    await page.keyboard.press('Enter');
    await page.getByRole('heading',{name:'Work',exact:true}).waitFor();
    // Immediate authentication must wait for delayed route registration.
    await page.route('**/static/slice.js',async route=>{await new Promise(r=>setTimeout(r,500));await route.continue();});
    await page.goto(`http://127.0.0.1:${server.address().port}/#now`);
    await page.getByRole('heading',{name:'Now',exact:true}).waitFor({timeout:3000});
    await page.unroute('**/static/slice.js');
    await page.locator('.watcher-row').getByRole('button',{name:'checkpoint_fixture_0',exact:true}).click();
    await page.locator('#detail').getByText('Failed',{exact:true}).waitFor();
    assert.match(await page.locator('#detail').textContent(),/process_exit/);
    await page.getByRole('button',{name:'Close details',exact:true}).click();
    await page.getByRole('button',{name:'$fixture',exact:true}).click();
    await page.getByText('Blocked item evidence',{exact:true}).waitFor();
    assert.equal(eventRoom,'!fixture:test');
    taxonomyWings = Array.from({length:30}, (_,i)=>({wing:`Project ${i}`,total:10,classes:{knowledge:10},rooms:[]}));
    for(const width of [375,400,900]) {
      await page.setViewportSize({width,height:900});
      await page.goto(`http://127.0.0.1:${server.address().port}/#memory`);
      await page.reload();
      await page.locator('.palace .wing').nth(30).waitFor();
      await page.getByRole('button',{name:'Search',exact:true}).click({timeout:3000});
      await page.getByText('Newest 1 drawer',{exact:true}).waitFor();
    }
    taxonomyWings = [];
    await page.goto(`http://127.0.0.1:${server.address().port}/#memory`);
    await page.setViewportSize({width:400,height:900});
    await page.locator('.drawer').waitFor();
    await page.getByRole('button',{name:'Search',exact:true}).click();
    await page.getByText('Newest 1 drawer',{exact:true}).waitFor();
    assert.equal(await page.locator('.drawer').getAttribute('tabindex'),'0');
    await page.locator('.drawer').focus();await page.keyboard.press('Enter');
    await page.locator('#detail .content').getByText('Fixture knowledge',{exact:true}).waitFor();
    await page.locator('#detail .close').click();
    await page.getByRole('button',{name:'show superseded',exact:true}).focus();
    await page.keyboard.press('Space');
    assert.equal(await page.getByRole('button',{name:'show superseded',exact:true}).getAttribute('aria-pressed'),'true');
    await page.locator('.drawer').waitFor();
    assert.equal(await page.locator('.drawer').getAttribute('tabindex'),'0');
    await page.getByRole('button',{name:'View source drawers',exact:true}).nth(3).click();
    await page.locator('#detail').getByRole('button',{name:'drawer_other',exact:true}).waitFor();
    assert.equal(await page.locator('#detail').getByText('drawer_unrelated',{exact:true}).count(),0);
    mode='ack';ackItems=inbox.items.map((i,n)=>({...i,state_key:`fixture-${n}`,acknowledged:n===0,acknowledged_by:n===0?'fixture-human':null,acknowledged_at:n===0?'2026-10-10T20:00:00Z':null}));
    for(const width of [400,1280]) {
      await page.setViewportSize({width,height:900});
      await page.goto(`http://127.0.0.1:${server.address().port}/#now`);await page.reload();
      await page.getByText('Acknowledged (1)',{exact:true}).waitFor();
      assert.match(await page.locator('.takeaway').textContent(),/2 items waiting · 1 acknowledged/);
      assert.equal(await page.locator('.inbox-item .actions button').filter({hasText:'Acknowledge'}).count(),2);
      assert.equal(await page.locator('.inbox-with-source .source-refs').first().getByText('Evidence ids:',{exact:true}).count(),1);
      assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
      if(process.env.SCREENSHOT_DIR)await page.screenshot({path:resolve(process.env.SCREENSHOT_DIR,`now-acknowledged-${width}.png`),fullPage:true});
    }
    await page.getByText('Acknowledged (1)',{exact:true}).click();
    await page.getByText('Acknowledged by fixture-human',{exact:false}).waitFor();
    if(process.env.SCREENSHOT_DIR)await page.screenshot({path:resolve(process.env.SCREENSHOT_DIR,'now-expanded-1280.png'),fullPage:true});
    await page.getByRole('button',{name:'Reopen',exact:true}).click();
    await page.getByRole('button',{name:'Acknowledge',exact:true}).nth(2).waitFor();
    assert.equal(await page.getByText('Acknowledged (1)',{exact:true}).count(),0);
    staleAck=true;await page.getByRole('button',{name:'Acknowledge',exact:true}).first().click();
    await page.getByText('This item changed. Refresh before acknowledging or reopening it.',{exact:true}).waitFor();
    if(process.env.SCREENSHOT_DIR)await page.screenshot({path:resolve(process.env.SCREENSHOT_DIR,'now-stale-1280.png'),fullPage:true});
    staleAck=false;await page.getByRole('button',{name:'Acknowledge',exact:true}).first().focus();
    if(process.env.SCREENSHOT_DIR)await page.screenshot({path:resolve(process.env.SCREENSHOT_DIR,'now-keyboard-focus-1280.png'),fullPage:true});
    await page.keyboard.press('Enter');
    await page.getByText('Acknowledged (1)',{exact:true}).waitFor();
    for (mode of ['empty','error']) {
      for(const route of ['now','work','memory']) {
        await page.goto(`http://127.0.0.1:${server.address().port}/#${route}`);
        await page.getByRole('heading',{name:route[0].toUpperCase()+route.slice(1),exact:true}).waitFor();
        if(mode==='error') await page.getByText('Failed to load',{exact:true}).first().waitFor();
        assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
        if(process.env.SCREENSHOT_DIR) await page.screenshot({path:resolve(process.env.SCREENSHOT_DIR,`${route}-${mode}.png`),fullPage:true});
      }
    }
    assert.deepEqual(errors,[]);
  } finally {if(browser)await browser.close();server.closeAllConnections();await new Promise(r=>server.close(r));mode='normal';}
});
