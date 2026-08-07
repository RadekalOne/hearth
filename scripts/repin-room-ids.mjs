#!/usr/bin/env node
// Phase 4 of docs/MIGRATION-CONTINUWUITY.md — rewrite hardcoded Matrix room IDs
// after the rebuild. Room IDs change; MXIDs and aliases do not.
//
//   node scripts/repin-room-ids.mjs --snapshot   BEFORE migrating: record current IDs
//   node scripts/repin-room-ids.mjs              AFTER migrating: dry run (default)
//   node scripts/repin-room-ids.mjs --write      ...apply
//   node scripts/repin-room-ids.mjs --write --all   also rewrite dated one-off scripts
//
// Old IDs come from the snapshot, new IDs from the current hearth.config.json,
// matched by room alias. Originals are copied to archive/repin-backup/ before any
// file is touched — most of the tree is untracked, so git is not a safety net.

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const SNAPSHOT = path.join(ROOT, "scripts", ".room-id-map.json");
const BACKUP_DIR = path.join(ROOT, "archive", "repin-backup");

const args = process.argv.slice(2);
const doSnapshot = args.includes("--snapshot");
const doWrite = args.includes("--write");
const includeAll = args.includes("--all");
const scanRoot = path.resolve(flagValue("--root") || path.join(ROOT, ".."));

const SKIP_DIRS = new Set([
  "node_modules", ".git", ".venv", "venv", "__pycache__", "dist", "build",
  "archive", ".claude", "logs",
  // Historical records: they document what the IDs *were*. Rewriting them would
  // corrupt the audit trail and, for backups/, the rollback material.
  "scratch", "backups", "docs", "chat_log",
]);
// Same reasoning, for individual files — including this script's own snapshot,
// which holds the old→new mapping and must survive the rewrite.
const SKIP_FILES = [
  /(^|[\\/])\.room-id-map\.json$/,
  /(^|[\\/])chat_log\b/i,
  // Migration handoffs print the old→new mapping as a reference table on purpose.
  // Body-matching would rewrite the "old" column to equal the "new" one, destroying it.
  /(^|[\\/])HANDOFF-[\w-]*\.md$/i,
];
const EXTS = new Set([".py", ".ps1", ".js", ".mjs", ".md", ".json", ".cmd", ".txt", ".vbs", ".toml"]);
// Dated one-off sweeps/posts: historical runs, not part of the live loop.
const ONE_OFF = /(^|[\\/])(sweep|post|post-status|append|append-chat-log|append-chatlog|fetch-tasks|verify-lobby|heartbeat)[-\w]*-\d{2}-\d{2}\b/i;

function flagValue(name) {
  const i = args.indexOf(name);
  return i >= 0 ? args[i + 1] : null;
}

function die(msg) {
  console.error(`✗ ${msg}`);
  process.exit(1);
}

function loadRooms() {
  const cfg = JSON.parse(fs.readFileSync(path.join(ROOT, "hearth.config.json"), "utf8"));
  const rooms = cfg.rooms || {};
  if (!Object.keys(rooms).length) die("hearth.config.json lists no rooms");
  return rooms;
}

function* walk(dir) {
  let entries;
  try {
    entries = fs.readdirSync(dir, { withFileTypes: true });
  } catch {
    return;
  }
  for (const e of entries) {
    const full = path.join(dir, e.name);
    if (e.isDirectory()) {
      if (SKIP_DIRS.has(e.name)) continue;
      yield* walk(full);
    } else if (e.isFile() && EXTS.has(path.extname(e.name)) && !SKIP_FILES.some((re) => re.test(full))) {
      yield full;
    }
  }
}

// ------------------------------------------------------------------ snapshot

if (doSnapshot) {
  const rooms = loadRooms();
  fs.writeFileSync(SNAPSHOT, JSON.stringify({
    capturedAt: new Date().toISOString(),
    note: "Room IDs as they were before the Conduit → continuwuity rebuild.",
    old: rooms,
  }, null, 2));
  console.log(`✓ snapshotted ${Object.keys(rooms).length} room IDs → ${path.relative(ROOT, SNAPSHOT)}`);
  for (const [alias, id] of Object.entries(rooms)) console.log(`    ${alias.padEnd(16)} ${id}`);
  console.log("\nMigrate, run `hearth setup`, then re-run this script without --snapshot.");
  process.exit(0);
}

// ------------------------------------------------------------------ re-pin

if (!fs.existsSync(SNAPSHOT)) {
  die(`no snapshot at ${path.relative(ROOT, SNAPSHOT)} — run with --snapshot BEFORE migrating`);
}

const oldRooms = JSON.parse(fs.readFileSync(SNAPSHOT, "utf8")).old || {};
const newRooms = loadRooms();

const replacements = [];
for (const [alias, oldId] of Object.entries(oldRooms)) {
  const newId = newRooms[alias];
  if (!newId) {
    console.warn(`⚠ #${alias} is in the snapshot but not in hearth.config.json — recreate it, then re-run`);
    continue;
  }
  if (newId === oldId) {
    console.warn(`⚠ #${alias} still has its pre-migration ID — did \`hearth setup\` run?`);
    continue;
  }
  // Match on the ID body, not the !-prefixed literal: room IDs also appear
  // URL-encoded (%21...) or bare in launcher scripts and URLs. The 43-char body is
  // unique enough to substitute on its own, and doing so preserves whatever sigil
  // encoding the surrounding file uses. A %21-encoded reference in a tracked .cmd
  // file survived the first migration pass precisely because of this.
  replacements.push({ alias, oldId, newId, oldBody: oldId.replace(/^!/, ""), newBody: newId.replace(/^!/, "") });
}
if (!replacements.length) die("nothing to re-pin");

console.log(`Re-pinning ${replacements.length} room IDs under ${scanRoot}\n`);
for (const r of replacements) console.log(`  #${r.alias.padEnd(16)} ${r.oldId}\n   ${" ".repeat(17)}→ ${r.newId}`);

const hits = [];
for (const file of walk(scanRoot)) {
  let text;
  try {
    text = fs.readFileSync(file, "utf8");
  } catch {
    continue;
  }
  const counts = replacements
    .map((r) => ({ ...r, n: text.split(r.oldBody).length - 1 }))
    .filter((r) => r.n > 0);
  if (counts.length) hits.push({ file, text, counts, oneOff: ONE_OFF.test(file) });
}

const live = hits.filter((h) => !h.oneOff);
const dated = hits.filter((h) => h.oneOff);
const targets = includeAll ? hits : live;

const total = (list) => list.reduce((s, h) => s + h.counts.reduce((a, c) => a + c.n, 0), 0);

console.log(`\n── live files (${live.length}, ${total(live)} refs) ──`);
for (const h of live) {
  console.log(`  ${path.relative(scanRoot, h.file)}  [${h.counts.map((c) => `${c.alias}×${c.n}`).join(" ")}]`);
}
console.log(`\n── dated one-offs (${dated.length}, ${total(dated)} refs) ── ${includeAll ? "INCLUDED (--all)" : "skipped; pass --all to include"}`);
for (const h of dated) console.log(`  ${path.relative(scanRoot, h.file)}`);

if (!doWrite) {
  console.log(`\nDry run. ${targets.length} files would change. Re-run with --write to apply.`);
  process.exit(0);
}

fs.mkdirSync(BACKUP_DIR, { recursive: true });
let changed = 0;
for (const h of targets) {
  const backup = path.join(BACKUP_DIR, path.relative(scanRoot, h.file));
  fs.mkdirSync(path.dirname(backup), { recursive: true });
  fs.copyFileSync(h.file, backup);

  let out = h.text;
  for (const r of h.counts) out = out.split(r.oldBody).join(r.newBody);
  fs.writeFileSync(h.file, out);
  changed++;
}

console.log(`\n✓ rewrote ${changed} files. Originals: ${path.relative(scanRoot, BACKUP_DIR)}`);
console.log("Re-enable the scheduled tasks and confirm each agent posts [STATUS] in the lobby.");
