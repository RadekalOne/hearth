import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { shouldReply, handleEvent, claimEvent, completion, requestJSON, PROVIDER, run } from '../integrations/openrouter/agent.mjs';
import { validateAgent, checkBudget, register, provision } from '../installer/windows/openrouter.mjs';

const config = { name: 'helper', model: 'provider/model', key: 'test-not-a-real-key', humanId: '@human:test', userId: '@or-helper:test' };
const now = Date.now();
const event = (overrides = {}) => ({ event_id: '$one', type: 'm.room.message', sender: config.humanId,
  origin_server_ts: now, content: { msgtype: 'm.text', body: '@helper hello' }, ...overrides });

test('only direct human mentions wake the test agent', () => {
  assert.equal(shouldReply(event(), config, now), true);
  for (const change of [
    { sender: config.userId }, { sender: '@someone-else:test' }, { type: 'm.room.encrypted' },
    { origin_server_ts: now - 300001 }, { origin_server_ts: now + 60000 },
    { content: { msgtype: 'm.text', body: '@helper2 hello' } },
    { content: { msgtype: 'm.text', body: 'quoted @helper hello' } },
    { content: { msgtype: 'm.text', body: '@helper hello', 'm.mentions': { room: true, user_ids: [config.userId] } } },
    { content: { msgtype: 'm.text', body: '@helper hello', 'm.mentions': { user_ids: [] } } },
    { content: { msgtype: 'm.text', body: '@helper edited', 'm.relates_to': { rel_type: 'm.replace' } } },
  ]) assert.equal(shouldReply(event(change), config, now), false, JSON.stringify(change));
  assert.equal(shouldReply(event({ content: { msgtype: 'm.text', body: 'hello helper', 'm.mentions': { user_ids: [config.userId] } } }), config, now), true);
});

test('event is persisted before billing and cannot be billed twice after restart', async () => {
  let disk, calls = 0, sent = 0;
  const state = {};
  const options = { now, save: () => { disk = JSON.stringify(state); },
    generate: async () => { assert.ok(JSON.parse(disk).processed.includes('$one')); calls++; return 'hello'; },
    send: async (txn, body) => { assert.equal(txn.length, 64); assert.equal(body.body, 'hello'); sent++; } };
  assert.equal(await handleEvent(event(), config, state, options), true);
  assert.equal(await handleEvent(event(), config, JSON.parse(disk), { ...options, now: now + 11000 }), false);
  assert.equal(calls, 1); assert.equal(sent, 1);
});

test('failed model request produces a safe reply once and no retry', async () => {
  let calls = 0, body;
  const state = {};
  const options = { now, save() {}, generate: async () => { calls++; throw new Error('SECRET-KEY'); }, send: async (_, value) => { body = value; } };
  await handleEvent(event(), config, state, options);
  await handleEvent(event(), config, state, options);
  assert.equal(calls, 1); assert.doesNotMatch(body.body, /SECRET/); assert.match(body.body, /No automatic retry/);
});

test('sync skips initial history, isolates the test room and resumes its cursor', async () => {
  const folder = fs.mkdtempSync(path.join(os.tmpdir(), 'hearth-or-sync-'));
  const stateFile = path.join(folder, 'status.json');
  const agent = { ...config, roomId: '!test:local' };
  let polls = 0, replies = 0, generations = 0;
  const matrixRequest = async (suffix, options) => {
    if (suffix.startsWith('/rooms/')) {
      assert.match(suffix, /^\/rooms\/!test%3Alocal\/send\/m.room.message\//);
      replies++; return {};
    }
    const query = new URL('http://local' + suffix).searchParams;
    assert.deepEqual(JSON.parse(query.get('filter')).room.rooms, [agent.roomId]);
    if (polls === 0) assert.equal(query.has('since'), false);
    else assert.equal(query.get('since'), 'cursor-' + polls);
    polls++;
    return { next_batch: 'cursor-' + polls, rooms: { join: {
      [agent.roomId]: { timeline: { events: [event({ event_id: polls === 1 ? '$history' : '$new' })] } },
      '!other:local': { timeline: { events: [event({ event_id: '$other' })] } },
    } } };
  };
  const generate = async () => { generations++; return 'hello'; };
  try {
    await run(agent, stateFile, { maxPolls: 2, matrixRequest, generate });
    assert.equal(generations, 1); assert.equal(replies, 1);
    assert.equal(JSON.parse(fs.readFileSync(stateFile, 'utf8')).status, 'ready');
    await run(agent, stateFile, { maxPolls: 1, matrixRequest, generate });
    assert.equal(generations, 1); assert.equal(replies, 1);
    assert.equal(JSON.parse(fs.readFileSync(stateFile, 'utf8')).cursor, 'cursor-3');
  } finally { fs.rmSync(folder, { recursive: true, force: true }); }
});

test('daily and cooldown limits survive reloading state', () => {
  let state = {};
  assert.equal(claimEvent(state, event(), now), true);
  assert.equal(claimEvent(state, event({ event_id: '$too-fast' }), now + 1), false);
  for (let i = 1; i < 20; i++) {
    state = JSON.parse(JSON.stringify(state));
    assert.equal(claimEvent(state, event({ event_id: '$' + i }), now + i * 10000), true);
  }
  assert.equal(claimEvent(state, event({ event_id: '$over-limit' }), now + 200000), false);
  assert.equal(claimEvent(state, event({ event_id: '$tomorrow' }), now + 86400000), true);
});

test('OpenRouter requests are bounded, private, and contain no tools or Hearth credentials', async () => {
  const answer = await completion({ ...config, token: 'MATRIX-SECRET' }, 'x'.repeat(8000), async (url, options) => {
    assert.equal(url, 'https://openrouter.ai/api/v1/chat/completions');
    assert.equal(options.redirect, 'error');
    const body = JSON.parse(options.body);
    assert.deepEqual(body.provider, PROVIDER);
    assert.equal(body.messages[1].content.length, 4000);
    assert.equal(body.max_tokens, 512);
    assert.equal(body.tools, undefined);
    assert.doesNotMatch(options.body, /MATRIX-SECRET/);
    return { ok: true, json: async () => ({ choices: [{ message: { content: 'connected' } }] }) };
  });
  assert.equal(answer, 'connected');
  await assert.rejects(requestJSON('https://example.test', {}, async () => ({ ok: false, status: 401, json: () => { throw new Error('must not read secret-bearing error body'); } })), /HTTP 401/);
});

test('agent input and API-key budget checks fail closed', () => {
  assert.doesNotThrow(() => validateAgent(config));
  for (const name of ['../escape', 'UPPER', '-option', '']) assert.throws(() => validateAgent({ ...config, name }));
  for (const model of ['', 'https://evil.test', '../model', 'provider/model\n']) assert.throws(() => validateAgent({ ...config, model }));
  for (const data of [{}, { limit: null }, { limit: 10 }, { limit: 0 }, { limit: 5, limit_remaining: 0 }, { limit: 5, limit_remaining: 5, is_management_key: true }])
    assert.throws(() => checkBudget(data));
  assert.doesNotThrow(() => checkBudget({ limit: 5, limit_remaining: 4.99 }));
});

test('Matrix registration handles registration-token auth without leaking it', async () => {
  const calls = [];
  const result = await register(async (url, options) => {
    calls.push(options.body);
    return calls.length === 1 ? { session: 'session', flows: [{ stages: ['m.login.registration_token'] }] } : { user_id: '@or-helper:test', access_token: 'matrix-token' };
  }, 'or-helper', 'random-password', 'registration-secret');
  assert.equal(result.access_token, 'matrix-token');
  assert.equal(calls[1].auth.token, 'registration-secret');
  assert.equal(calls[1].auth.session, 'session');
});

test('provisioning creates one private account and room and safely resumes', async () => {
  const target = fs.mkdtempSync(path.join(os.tmpdir(), 'hearth-or-setup-'));
  fs.mkdirSync(path.join(target, 'secrets'));
  fs.writeFileSync(path.join(target, 'hearth.config.json'), JSON.stringify({ mode: 'local', ports: { matrix: 6167, memory: 8010 }, serverName: 'test' }));
  fs.writeFileSync(path.join(target, '.env'), 'HEARTH_REGISTRATION_TOKEN=reg\n');
  fs.writeFileSync(path.join(target, 'secrets/admin.env'), 'MATRIX_ACCESS_TOKEN=admin-secret\nMATRIX_USER_ID=@human:test\n');
  const previousFetch = globalThis.fetch;
  const calls = [];
  globalThis.fetch = async (url, options) => {
    calls.push({ url, options });
    let value = {};
    if (url.endsWith('/register')) value = { access_token: 'bot-secret', user_id: config.userId };
    if (url.endsWith('/createRoom')) {
      const body = JSON.parse(options.body);
      assert.equal(body.preset, 'private_chat'); assert.deepEqual(body.invite, [config.userId]);
      value = { room_id: '!private:test' };
    }
    return { ok: true, json: async () => value };
  };
  try {
    const first = await provision(target, config);
    assert.equal(first.roomId, '!private:test');
    assert.equal(first.humanId, config.humanId);
    assert.equal(first.matrixUrl, 'http://conduit:6167');
    const second = await provision(target, { ...config, model: 'provider/new' });
    assert.equal(second.model, 'provider/new');
    assert.equal(calls.filter(call => call.url.endsWith('/register')).length, 1);
    assert.equal(calls.filter(call => call.url.endsWith('/createRoom')).length, 1);
    assert.ok(calls.every(call => !call.options.body?.includes(config.key)));
    assert.doesNotMatch(fs.readFileSync(path.join(target, 'secrets/openrouter/agent.json'), 'utf8'), /admin-secret|reg"/);
    await assert.rejects(provision(target, { ...config, name: 'other' }), /one test agent/);
  } finally { globalThis.fetch = previousFetch; fs.rmSync(target, { recursive: true, force: true }); }
});
