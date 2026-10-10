import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import { readFile, mkdir } from 'node:fs/promises';
import { resolve } from 'node:path';
import { chromium } from 'playwright';

const root = resolve('mcp/memory/static');
const watchers = ['failed', 'stalled', 'late', 'ok', 'on-demand', 'unknown'].map((state, i) => ({
  key: `agent${i}@laptop`, agent: `agent${i}`, surface: 'laptop', monitor: i === 4 ? 'mention listener' : 'hourly sweep',
  state, age_minutes: i * 60, expected_every_minutes: i === 4 ? null : 60,
  source_refs: [`checkpoint_fixture_${i}`], receipt: state === 'failed' ? { process_exit: 1 } : {},
}));
const items = ['queued', 'claimed', 'running', 'review', 'blocked', 'done'].map((state, i) => ({
  id: `task_fixture_${i}`, title: ['Dashboard design', 'Memory audit', 'Fixture checks', 'Layout review', 'Missing receipt', 'Source reconciliation'][i],
  state, owner: 'codex', age_minutes: i * 30, source_refs: [`task_fixture_${i}`], age_basis: 'transition',
}));
const inbox = { total: 1, items: [{kind:'blocked', sender:'codex', label:'Missing receipt', body:'Review the failed runner receipt.',
  event_id:'$fixture', room_id:'!fixture:test', room:'Agent Tasks', age_minutes:140, source_refs:['$fixture']}], element_url:'https://hearth.test' };
const health = {knowledge_count:741,total_count:3057,noise_ratio:2316/3057,superseded_count:12,near_duplicate_pair_count:4,
  duplicate_coverage:{complete:false,scanned:250,total:741},source_refs:['drawer_fixture','drawer_other','drawer_unrelated'],
  metric_sources:{knowledge:['drawer_fixture','drawer_other'],noise:['drawer_fixture','drawer_other','drawer_unrelated'],superseded:['drawer_other']},near_duplicate_pairs:[['drawer_fixture','drawer_other']]};
const drawer={drawer_id:'drawer_fixture',wing:'Hearth',room:'design',record_class:'knowledge',content:'Fixture knowledge',is_current:true};
watchers.push({agent:'post-only',surface:'laptop',state:'unknown',source_refs:['$post_only'],last_post_room_id:'!source:test'});
let eventRoom;
let mode = 'normal';
const server = createServer(async (req,res) => {
  const path = new URL(req.url, 'http://local').pathname;
  if(path==='/api/activity/event')eventRoom=new URL(req.url,'http://local').searchParams.get('room_id');
  const api = {
    '/api/auth/status': {authenticated:true,principal:'fixture-human',auth_enabled:false},
    '/api/inbox': mode === 'empty' ? {...inbox,total:0,items:[]} : inbox,
    '/api/surfaces': {surfaces:[],watchers:mode==='empty'?[]:watchers},
    '/api/dashboard/work': {items:mode==='empty'?[]:items},
    '/api/dashboard/memory-health': mode==='empty'?{...health,knowledge_count:0,total_count:0,noise_ratio:0,superseded_count:0,near_duplicate_pair_count:0,duplicate_coverage:{complete:true,scanned:0,total:0},source_refs:[]}:health,
    '/api/taxonomy': {total_drawers:741,wings:[]},
    '/api/recent': {entries:mode==='empty'?[]:[drawer]}, '/api/health': {},
    '/api/drawer/drawer_fixture':drawer,
    '/api/activity/event':{event:{room_id:'!source:test',event_id:'$post_only',body:'Post-only evidence',sender:'fixture'},related:[]},
  };
  if (path.startsWith('/api/')) {
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
          await page.getByText('Failed',{exact:true}).waitFor();
          assert.equal(await page.locator('.watcher-row:visible').count(),3);
          await page.getByText('Event-driven and unconfirmed').click();
          await page.getByText('mention listener',{exact:true}).waitFor();
        }
        if(route==='work') await page.getByText('Queued',{exact:true}).first().waitFor();
        if(route==='memory') await page.getByText('Knowledge only',{exact:true}).waitFor();
        const contrast=await page.evaluate(()=>{
          const vars=getComputedStyle(document.documentElement);
          const luminance=hex=>{const rgb=hex.trim().replace('#','').match(/.{2}/g).map(v=>parseInt(v,16)/255).map(v=>v<=.04045?v/12.92:((v+.055)/1.055)**2.4);return rgb[0]*.2126+rgb[1]*.7152+rgb[2]*.0722;};
          const bg=luminance(vars.getPropertyValue('--card'));
          return ['--text','--dim','--accent','--warn','--bad'].map(v=>{const fg=luminance(vars.getPropertyValue(v));return (Math.max(bg,fg)+.05)/(Math.min(bg,fg)+.05);});
        });
        assert.ok(contrast.every(r=>r>=4.5),`Light text contrast below AA: ${contrast}`);
        if(process.env.SCREENSHOT_DIR) {await mkdir(process.env.SCREENSHOT_DIR,{recursive:true});await page.screenshot({path:resolve(process.env.SCREENSHOT_DIR,`${route}-${width}.png`),fullPage:true});}
      }
    }
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
    await page.getByRole('button',{name:'checkpoint_fixture_0',exact:true}).click();
    await page.locator('#detail').getByText('Failed',{exact:true}).waitFor();
    assert.match(await page.locator('#detail').textContent(),/process_exit/);
    await page.getByRole('button',{name:'Close details',exact:true}).click();
    await page.getByText('Event-driven and unconfirmed').click();
    await page.getByRole('button',{name:'$post_only',exact:true}).click();
    await page.getByText('Post-only evidence',{exact:true}).waitFor();
    assert.equal(eventRoom,'!source:test');
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
