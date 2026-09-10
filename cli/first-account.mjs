import { spawnSync } from 'node:child_process';

// Continuwuity creates a fresh bootstrap token at every start until its first
// human account exists. The configured registration token works only afterward.
export function bootstrapToken(logs) {
  const clean = logs.replace(/\x1b\[[0-9;]*m/g, '');
  return [...clean.matchAll(/using the registration token\s+([A-Za-z0-9_-]+)/g)].at(-1)?.[1];
}

export function firstAccountToken(root, cfg, fallback, run = spawnSync) {
  let url;
  try { url = new URL(cfg.homeserverUrl); } catch { return fallback; }
  if (cfg.mode !== 'local' || !['localhost', '127.0.0.1', '[::1]'].includes(url.hostname)) return fallback;
  // Capture locally, never stream the logs: they contain the one-time secret.
  const result = run('docker', ['compose', 'logs', '--no-color', '--tail', '250', 'conduit'], {
    cwd: root, encoding: 'utf8', windowsHide: true, timeout: 15000, maxBuffer: 1024 * 1024,
  });
  if (result.error || result.status !== 0) return fallback;
  return bootstrapToken((result.stdout || '') + '\n' + (result.stderr || '')) || fallback;
}
