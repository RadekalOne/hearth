#!/usr/bin/env node
// Phase 1 of docs/MIGRATION-CONTINUWUITY.md — archive Matrix room history before
// the homeserver is replaced. Conduit's database cannot be migrated, so this is
// the only chance to keep what is in the rooms.
//
//   node scripts/archive-rooms.mjs              dump to archive/ (no network writes)
//   node scripts/archive-rooms.mjs --import     ...and file the transcripts as drawers
//   node scripts/archive-rooms.mjs --room agent-lobby
//
// Reads room IDs from hearth.config.json, the Matrix token from secrets/admin.env
// (the admin is in every room), and the memory admin token from .env.
// Imports are upserts keyed on a deterministic drawer id, so re-running is safe.

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const ARCHIVE_DIR = path.join(ROOT, "archive");
const MESSAGES_PER_DRAWER = 40;
const PAGE_SIZE = 100;
const IMPORT_BATCH = 200; // /api/import hard limit

const args = process.argv.slice(2);
const doImport = args.includes("--import");
const onlyRoom = flag("--room");

function flag(name) {
  const i = args.indexOf(name);
  return i >= 0 ? args[i + 1] : null;
}

function die(msg) {
  console.error(`✗ ${msg}`);
  process.exit(1);
}

function readEnvFile(file) {
  if (!fs.existsSync(file)) die(`missing ${file}`);
  const out = {};
  for (const line of fs.readFileSync(file, "utf8").split(/\r?\n/)) {
    const m = line.match(/^\s*([A-Z0-9_]+)\s*=\s*(.*)$/);
    if (m) out[m[1]] = m[2].trim();
  }
  return out;
}

async function matrixGet(base, pathname, token, params) {
  const url = new URL(`/_matrix/client/v3${pathname}`, base);
  for (const [k, v] of Object.entries(params)) if (v != null) url.searchParams.set(k, v);
  const res = await fetch(url, { headers: { Authorization: `Bearer ${token}` } });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(`${res.status} ${data.errcode || ""} ${data.error || ""}`.trim());
  return data;
}

// Page backwards from the live edge until the server stops handing out tokens.
async function fetchRoom(base, token, roomId) {
  const events = [];
  let from = null;
  for (;;) {
    const page = await matrixGet(base, `/rooms/${encodeURIComponent(roomId)}/messages`, token, {
      dir: "b", limit: PAGE_SIZE, from,
    });
    const chunk = page.chunk || [];
    events.push(...chunk.filter((e) => e.type === "m.room.message"));
    if (!page.end || page.end === from || chunk.length === 0) break;
    from = page.end;
    process.stdout.write(`\r  … ${events.length} messages`);
  }
  process.stdout.write("\r");
  return events.reverse(); // chronological
}

function iso(ts) {
  return new Date(ts).toISOString().replace(/\.\d{3}Z$/, "Z");
}

function transcriptLine(e) {
  const body = (e.content?.body ?? "").replace(/\r/g, "");
  return `${iso(e.origin_server_ts)}  ${e.sender}: ${body}`;
}

function toDrawers(alias, roomId, events) {
  const out = [];
  for (let i = 0; i < events.length; i += MESSAGES_PER_DRAWER) {
    const slice = events.slice(i, i + MESSAGES_PER_DRAWER);
    const seq = String(out.length).padStart(4, "0");
    const first = iso(slice[0].origin_server_ts);
    const last = iso(slice[slice.length - 1].origin_server_ts);
    const header =
      `[ARCHIVE] #${alias} — messages ${i + 1}–${i + slice.length} of ${events.length}\n` +
      `Window: ${first} → ${last}\n` +
      `Pre-migration room ID: ${roomId}\n` +
      `Captured before the Conduit → continuwuity rebuild (docs/MIGRATION-CONTINUWUITY.md).\n`;
    out.push({
      drawer_id: `drawer_archive_${alias.replace(/-/g, "_")}_${seq}`,
      wing: "hearth",
      room: `archive-${alias}`,
      added_by: "archive-rooms.mjs",
      source: `matrix:${roomId}`,
      created_at: new Date(slice[0].origin_server_ts).toISOString(),
      content: `${header}\n${slice.map(transcriptLine).join("\n")}`,
    });
  }
  return out;
}

async function importDrawers(memoryUrl, adminToken, drawers) {
  let imported = 0;
  for (let i = 0; i < drawers.length; i += IMPORT_BATCH) {
    const batch = drawers.slice(i, i + IMPORT_BATCH);
    const res = await fetch(new URL("/api/import", memoryUrl), {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${adminToken}` },
      body: JSON.stringify({ drawers: batch }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(`import failed: ${res.status} ${data.error || ""}`);
    imported += data.imported ?? 0;
  }
  return imported;
}

// ------------------------------------------------------------------ main

const cfg = JSON.parse(fs.readFileSync(path.join(ROOT, "hearth.config.json"), "utf8"));
const admin = readEnvFile(path.join(ROOT, "secrets", "admin.env"));
const env = readEnvFile(path.join(ROOT, ".env"));

const base = admin.MATRIX_HOMESERVER_URL || cfg.homeserverUrl;
if (!admin.MATRIX_ACCESS_TOKEN) die("secrets/admin.env has no MATRIX_ACCESS_TOKEN");

const rooms = Object.entries(cfg.rooms || {}).filter(([alias]) => !onlyRoom || alias === onlyRoom);
if (!rooms.length) die(onlyRoom ? `no room aliased ${onlyRoom}` : "hearth.config.json lists no rooms");

if (doImport) {
  if (!env.HEARTH_MEMORY_ADMIN_TOKEN) die(".env has no HEARTH_MEMORY_ADMIN_TOKEN (needed for /api/import)");
  if (!env.HEARTH_MEMORY_URL) die(".env has no HEARTH_MEMORY_URL");
}

fs.mkdirSync(ARCHIVE_DIR, { recursive: true });

let grandTotal = 0;
const allDrawers = [];

for (const [alias, roomId] of rooms) {
  console.log(`\n▸ #${alias}  ${roomId}`);
  let events;
  try {
    events = await fetchRoom(base, admin.MATRIX_ACCESS_TOKEN, roomId);
  } catch (err) {
    console.error(`  ✗ ${err.message} — skipped`);
    continue;
  }
  const raw = path.join(ARCHIVE_DIR, `${alias}.json`);
  fs.writeFileSync(raw, JSON.stringify({ alias, roomId, capturedAt: new Date().toISOString(), events }, null, 2));

  const drawers = toDrawers(alias, roomId, events);
  fs.writeFileSync(path.join(ARCHIVE_DIR, `${alias}.drawers.json`), JSON.stringify(drawers, null, 2));
  allDrawers.push(...drawers);
  grandTotal += events.length;

  console.log(`  ${events.length} messages → ${path.relative(ROOT, raw)} (${drawers.length} drawers)`);
}

console.log(`\n${grandTotal} messages across ${rooms.length} rooms, ${allDrawers.length} drawers staged.`);

if (!doImport) {
  console.log("Local dump only. Review archive/, then re-run with --import to file them in hearth-memory.");
  console.log("⚠ Transcripts are verbatim — check them for pasted tokens or passwords before importing.");
} else {
  const n = await importDrawers(env.HEARTH_MEMORY_URL, env.HEARTH_MEMORY_ADMIN_TOKEN, allDrawers);
  console.log(`✓ imported ${n} drawers into hearth-memory (wing=hearth, room=archive-<alias>)`);
}
