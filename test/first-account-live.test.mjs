// Opt in: HEARTH_LIVE_DOCKER_TEST=1 node --test test/first-account-live.test.mjs
import test from 'node:test';
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { randomBytes } from 'node:crypto';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { provision } from '../installer/windows/openrouter.mjs';

const repo = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
function command(file, args, options) {
  return new Promise(resolve => {
    const child = spawn(file, args, { windowsHide: true, stdio: 'ignore', ...options });
    child.once('error', () => resolve(-1));
    child.once('close', resolve);
  });
}
test('fresh Docker hub completes bootstrap registration, rooms, observer and repeat install', {
  skip: process.env.HEARTH_LIVE_DOCKER_TEST !== '1', timeout: 300000,
}, async () => {
  const folder = fs.mkdtempSync(path.join(os.tmpdir(), 'hearth-bootstrap-test-'));
  const hub = path.join(folder, 'hub');
  const project = 'hearth-bootstrap-test-' + randomBytes(5).toString('hex');
  const env = { ...process.env, COMPOSE_PROJECT_NAME: project, HEARTH_ADMIN_PASSWORD: randomBytes(24).toString('base64url') };
  delete env.HEARTH_ROOT;
  const deployment = path.join(folder, 'deployment.json');
  fs.writeFileSync(deployment, JSON.stringify({ mode: 'local', serverName: 'bootstrap.localhost', adminUsername: 'testadmin',
    ports: { matrix: 16168, element: 18019, memory: 18020 } }));
  try {
    const args = [path.join(repo, 'cli/create-hearth.mjs'), '--directory', hub, '--yes', '--config', deployment];
    assert.equal(await command(process.execPath, args, { cwd: folder, env }), 0, 'Fresh install must complete');
    const cfg = JSON.parse(fs.readFileSync(path.join(hub, 'hearth.config.json'), 'utf8'));
    assert.equal(Object.keys(cfg.rooms).length, 4);
    for (const name of ['admin.env', 'dashboard.env']) {
      assert.match(fs.readFileSync(path.join(hub, 'secrets', name), 'utf8'), /MATRIX_ACCESS_TOKEN=.+/);
    }
    const adminBefore = fs.readFileSync(path.join(hub, 'secrets/admin.env'), 'utf8');
    assert.equal(await command(process.execPath, args, { cwd: folder, env }), 0, 'Repeat install must complete');
    assert.equal(fs.readFileSync(path.join(hub, 'secrets/admin.env'), 'utf8'), adminBefore);
    assert.deepEqual(JSON.parse(fs.readFileSync(path.join(hub, 'hearth.config.json'), 'utf8')).rooms, cfg.rooms);
    const response = await fetch('http://127.0.0.1:18020/health', { signal: AbortSignal.timeout(10000) });
    const health = await response.json();
    assert.equal(health.memory, 'ok');
    const agent = await provision(hub, { name: 'testhelper', model: 'provider/test', key: 'nonfunctional-local-test-key' });
    assert.equal(agent.userId, '@or-testhelper:bootstrap.localhost');
    const retryAgent = await provision(hub, { name: 'testhelper', model: 'provider/test', key: 'nonfunctional-local-test-key' });
    assert.equal(retryAgent.roomId, agent.roomId);
    const integration = path.join(hub, 'integrations/openrouter');
    fs.mkdirSync(integration, { recursive: true });
    fs.mkdirSync(path.join(hub, 'data/openrouter'), { recursive: true });
    fs.copyFileSync(path.join(repo, 'integrations/openrouter/agent.mjs'), path.join(integration, 'agent.mjs'));
    fs.writeFileSync(path.join(integration, 'compose.yml'), fs.readFileSync(path.join(repo, 'integrations/openrouter/compose.yml'), 'utf8').replace('name: hearth_default', `name: ${project}_default`));
    assert.equal(await command('docker', ['compose', '--project-name', project + '-agent', 'up', '-d'], { cwd: integration, env }), 0);
    let connected = false;
    for (let attempt = 0; attempt < 40; attempt++) {
      try { connected = JSON.parse(fs.readFileSync(path.join(hub, 'data/openrouter/status.json'), 'utf8')).status === 'ready'; } catch {}
      if (connected) break;
      await new Promise(resolve => setTimeout(resolve, 1000));
    }
    assert.equal(connected, true, 'Real agent container must connect to its private room without a model call');
  } finally {
    // Delete only this test's randomly named Compose project and temp directory.
    if (fs.existsSync(path.join(hub, 'docker-compose.yml'))) {
      assert.match(project, /^hearth-bootstrap-test-[a-f0-9]{10}$/);
      if (fs.existsSync(path.join(hub, 'integrations/openrouter/compose.yml'))) {
        await command('docker', ['compose', '--project-name', project + '-agent', 'down'], { cwd: path.join(hub, 'integrations/openrouter'), env });
      }
      await command('docker', ['compose', '--project-name', project, 'down', '--volumes'], { cwd: hub, env });
    }
    const resolved = path.resolve(folder);
    assert.ok(resolved.startsWith(path.resolve(os.tmpdir()) + path.sep));
    assert.ok(path.basename(resolved).startsWith('hearth-bootstrap-test-'));
    fs.rmSync(resolved, { recursive: true, force: true });
  }
});
