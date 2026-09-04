// `hearth notify` persists its sync cursor and resumes from it after a restart, so
// mentions that arrived while the notifier was down are not lost.
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import fs from "node:fs";
import http from "node:http";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const REPO = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const USER = "@claude:hearth.test";

function fixture() {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "hearth-notify-test-"));
  fs.mkdirSync(path.join(root, "cli"), { recursive: true });
  fs.mkdirSync(path.join(root, "secrets", "agents"), { recursive: true });
  fs.copyFileSync(path.join(REPO, "cli", "hearth.mjs"), path.join(root, "cli", "hearth.mjs"));
  fs.writeFileSync(
    path.join(root, "handler.mjs"),
    "import fs from 'node:fs'; fs.appendFileSync(process.argv[2], process.env.HEARTH_EVENT_ID + '\\n');\n"
  );
  return root;
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
async function waitFor(check, timeoutMs = 15000) {
  const started = Date.now();
  while (Date.now() - started < timeoutMs) {
    if (check()) return true;
    await sleep(100);
  }
  return false;
}

// /sync script: a map of since-token -> response. Missing tokens hang (long poll).
function fakeSync(script) {
  const sockets = new Set();
  const seen = [];
  const server = http.createServer((req, res) => {
    const url = new URL(req.url, "http://x");
    seen.push(url.searchParams.get("since"));
    const key = url.searchParams.get("since") ?? "initial";
    const payload = script[key];
    if (!payload) return; // hang like a real long-poll
    res.writeHead(200, { "content-type": "application/json" });
    res.end(JSON.stringify(payload));
  });
  server.on("connection", (s) => {
    sockets.add(s);
    s.on("close", () => sockets.delete(s));
  });
  return {
    server,
    seen,
    async start() {
      await new Promise((r) => server.listen(0, "127.0.0.1", r));
      return `http://127.0.0.1:${server.address().port}`;
    },
    stop() {
      for (const s of sockets) s.destroy();
      server.close();
    },
  };
}

const mention = (eventId) => ({
  rooms: { join: { "!r:hearth.test": { timeline: { events: [
    { type: "m.room.message", event_id: eventId, sender: "@rad:hearth.test",
      content: { msgtype: "m.text", body: "claude: hello", "m.mentions": { user_ids: [USER] } } },
  ] } } } },
});

function startNotifier(root, handlerLog) {
  const child = spawn(process.execPath, [
    path.join(root, "cli", "hearth.mjs"), "notify", "claude", "--exec",
    `"${process.execPath}" "${path.join(root, "handler.mjs")}" "${handlerLog}"`,
  ], { env: { ...process.env, HEARTH_ROOT: root }, stdio: ["ignore", "pipe", "pipe"] });
  let out = "";
  child.stdout.on("data", (c) => (out += c));
  child.stderr.on("data", (c) => (out += c));
  return { child, output: () => out };
}

test("notify persists its sync cursor and resumes from it after a restart", async (t) => {
  const root = fixture();
  const handlerLog = path.join(root, "handled.log");
  const cursorFile = path.join(root, "secrets", "agents", "claude.notify-cursor");

  // Phase 1: fresh start. initial -> s1, s1 -> one mention + s2, s2 -> quiet + s3, s3 hangs.
  const phase1 = fakeSync({
    initial: { next_batch: "s1" },
    s1: { next_batch: "s2", ...mention("$m1") },
    s2: { next_batch: "s3", rooms: {} },
  });
  const base1 = await phase1.start();
  fs.writeFileSync(path.join(root, "secrets", "agents", "claude.env"),
    `MATRIX_HOMESERVER_URL=${base1}\nMATRIX_USER_ID=${USER}\nMATRIX_ACCESS_TOKEN=tok\n`);
  const run1 = startNotifier(root, handlerLog);
  t.after(() => { try { run1.child.kill(); } catch {} phase1.stop(); });

  assert.ok(await waitFor(() => fs.existsSync(cursorFile) && fs.readFileSync(cursorFile, "utf8").trim() === "s3"),
    `cursor should reach s3; output:\n${run1.output()}`);
  assert.ok(await waitFor(() => fs.existsSync(handlerLog) && fs.readFileSync(handlerLog, "utf8").includes("$m1")),
    "handler fired for the first mention");
  assert.equal(phase1.seen[0], null, "first sync has no since token");
  run1.child.kill();
  phase1.stop();

  // Phase 2: the server moved on while we were down. Resume from s3 (catch-up), get the
  // mention we missed, then park on s4.
  const phase2 = fakeSync({
    s3: { next_batch: "s4", ...mention("$m2") },
  });
  const base2 = await phase2.start();
  fs.writeFileSync(path.join(root, "secrets", "agents", "claude.env"),
    `MATRIX_HOMESERVER_URL=${base2}\nMATRIX_USER_ID=${USER}\nMATRIX_ACCESS_TOKEN=tok\n`);
  const run2 = startNotifier(root, handlerLog);
  t.after(() => { try { run2.child.kill(); } catch {} phase2.stop(); });

  assert.ok(await waitFor(() => fs.readFileSync(cursorFile, "utf8").trim() === "s4"),
    `cursor should advance to s4 after resume; output:\n${run2.output()}`);
  assert.ok(await waitFor(() => fs.readFileSync(handlerLog, "utf8").includes("$m2")),
    "handler fired for the mention that arrived while the notifier was down");
  assert.equal(phase2.seen[0], "s3", "resumed from the saved cursor, not from a fresh initial sync");
  assert.match(run2.output(), /resuming from saved cursor/);
  run2.child.kill();
  phase2.stop();
});

test("notify discards a cursor the server rejects and starts fresh", async (t) => {
  const root = fixture();
  const handlerLog = path.join(root, "handled.log");
  const cursorFile = path.join(root, "secrets", "agents", "claude.notify-cursor");
  fs.writeFileSync(cursorFile, "stale\n");

  const sockets = new Set();
  const seen = [];
  const server = http.createServer((req, res) => {
    const url = new URL(req.url, "http://x");
    const since = url.searchParams.get("since");
    seen.push(since);
    if (since === "stale") {
      res.writeHead(400, { "content-type": "application/json" });
      return res.end(JSON.stringify({ errcode: "M_UNKNOWN", error: "unknown token" }));
    }
    if (since === null) {
      res.writeHead(200, { "content-type": "application/json" });
      return res.end(JSON.stringify({ next_batch: "fresh1" }));
    }
    // hang
  });
  server.on("connection", (s) => { sockets.add(s); s.on("close", () => sockets.delete(s)); });
  await new Promise((r) => server.listen(0, "127.0.0.1", r));
  const base = `http://127.0.0.1:${server.address().port}`;
  fs.writeFileSync(path.join(root, "secrets", "agents", "claude.env"),
    `MATRIX_HOMESERVER_URL=${base}\nMATRIX_USER_ID=${USER}\nMATRIX_ACCESS_TOKEN=tok\n`);
  const run = startNotifier(root, handlerLog);
  t.after(() => { try { run.child.kill(); } catch {} for (const s of sockets) s.destroy(); server.close(); });

  assert.ok(await waitFor(() => fs.readFileSync(cursorFile, "utf8").trim() === "fresh1"),
    `cursor should be replaced; output:\n${run.output()}`);
  assert.deepEqual(seen.slice(0, 2), ["stale", null]);
  assert.match(run.output(), /saved cursor rejected/);
});
