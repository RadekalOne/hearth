// End-to-end tests for the hearth-matrix MCP server against a fake homeserver.
// Skips cleanly when mcp/matrix dependencies are not installed (run `npm ci --prefix mcp/matrix`).
import assert from "node:assert/strict";
import fs from "node:fs";
import http from "node:http";
import path from "node:path";
import test from "node:test";
import { fileURLToPath, pathToFileURL } from "node:url";

const REPO = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const MATRIX_DIR = path.join(REPO, "mcp", "matrix");
const SDK = path.join(MATRIX_DIR, "node_modules", "@modelcontextprotocol", "sdk");
const HAS_SDK = fs.existsSync(SDK);

const USER = "@claude:hearth.test";
const RAD = "@rad:hearth.test";
const ROOM = "!room1:hearth.test";

// ---------------------------------------------------------------- fake homeserver

function fakeHomeserver() {
  const events = []; // oldest -> newest, raw Matrix events
  let counter = 0;
  const markers = {};
  const sent = []; // content of messages posted through the API
  const addEvent = (type, sender, content) => {
    const ev = { type, sender, event_id: `$e${++counter}`, origin_server_ts: 1_700_000_000_000 + counter * 60_000, content, room_id: ROOM };
    events.push(ev);
    return ev;
  };
  const server = http.createServer((req, res) => {
    const url = new URL(req.url, "http://x");
    const p = url.pathname;
    let body = "";
    req.on("data", (c) => (body += c));
    req.on("end", () => {
      const json = (code, payload) => {
        res.writeHead(code, { "content-type": "application/json" });
        res.end(JSON.stringify(payload));
      };
      if (req.headers.authorization !== "Bearer tok") return json(401, { errcode: "M_UNKNOWN_TOKEN" });
      if (p.endsWith("/account/whoami")) return json(200, { user_id: USER, device_id: "DEV" });
      if (p.endsWith("/joined_rooms")) return json(200, { joined_rooms: [ROOM] });
      if (p.includes("/state/m.room.name")) return json(200, { name: "Agent Tasks" });
      if (p.includes("/state/")) return json(404, { errcode: "M_NOT_FOUND" });
      if (p.endsWith("/messages")) {
        const dir = url.searchParams.get("dir") ?? "b";
        const limit = Number(url.searchParams.get("limit") ?? 10);
        const from = url.searchParams.get("from");
        if (dir === "b") {
          // token "b:<n>" = number of newest events already consumed
          const consumed = from ? Number(from.split(":")[1]) : 0;
          const remaining = events.slice(0, events.length - consumed).reverse();
          const chunk = remaining.slice(0, limit);
          const next = consumed + chunk.length;
          return json(200, { chunk, start: `b:${consumed}`, end: next < events.length ? `b:${next}` : null });
        }
        const consumed = from ? Number(from.split(":")[1]) : 0;
        const chunk = events.slice(events.length - consumed).slice(0, limit);
        return json(200, { chunk, start: from, end: `b:${Math.max(0, consumed - chunk.length)}` });
      }
      if (p.includes("/account_data/m.fully_read")) {
        return markers[ROOM] ? json(200, { event_id: markers[ROOM] }) : json(404, { errcode: "M_NOT_FOUND" });
      }
      if (p.endsWith("/read_markers")) {
        markers[ROOM] = JSON.parse(body)["m.fully_read"];
        return json(200, {});
      }
      if (p.includes("/send/m.room.message/")) {
        const content = JSON.parse(body);
        sent.push(content);
        return json(200, { event_id: addEvent("m.room.message", USER, content).event_id });
      }
      if (p.includes("/send/m.reaction/")) {
        return json(200, { event_id: addEvent("m.reaction", USER, JSON.parse(body)).event_id });
      }
      if (p.includes("/relations/")) {
        const target = decodeURIComponent(p.split("/relations/")[1]);
        return json(200, { chunk: events.filter((e) => e.content?.["m.relates_to"]?.event_id === target) });
      }
      if (p.includes("/event/")) {
        const id = decodeURIComponent(p.split("/event/")[1]);
        const ev = events.find((e) => e.event_id === id);
        return ev ? json(200, ev) : json(404, { errcode: "M_NOT_FOUND" });
      }
      json(404, { errcode: "M_UNRECOGNIZED", error: p });
    });
  });
  return { server, events, addEvent, sent, markers };
}

async function startServer(server) {
  await new Promise((r) => server.listen(0, "127.0.0.1", r));
  return `http://127.0.0.1:${server.address().port}`;
}

async function connectClient(base) {
  const { Client } = await import(pathToFileURL(path.join(SDK, "dist", "esm", "client", "index.js")).href);
  const { StdioClientTransport } = await import(pathToFileURL(path.join(SDK, "dist", "esm", "client", "stdio.js")).href);
  const transport = new StdioClientTransport({
    command: process.execPath,
    args: [path.join(MATRIX_DIR, "index.mjs")],
    // The parser test imports the module in-process with HEARTH_MATRIX_MCP_NO_STDIO=1;
    // that flag must not leak into the spawned server or the client waits forever.
    env: { ...process.env, MATRIX_HOMESERVER_URL: base, MATRIX_USER_ID: USER, MATRIX_ACCESS_TOKEN: "tok", HEARTH_MATRIX_MCP_NO_STDIO: "0" },
    stderr: "pipe",
  });
  const client = new Client({ name: "test", version: "0" }, { capabilities: {} });
  await client.connect(transport);
  const call = async (name, args = {}) => {
    const res = await client.callTool({ name, arguments: args });
    const text = res.content[0].text;
    if (res.isError) throw new Error(text);
    return JSON.parse(text);
  };
  return { client, call };
}

test("parsers: tag, signature, markdown, reaction key", { skip: !HAS_SDK && "mcp/matrix deps not installed" }, async () => {
  process.env.MATRIX_HOMESERVER_URL = "http://127.0.0.1:9";
  process.env.MATRIX_USER_ID = USER;
  process.env.MATRIX_ACCESS_TOKEN = "tok";
  process.env.HEARTH_MATRIX_MCP_NO_STDIO = "1";
  const mod = await import(pathToFileURL(path.join(MATRIX_DIR, "index.mjs")).href);
  assert.deepEqual(mod.parseTag("[BLOCKED-NEEDS-RAD] x"), { tag: "BLOCKED-NEEDS-RAD", tag_base: "BLOCKED" });
  assert.deepEqual(mod.parseTag("[tick 12:00 ET 9/3] [HB]"), { tag: "TICK 12:00 ET 9/3", tag_base: "TICK" });
  assert.equal(mod.parseTag("plain"), null);
  assert.deepEqual(mod.parseSignature("body\n\n-- claude @ laptop (executor)"), { agent: "claude", surface: "laptop", role: "executor" });
  assert.deepEqual(mod.parseSignature("body\n— Codex"), { agent: "codex" });
  assert.deepEqual(mod.parseSignature("body\n- mavis @ laptop (auto)"), { agent: "mavis", surface: "laptop", role: "auto" });
  assert.equal(mod.parseSignature("no signature"), null);
  assert.deepEqual(mod.parseSignature(["body", "-- claude @ desktop (all five rooms read and re-read before this post; ids identical)"].join(String.fromCharCode(10))), { agent: "claude", surface: "desktop" }, "a parenthetical sentence is not a role");

  assert.equal(mod.normalizeReactionKey("👍️"), "👍");
  const html = mod.markdownToHtml("Run `npm test` and see **bold** [docs](https://x.y/z)\n```sh\necho hi\n```\n<script>");
  assert.match(html, /<code>npm test<\/code>/);
  assert.match(html, /<strong>bold<\/strong>/);
  assert.match(html, /<a href="https:\/\/x\.y\/z">docs<\/a>/);
  assert.match(html, /<pre><code class="language-sh">echo hi<\/code><\/pre>/);
  assert.match(html, /&lt;script&gt;/, "HTML is escaped, never passed through");
});

test("matrix MCP: enriched reads, unread from marker, reactions, threads, search", { skip: !HAS_SDK && "mcp/matrix deps not installed" }, async (t) => {
  const hs = fakeHomeserver();
  const base = await startServer(hs.server);
  const { client, call } = await connectClient(base);
  t.after(async () => {
    await client.close();
    hs.server.close();
  });

  const e1 = hs.addEvent("m.room.message", RAD, { msgtype: "m.text", body: "[TASK] write the guide" });
  const e2 = hs.addEvent("m.room.message", "@codex:hearth.test", {
    msgtype: "m.text", body: "[PLAN] guide outline\n-- codex @ laptop (executor)",
    "m.relates_to": { "m.in_reply_to": { event_id: e1.event_id } },
  });
  const e3 = hs.addEvent("m.room.message", RAD, { msgtype: "m.text", body: "claude: please review", "m.mentions": { user_ids: [USER] } });
  const e4 = hs.addEvent("m.room.message", "@mavis:hearth.test", {
    msgtype: "m.text", body: "[BLOCKED-NEEDS-RAD] need the token\n- mavis @ laptop (auto)",
    "m.relates_to": { rel_type: "m.thread", event_id: e1.event_id, "m.in_reply_to": { event_id: e1.event_id }, is_falling_back: true },
  });
  hs.addEvent("m.room.message", "@codex:hearth.test", { msgtype: "m.text", body: "* edited plan", "m.relates_to": { rel_type: "m.replace", event_id: e2.event_id }, "m.new_content": { msgtype: "m.text", body: "[PLAN] guide outline v2\n-- codex @ laptop (executor)" } });
  const e5 = hs.addEvent("m.room.message", RAD, { msgtype: "m.text", body: "thanks all" });

  const who = await call("whoami");
  assert.equal(who.user_id, USER);
  assert.match(who.now, /^\d{4}-\d{2}-\d{2}T/, "every response carries the server clock");

  const read = await call("read_messages", { room_id: ROOM, limit: 10 });
  assert.equal(read.count, 5, "the edit event is folded, not listed");
  assert.equal(read.messages[0].event_id, e5.event_id, "newest first");
  const byId = Object.fromEntries(read.messages.map((m) => [m.event_id, m]));
  assert.equal(byId[e3.event_id].mentioned_me, true, "pill mention with no @name in the body");
  assert.equal(byId[e5.event_id].mentioned_me, false);
  assert.equal(byId[e2.event_id].in_reply_to, e1.event_id);
  assert.equal(byId[e2.event_id].edited, true);
  assert.match(byId[e2.event_id].body, /v2/, "edited body replaces the original");
  assert.equal(byId[e2.event_id].tag_base, "PLAN");
  assert.deepEqual(byId[e2.event_id].signature, { agent: "codex", surface: "laptop", role: "executor" });
  assert.equal(byId[e4.event_id].thread_root, e1.event_id);
  assert.equal(byId[e4.event_id].tag, "BLOCKED-NEEDS-RAD");
  assert.equal(byId[e4.event_id].tag_base, "BLOCKED");
  assert.equal(byId[e1.event_id].tag_base, "TASK");
  assert.equal(read.newest_ts, byId[e5.event_id].timestamp);

  // Reactions are visible on reads and via get_event relations.
  await call("react", { room_id: ROOM, event_id: e2.event_id, key: "👍" });
  const afterReact = await call("read_messages", { room_id: ROOM, limit: 10 });
  const plan = afterReact.messages.find((m) => m.event_id === e2.event_id);
  assert.deepEqual(plan.reactions, { "👍": [USER] });
  const single = await call("get_event", { room_id: ROOM, event_id: e2.event_id });
  assert.deepEqual(single.reactions, { "👍": [USER] });
  assert.equal(single.in_reply_to, e1.event_id);

  // unread before any marker explains itself; after mark_read it returns only newer events.
  const noMarker = await call("unread", { room_id: ROOM });
  assert.equal(noMarker.marker_event_id, null);
  assert.equal(noMarker.marker_found, false);
  const marked = await call("mark_read", { room_id: ROOM, event_id: e3.event_id });
  assert.equal(marked.marked, e3.event_id);
  assert.equal(hs.markers[ROOM], e3.event_id, "mark_read sets the fully-read marker");
  const unread = await call("unread", { room_id: ROOM });
  assert.equal(unread.marker_event_id, e3.event_id);
  assert.equal(unread.marker_found, true);
  assert.deepEqual(unread.messages.map((m) => m.event_id), [e4.event_id, e5.event_id], "oldest first, only after the marker");
  assert.equal(unread.newest_event_id, e5.event_id);

  const after = await call("read_messages", { room_id: ROOM, after_event_id: e3.event_id });
  assert.equal(after.after_event_found, true);
  assert.deepEqual(after.messages.map((m) => m.event_id), [e5.event_id, e4.event_id]);

  // Posting with mentions, a thread, and markdown produces proper Matrix content.
  const posted = await call("post_message", {
    room_id: ROOM,
    text: "@rad the **plan** is ready",
    mentions: [RAD],
    thread_root: e1.event_id,
    markdown: true,
  });
  assert.match(posted.event_id, /^\$e\d+$/);
  const content = hs.sent.at(-1);
  assert.deepEqual(content["m.mentions"], { user_ids: [RAD] });
  assert.equal(content.format, "org.matrix.custom.html");
  assert.match(content.formatted_body, /matrix\.to\/#\/%40rad%3Ahearth\.test/, "pill link for the mention");
  assert.match(content.formatted_body, /<strong>plan<\/strong>/);
  assert.equal(content["m.relates_to"].rel_type, "m.thread");
  assert.equal(content["m.relates_to"].event_id, e1.event_id);
  assert.equal(content.body, "@rad the **plan** is ready", "plain body kept for legacy clients");

  const plainReply = await call("post_message", { room_id: ROOM, text: "ok", reply_to: e5.event_id });
  assert.ok(plainReply.event_id);
  assert.deepEqual(hs.sent.at(-1)["m.relates_to"], { "m.in_reply_to": { event_id: e5.event_id } });

  const found = await call("search_messages", { room_id: ROOM, contains: "blocked" });
  assert.equal(found.count, 1);
  assert.equal(found.matches[0].event_id, e4.event_id);
  const bySender = await call("search_messages", { room_id: ROOM, sender: "rad" });
  assert.equal(bySender.count, 3, "rad posted e1, e3 and e5; everything else came from the agent");
});

test("matrix MCP: unread caps the no-marker case, pages a big backlog, and truncates long bodies", { skip: !HAS_SDK && "mcp/matrix deps not installed" }, async (t) => {
  const hs = fakeHomeserver();
  const base = await startServer(hs.server);
  const { client, call } = await connectClient(base);
  t.after(async () => {
    await client.close();
    hs.server.close();
  });

  const essay = "A very long post. ".repeat(200); // 3600 chars
  const seeded = [];
  for (let i = 1; i <= 30; i++) {
    seeded.push(hs.addEvent("m.room.message", RAD, { msgtype: "m.text", body: i % 10 === 0 ? essay : `message ${i}` }));
  }

  // No marker yet: only the newest 20, oldest-first, even when more is asked for.
  const cold = await call("unread", { room_id: ROOM, limit: 100 });
  assert.equal(cold.marker_event_id, null);
  assert.equal(cold.count, 20);
  assert.equal(cold.messages[0].event_id, seeded[10].event_id, "starts 20 back from the newest");
  assert.equal(cold.messages.at(-1).event_id, seeded[29].event_id);
  assert.equal(cold.newest_event_id, seeded[29].event_id);
  assert.match(cold.note, /newest 20/);

  // Long bodies are capped by default and flagged; the full text is available on request.
  const long = cold.messages.find((m) => m.body_truncated);
  assert.ok(long, "an essay in the window is truncated");
  assert.equal(long.body_chars, essay.length);
  assert.ok(long.body.length <= 2001 && long.body.endsWith("…"));
  const full = await call("get_event", { room_id: ROOM, event_id: long.event_id });
  assert.equal(full.body.length, essay.length, "get_event returns the full body by default");
  assert.equal(full.body_truncated, undefined);
  const uncapped = await call("read_messages", { room_id: ROOM, limit: 30, max_body_chars: 0 });
  assert.ok(uncapped.messages.every((m) => !m.body_truncated), "max_body_chars=0 disables the cap");
  const tight = await call("read_messages", { room_id: ROOM, limit: 5, max_body_chars: 10 });
  assert.ok(tight.messages.every((m) => m.body.length <= 11));

  // With a marker far back, unread pages the backlog oldest-first instead of dropping it.
  await call("mark_read", { room_id: ROOM, event_id: seeded[2].event_id });
  const page1 = await call("unread", { room_id: ROOM, limit: 10 });
  assert.equal(page1.marker_found, true);
  assert.equal(page1.total_unread, 27);
  assert.equal(page1.count, 10);
  assert.equal(page1.has_more, true);
  assert.equal(page1.messages[0].event_id, seeded[3].event_id, "oldest unread first");
  assert.equal(page1.newest_event_id, seeded[12].event_id);
  assert.match(page1.note, /oldest 10 of 27/);
  await call("mark_read", { room_id: ROOM, event_id: page1.newest_event_id });
  const page2 = await call("unread", { room_id: ROOM, limit: 100 });
  assert.equal(page2.total_unread, 17);
  assert.equal(page2.has_more, false);
  assert.equal(page2.messages[0].event_id, seeded[13].event_id, "continues exactly where the previous page stopped");
  assert.equal(page2.note, undefined);
  // Search matches against the full text even though the returned body is capped.
  const found = await call("search_messages", { room_id: ROOM, contains: "very long post" });
  assert.equal(found.count, 3);
  assert.ok(found.matches.every((m) => m.body_truncated));
});
