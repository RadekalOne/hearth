import fs from 'node:fs';
import path from 'node:path';
import { randomBytes } from 'node:crypto';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { checkTarget, preflight } from './runner.mjs';
import { completion, requestJSON } from '../../integrations/openrouter/agent.mjs';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
export function validateAgent(input) {
  if (!/^[a-z][a-z0-9_-]{0,23}$/.test(input.name || '')) throw new Error('Name your agent using 1–24 lowercase letters, numbers, dashes or underscores, starting with a letter.');
  if (!/^[a-zA-Z0-9][a-zA-Z0-9._-]*\/[a-zA-Z0-9][a-zA-Z0-9._:/-]*$/.test(input.model || '') || /[\r\n]/.test(input.model) || input.model.length > 160)
    throw new Error('Choose a model from the list, or enter its full provider/model ID.');
  if (typeof input.key !== 'string' || input.key.length < 16 || input.key.length > 512 || /\s/.test(input.key))
    throw new Error('Paste your OpenRouter API key into the key box.');
}
export function checkBudget(data) {
  if (!data || data.is_management_key || !Number.isFinite(data.limit) || data.limit <= 0 || data.limit > 5)
    throw new Error('For this test, create an OpenRouter key with a spending limit of $5 or less. Use that key here.');
  if (!Number.isFinite(data.limit_remaining) || data.limit_remaining <= 0)
    throw new Error('This key has no remaining spending allowance. Check it in OpenRouter.');
}
function envFile(file) {
  return Object.fromEntries(fs.readFileSync(file, 'utf8').split(/\r?\n/).flatMap(line => {
    const match = line.match(/^([A-Z_]+)=(.*)$/); return match ? [[match[1], match[2]]] : [];
  }));
}
function secretWrite(file, value) {
  fs.writeFileSync(file, JSON.stringify(value), { mode: 0o600 });
}
function compose(target, args) {
  const directory = path.join(target, 'integrations/openrouter');
  const list = spawnSync('docker', ['ps', '-aq', '--filter', 'label=com.docker.compose.project=hearth-openrouter-preview'], { windowsHide: true, encoding: 'utf8', timeout: 20000 });
  if (list.status !== 0) throw new Error('Docker is not ready. Open Docker Desktop and retry.');
  if (list.stdout.trim()) {
    const inspect = spawnSync('docker', ['inspect', ...list.stdout.trim().split(/\s+/)], { windowsHide: true, encoding: 'utf8', timeout: 20000 });
    if (inspect.status !== 0) throw new Error('Could not check the existing agent. Retry after Docker is ready.');
    if (JSON.parse(inspect.stdout).some(container => {
      const location = container.Config?.Labels?.['com.docker.compose.project.working_dir'];
      return !location || path.resolve(location).toLowerCase() !== path.resolve(directory).toLowerCase();
    })) throw new Error('Another installation owns the OpenRouter test container. This wizard will not change it.');
  }
  const result = spawnSync('docker', ['compose', '--project-name', 'hearth-openrouter-preview', '--project-directory', directory, '-f', path.join(directory, 'compose.yml'), ...args], {
    cwd: target, windowsHide: true, encoding: 'utf8', timeout: 180000,
  });
  if (result.error || result.status !== 0) throw new Error('Docker could not finish the agent action. Check Docker Desktop and your internet connection, then retry.');
}
export async function register(matrix, username, password, registrationToken) {
  let auth;
  for (let i = 0; i < 4; i++) {
    const response = await matrix('/register', { method: 'POST', body: { username, password, initial_device_display_name: 'Hearth OpenRouter test', ...(auth ? { auth } : {}) }, challenge: true });
    if (response.access_token) return response;
    if (!response.session) break;
    const next = (response.flows || []).flatMap(flow => flow.stages || []).find(stage => !(response.completed || []).includes(stage));
    if (!['m.login.dummy', 'm.login.registration_token'].includes(next)) break;
    auth = { type: next, session: response.session, ...(next === 'm.login.registration_token' ? { token: registrationToken } : {}) };
  }
  throw new Error('Could not create the test account. Choose a different agent name or ask for help.');
}
export async function provision(target, input) {
  const hub = JSON.parse(fs.readFileSync(path.join(target, 'hearth.config.json'), 'utf8'));
  if (hub.mode !== 'local' || ![6167, '6167'].includes(hub.ports?.matrix) || ![8010, '8010'].includes(hub.ports?.memory))
    throw new Error('This preview needs the local hub installed with the wizard defaults.');
  const env = envFile(path.join(target, '.env'));
  const admin = envFile(path.join(target, 'secrets/admin.env'));
  const folder = path.join(target, 'secrets/openrouter');
  fs.mkdirSync(folder, { recursive: true });
  // Restrict newly saved credentials to this Windows user and SYSTEM.
  if (process.platform === 'win32') {
    const identity = spawnSync('whoami', ['/user', '/fo', 'csv', '/nh'], { encoding: 'utf8', windowsHide: true });
    const sid = identity.stdout?.match(/S-1-5-[0-9-]+/)?.[0];
    if (!sid) throw new Error('Windows could not identify the account for private key storage.');
    const acl = spawnSync('icacls', [folder, '/inheritance:r', '/grant:r', `*${sid}:(OI)(CI)F`, '*S-1-5-18:(OI)(CI)F'], { windowsHide: true, encoding: 'utf8' });
    if (acl.status !== 0) throw new Error('Windows could not protect the API key folder.');
  }
  const stateFile = path.join(folder, 'setup.json');
  const saved = fs.existsSync(stateFile) ? JSON.parse(fs.readFileSync(stateFile, 'utf8')) : {};
  if (saved.name && saved.name !== input.name) throw new Error('This preview supports one test agent. Keep its original name to reconnect or change the model.');
  const persist = () => secretWrite(stateFile, saved);
  const base = 'http://127.0.0.1:6167/_matrix/client/v3';
  const matrix = async (suffix, { token = admin.MATRIX_ACCESS_TOKEN, body, method = body ? 'POST' : 'GET', challenge = false } = {}) => {
    const response = await fetch(base + suffix, { method, redirect: 'error', signal: AbortSignal.timeout(15000),
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' }, ...(body ? { body: JSON.stringify(body) } : {}) });
    if (!response.ok && !(challenge && response.status === 401)) throw new Error(`Hearth account setup failed (HTTP ${response.status}). Retry with the same agent name.`);
    return response.json();
  };
  const account = 'or-' + input.name;
  if (!saved.password && !saved.token) { saved.name = input.name; saved.password = randomBytes(32).toString('base64url'); persist(); }
  if (!saved.token) {
    let credentials;
    try { credentials = await register(matrix, account, saved.password, env.HEARTH_REGISTRATION_TOKEN); }
    catch {
      credentials = await matrix('/login', { body: { type: 'm.login.password', identifier: { type: 'm.id.user', user: account }, password: saved.password } });
    }
    saved.token = credentials.access_token; saved.userId = credentials.user_id;
    if (!saved.token || !saved.userId) throw new Error('Hearth did not return account credentials.');
    delete saved.password; persist();
  }
  const alias = 'openrouter-test-' + input.name;
  if (!saved.roomId) {
    try {
      const room = await matrix('/createRoom', { body: { room_alias_name: alias, name: 'OpenRouter test - ' + input.name,
        preset: 'private_chat', visibility: 'private', invite: [saved.userId],
        topic: 'Private OpenRouter test. Mention the agent to get a reply. Each message is independent; shared memory is not enabled.' } });
      saved.roomId = room.room_id;
    } catch {
      const room = await matrix('/directory/room/' + encodeURIComponent(`#${alias}:${hub.serverName}`));
      saved.roomId = room.room_id;
      // Do not attach to an unrelated room with a coincidentally matching alias.
      const creator = await matrix(`/rooms/${encodeURIComponent(saved.roomId)}/state/m.room.create`);
      if (creator.creator !== admin.MATRIX_USER_ID) throw new Error('The test room alias belongs to another account. Ask for help.');
    }
    persist();
  }
  await matrix('/join/' + encodeURIComponent(saved.roomId), { token: saved.token, body: {} });
  await matrix('/profile/' + encodeURIComponent(saved.userId) + '/displayname', { token: saved.token, method: 'PUT', body: { displayname: input.name } });
  const config = { name: input.name, model: input.model, key: input.key, token: saved.token, userId: saved.userId,
    humanId: admin.MATRIX_USER_ID, roomId: saved.roomId, matrixUrl: 'http://conduit:6167' };
  secretWrite(path.join(folder, 'agent.json'), config);
  return config;
}
async function main() {
  let raw = '';
  for await (const part of process.stdin) { raw += part; if (raw.length > 8192) throw new Error('Input is too large.'); }
  const input = JSON.parse(raw);
  if (input.action === 'models') {
    const result = await requestJSON('https://openrouter.ai/api/v1/models');
    const models = (result.data || []).filter(m => m.architecture?.output_modalities?.includes('text') && /^[a-zA-Z0-9._-]+\/[a-zA-Z0-9._:/-]+$/.test(m.id))
      .map(m => ({ id: m.id, name: m.name })).sort((a, b) => a.name.localeCompare(b.name));
    return { ok: true, models, message: 'Choose a text model. Availability under private routing is checked by Test reply.' };
  }
  if (input.action === 'test') {
    validateAgent(input);
    checkBudget((await requestJSON('https://openrouter.ai/api/v1/key', { token: input.key })).data);
    await completion(input, 'Reply with a short greeting confirming that this test connection works.');
    return { ok: true, message: 'The model replied successfully. You can now start the agent in your private test room.' };
  }
  const target = path.join(process.env.LOCALAPPDATA, 'Hearth/hub');
  if (!checkTarget(target)) throw new Error('Install Hearth with the Windows wizard first.');
  if (input.action === 'stop') {
    compose(target, ['stop', 'agent']); return { ok: true, message: 'Agent stopped. Your chat, account and settings are kept.' };
  }
  if (input.action !== 'connect') throw new Error('Unknown agent action.');
  validateAgent(input);
  if (input.consent !== true) throw new Error('Confirm that messages sent to this agent go to OpenRouter and the selected provider.');
  await preflight(target);
  checkBudget((await requestJSON('https://openrouter.ai/api/v1/key', { token: input.key })).data);
  fs.mkdirSync(path.join(target, 'integrations/openrouter'), { recursive: true });
  for (const name of ['agent.mjs', 'compose.yml']) fs.copyFileSync(path.join(root, 'integrations/openrouter', name), path.join(target, 'integrations/openrouter', name));
  // Stop an existing runner before replacing its credentials or model.
  if (fs.existsSync(path.join(target, 'secrets/openrouter/agent.json'))) compose(target, ['stop', 'agent']);
  const config = await provision(target, input);
  fs.mkdirSync(path.join(target, 'data/openrouter'), { recursive: true });
  const startedAt = Date.now();
  compose(target, ['up', '-d', '--force-recreate', 'agent']);
  for (let attempt = 0; attempt < 40; attempt++) {
    try {
      const status = JSON.parse(fs.readFileSync(path.join(target, 'data/openrouter/status.json'), 'utf8'));
      if (status.status === 'ready' && status.updatedAt >= startedAt) return { ok: true,
        roomUrl: 'http://localhost:8009/#/room/' + encodeURIComponent(config.roomId),
        message: `Connected! Open the test room and type @${config.name} hello. Keep Docker running. Limit: 20 attempts per UTC day, at least 10 seconds apart.` };
    } catch {}
    await new Promise(resolve => setTimeout(resolve, 1000));
  }
  throw new Error('The agent started but has not connected to the test room yet. Check Docker Desktop, then retry.');
}
if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main().then(result => console.log(JSON.stringify(result))).catch(error => {
    console.log(JSON.stringify({ ok: false, message: error.message })); process.exitCode = 1;
  });
}
