// Private bridge for the Windows wizard. Input is JSON over stdin, never argv.
import fs from 'node:fs';
import path from 'node:path';
import net from 'node:net';
import { spawnSync, spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const marker = '.hearth-wizard.json';
export function validateInput(input) {
  if (!/^[a-z0-9][a-z0-9._-]{0,31}$/.test(input.username || ''))
    throw new Error('Use 1–32 lowercase letters, numbers, dots, dashes or underscores for your login name. Start with a letter or number.');
  if (typeof input.password !== 'string' || input.password.length < 12 || /[\r\n\0]/.test(input.password))
    throw new Error('Choose a password with at least 12 characters, without line breaks.');
}
export function checkTarget(target) {
  if (!fs.existsSync(target) || fs.readdirSync(target).length === 0) return false;
  try {
    const saved = JSON.parse(fs.readFileSync(path.join(target, marker), 'utf8'));
    if (saved.version === 1 && path.resolve(saved.target) === path.resolve(target)) return true;
  } catch {}
  throw new Error('The installation folder already contains files from another setup. This wizard will not overwrite them. Use a different Windows account or ask for help moving that installation.');
}
function docker(args) {
  const result = spawnSync('docker', args, { encoding: 'utf8', windowsHide: true, timeout: 20000 });
  if (result.error || result.status !== 0)
    throw new Error('Docker is not ready. Install Docker Desktop, open it, and wait until its engine is running. Then click Check again.');
  return result.stdout.trim();
}
async function freePort(port) {
  await new Promise((resolve, reject) => {
    const server = net.createServer();
    server.once('error', () => reject(new Error(`Another application is using port ${port}. Close it before installing Hearth.`)));
    server.listen(port, '127.0.0.1', () => server.close(resolve));
  });
}
export async function preflight(target, runDocker = docker) {
  if (Number(process.versions.node.split('.')[0]) < 20) throw new Error('Install Node.js 20 or newer, then reopen this wizard.');
  const owned = checkTarget(target);
  if (runDocker(['info', '--format', '{{.OSType}}']) !== 'linux')
    throw new Error('In Docker Desktop, switch to Linux containers, then check again.');
  runDocker(['compose', 'version']);
  const ids = runDocker(['ps', '-aq', '--filter', 'label=com.docker.compose.project=hearth']);
  if (ids) {
    const containers = JSON.parse(runDocker(['inspect', ...ids.split(/\s+/)]));
    if (!owned || containers.some(c => {
      const location = c.Config?.Labels?.['com.docker.compose.project.working_dir'];
      return !location || path.resolve(location).toLowerCase() !== path.resolve(target).toLowerCase();
    })) throw new Error('Another Hearth installation already uses Docker on this computer. This wizard will not change it.');
  } else {
    if (!owned && runDocker(['volume', 'ls', '-q', '--filter', 'label=com.docker.compose.project=hearth']))
      throw new Error('Docker contains data from an earlier Hearth installation. Restore that installation before using this wizard.');
    for (const port of [6167, 8009, 8010]) await freePort(port);
  }
  return owned;
}
async function ready() {
  for (let attempt = 0; attempt < 60; attempt++) {
    const results = await Promise.all([
      'http://127.0.0.1:6167/_matrix/client/versions',
      'http://127.0.0.1:8009/', 'http://127.0.0.1:8010/health',
    ].map(url => fetch(url, { signal: AbortSignal.timeout(3000) }).then(r => r.ok).catch(() => false)));
    if (results.every(Boolean)) return;
    await new Promise(resolve => setTimeout(resolve, 2000));
  }
  throw new Error('Setup finished, but Hearth is still not responding. Check Docker Desktop for a stopped Hearth container, then retry with the same login and password. Your data is kept.');
}
async function main() {
  let raw = '';
  for await (const chunk of process.stdin) { raw += chunk; if (raw.length > 16384) throw new Error('Setup input is too large.'); }
  const input = JSON.parse(raw);
  const target = path.join(process.env.LOCALAPPDATA, 'Hearth', 'hub');
  if (input.action !== 'check' && input.action !== 'install') throw new Error('Unknown setup action.');
  if (input.action === 'install') validateInput(input);
  await preflight(target);
  if (input.action === 'check') return { ok: true, message: 'Your computer is ready. Choose your Hearth login below.', target };
  fs.mkdirSync(target, { recursive: true });
  fs.writeFileSync(path.join(target, marker), JSON.stringify({ version: 1, target }));
  // The existing launcher requires an empty directory or the CLI marker. Stage
  // only the public package files; never copy a developer checkout's secrets.
  for (const item of ['cli', 'config', 'docs', 'mcp/matrix', 'mcp/memory', '.env.example',
    'docker-compose.yml', 'docker-compose.expose.yml', 'docker-compose.expose-memory.yml', 'LICENSE', 'README.md', 'PROJECT.md']) {
    if (item === 'config' && fs.existsSync(path.join(target, 'config'))) continue;
    fs.cpSync(path.join(root, item), path.join(target, item), { recursive: true,
      filter: source => !['node_modules', '__pycache__', 'data', 'secrets'].includes(path.basename(source)) });
  }
  fs.copyFileSync(path.join(root, 'config/gitignore.template'), path.join(target, '.gitignore'));
  const config = path.join(target, 'wizard-deployment.json');
  fs.writeFileSync(config, JSON.stringify({ mode: 'local', adminUsername: input.username }));
  await new Promise((resolve, reject) => {
    const child = spawn(process.execPath, [path.join(target, 'cli/hearth.mjs'), 'install', '--yes', '--config', config], {
      cwd: target, windowsHide: true, stdio: ['ignore', 'ignore', 'ignore'],
      env: { ...process.env, HEARTH_ROOT: target, HEARTH_ADMIN_PASSWORD: input.password },
    });
    child.once('error', () => reject(new Error('Hearth could not start setup. Reopen the wizard and try again.')));
    child.once('exit', code => code === 0 ? resolve() : reject(new Error('Hearth setup could not finish. Check that Docker Desktop is running and your internet connection works. Retry with the same login and password. If it still fails, ask for help using the installation folder shown below.')));
  });
  input.password = '';
  await ready();
  return { ok: true, message: 'Hearth is ready! Open chat and sign in with the login and password you chose. Agent connections are a separate next step; see the guide.', target };
}
if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main().then(result => console.log(JSON.stringify(result))).catch(error => {
    console.log(JSON.stringify({ ok: false, message: error.message })); process.exitCode = 1;
  });
}
