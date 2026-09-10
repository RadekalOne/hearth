import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { checkTarget, validateInput, preflight } from '../installer/windows/runner.mjs';

test('wizard protects unrelated deployments and accepts its own retry', () => {
  const target = fs.mkdtempSync(path.join(os.tmpdir(), 'hearth-wizard-test-'));
  try {
    assert.equal(checkTarget(target), false);
    fs.writeFileSync(path.join(target, '.env'), 'DO_NOT_OVERWRITE=yes');
    assert.throws(() => checkTarget(target), /already contains/);
    fs.writeFileSync(path.join(target, '.hearth-wizard.json'), JSON.stringify({ version: 1, target: target + '-other' }));
    assert.throws(() => checkTarget(target), /already contains/);
    fs.writeFileSync(path.join(target, '.hearth-wizard.json'), JSON.stringify({ version: 1, target }));
    assert.equal(checkTarget(target), true);
    assert.equal(fs.readFileSync(path.join(target, '.env'), 'utf8'), 'DO_NOT_OVERWRITE=yes');
  } finally { fs.rmSync(target, { recursive: true, force: true }); }
});
test('wizard rejects unsafe usernames and unsuitable passwords', () => {
  for (const username of ['../admin', '--flag', 'Name', 'a\nb', ''])
    assert.throws(() => validateInput({ username, password: 'long-enough-password' }));
  for (const password of ['', 'short', 'long-password\n', 'long-password\0'])
    assert.throws(() => validateInput({ username: 'jane', password }));
  assert.doesNotThrow(() => validateInput({ username: 'jane-doe', password: 'a strong Unicode password 🔥' }));
});

test('wizard refuses other Docker projects and abandoned data, but permits its own retry', async () => {
  const target = fs.mkdtempSync(path.join(os.tmpdir(), 'hearth-wizard-docker-'));
  const fakeDocker = (location, volumes = '') => args => {
    if (args[0] === 'info') return 'linux';
    if (args[0] === 'compose') return 'Docker Compose v2';
    if (args[0] === 'ps') return location ? 'container-id' : '';
    if (args[0] === 'inspect') return JSON.stringify([{ Config: { Labels: { 'com.docker.compose.project.working_dir': location } } }]);
    if (args[0] === 'volume') return volumes;
    throw new Error('Unexpected Docker call');
  };
  try {
    await assert.rejects(preflight(target, fakeDocker(target)), /Another Hearth/);
    await assert.rejects(preflight(target, fakeDocker('', 'hearth_memory-data')), /earlier Hearth/);
    fs.writeFileSync(path.join(target, '.hearth-wizard.json'), JSON.stringify({ version: 1, target }));
    await assert.rejects(preflight(target, fakeDocker(target + '-other')), /Another Hearth/);
    assert.equal(await preflight(target, fakeDocker(target)), true);
  } finally { fs.rmSync(target, { recursive: true, force: true }); }
});
