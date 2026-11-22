import assert from 'node:assert/strict';
import {spawn} from 'node:child_process';
import {createInterface} from 'node:readline';
import {test} from 'node:test';
import {fileURLToPath} from 'node:url';
import {chromium} from 'playwright';

async function startPreview(t) {
  const child = spawn(process.env.HEARTH_TEST_PYTHON || 'python',
    [fileURLToPath(new URL('./glossary_preview.py', import.meta.url))],
    {windowsHide: true, stdio: ['ignore', 'pipe', 'pipe']});
  t.after(() => child.kill());
  let diagnostics = '';
  child.stderr.on('data', chunk => { diagnostics += chunk; });
  const lines = createInterface({input: child.stdout});
  t.after(() => lines.close());
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(Error('Preview startup timeout: ' + diagnostics)), 30000);
    child.once('error', reject);
    child.once('exit', () => { clearTimeout(timer); reject(Error('Preview exited: ' + diagnostics)); });
    lines.on('line', line => {
      if (line.startsWith('GLOSSARY_PREVIEW=')) {
        clearTimeout(timer);
        resolve(new URL(JSON.parse(line.slice(17)).url).origin);
      }
    });
  });
}

async function brief(origin, taskId) {
  const headers = {Authorization: 'Bearer fixture-codex', 'Content-Type': 'application/json',
    Accept: 'application/json, text/event-stream'};
  async function rpc(method, params, id) {
    const response = await fetch(origin + '/mcp', {method: 'POST', headers,
      body: JSON.stringify({jsonrpc: '2.0', method, params, id})});
    assert.ok(response.ok, 'MCP ' + method + ' returned ' + response.status);
    if (response.headers.has('mcp-session-id')) headers['mcp-session-id'] = response.headers.get('mcp-session-id');
    const body = await response.text();
    if (!body.trim() || id === undefined) return;
    const payload = response.headers.get('content-type').includes('text/event-stream')
      ? JSON.parse(body.split(/\r?\n/).find(line => line.startsWith('data:')).slice(5))
      : JSON.parse(body);
    assert.equal(payload.error, undefined);
    return payload.result;
  }
  await rpc('initialize', {protocolVersion: '2025-03-26', capabilities: {},
    clientInfo: {name: 'category-test', version: '1'}}, 1);
  await rpc('notifications/initialized', {});
  const result = await rpc('tools/call', {name: 'brief', arguments: {task_id: taskId}}, 2);
  assert.ok(!result.isError, result.content[0]?.text);
  return JSON.parse(result.content[0].text);
}

test('only a human can set the project category and brief inherits it after reload', async t => {
  const origin = await startPreview(t);
  const browser = await chromium.launch();
  t.after(() => browser.close());
  const page = await browser.newPage();
  page.setDefaultTimeout(5000);
  async function post(path, data) {
    const response = await page.request.post(origin + path, {data});
    assert.ok(response.ok(), await response.text());
    return response.json();
  }
  await post('/api/auth/login', {token: 'local-only-preview-admin'});
  for (const title of ['Mail trial', 'Other trial']) {
    await post('/api/work/projects', {title, goal: 'Exercise project categories'});
  }
  await page.goto(origin + '/#projects');
  const projects = page.getByRole('combobox', {name: 'Project', exact: true});
  await projects.waitFor();
  const target = await projects.locator('option:not(:checked)').first().getAttribute('value');
  await projects.selectOption(target);
  const task = await post('/api/work/projects/' + target + '/tasks',
    {title: 'Check mail', assignee: 'codex', acceptance: 'Confirm category'});
  assert.equal((await brief(origin, task.id)).category_question, 'Personal or Climate Central?');
  const category = page.getByLabel('Category', {exact: true});
  assert.equal(await category.inputValue(), '');
  for (const value of ['Personal', 'Climate Central']) {
    await category.selectOption(value);
    await page.getByText('Category saved', {exact: true}).waitFor();
    await page.reload();
    assert.equal(await projects.inputValue(), target);
    assert.equal(await category.inputValue(), value);
    const result = await brief(origin, task.id);
    assert.equal(result.category, value);
    assert.equal(result.category_question, null);
    assert.ok(!result.open_points.includes('category'));
  }
  const reader = await browser.newPage();
  await reader.request.get(origin + '/preview?as=codex');
  await reader.goto(origin + '/#projects');
  await reader.getByLabel('Project', {exact: true}).selectOption(target);
  await reader.getByText('Category: Climate Central', {exact: true}).waitFor();
  assert.equal(await reader.getByLabel('Category', {exact: true}).count(), 0);
  const denied = await reader.request.post(origin + '/api/work/projects/' + target + '/category',
    {data: {category: 'Personal'}});
  assert.equal(denied.status(), 403);
  assert.equal((await brief(origin, task.id)).category, 'Climate Central');
});
