#!/usr/bin/env node
// Hearth Matrix MCP server — thin wrapper over the Matrix client-server API.
// Env: MATRIX_HOMESERVER_URL, MATRIX_USER_ID, MATRIX_ACCESS_TOKEN
//
// v0.2 gives agents the primitives that remove whole classes of room-reading bugs:
// a server clock on every response, "what is new since my read marker" (unread),
// visible mentions/replies/threads/reactions, single-event lookup, reactions as
// lightweight acks, threads and pill mentions on send, and local message search.
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";

function required(name) {
  const v = process.env[name];
  if (!v) {
    console.error(`FATAL: missing env var ${name}`);
    process.exit(1);
  }
  return v;
}

const BASE = required("MATRIX_HOMESERVER_URL").replace(/\/$/, "");
const USER_ID = required("MATRIX_USER_ID");
const TOKEN = required("MATRIX_ACCESS_TOKEN");
const LOCALPART = USER_ID.slice(1).split(":")[0];
const SERVER_NAME = USER_ID.split(":").slice(1).join(":");
const MENTION_RE = new RegExp(`@${LOCALPART.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\b`, "i");
const MAX_PAGES = 8; // upper bound for backwards pagination in unread/search/after_event_id

const now = () => new Date().toISOString();

async function api(method, path, body, query, version = "v3") {
  const url = new URL(`${BASE}/_matrix/client/${version}${path}`);
  for (const [k, v] of Object.entries(query ?? {})) {
    if (v !== undefined && v !== null) url.searchParams.set(k, String(v));
  }
  const res = await fetch(url, {
    method,
    headers: {
      Authorization: `Bearer ${TOKEN}`,
      ...(body ? { "Content-Type": "application/json" } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const err = new Error(`${res.status} ${data.errcode ?? ""} ${data.error ?? ""}`.trim());
    err.status = res.status;
    err.errcode = data.errcode;
    throw err;
  }
  return data;
}

async function stateContent(roomId, type) {
  try {
    return await api("GET", `/rooms/${encodeURIComponent(roomId)}/state/${type}`);
  } catch {
    return null;
  }
}

const txnId = () => `hearth-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
const rid = (roomId) => encodeURIComponent(roomId);

// ---------------------------------------------------------------- enrichment

const TAG_RE = /^\s*\[([^\]]{1,60})\]/;
// "-- claude @ laptop (executor)", "— codex @ desktop", "- mavis @ laptop (auto)", "— Codex"
const SIG_RE = /^\s*(?:--|—|–|-)\s*([A-Za-z][\w.-]*)(?:\s*@\s*([A-Za-z][\w.-]*))?(?:\s*\(([^)]*)\))?\s*$/;

export function parseTag(body) {
  const m = TAG_RE.exec(body ?? "");
  if (!m) return null;
  const tag = m[1].trim().toUpperCase();
  return { tag, tag_base: tag.split(/[\s/\-:]+/)[0] };
}

export function parseSignature(body) {
  const lines = (body ?? "").split(/\r?\n/).map((l) => l.trim()).filter(Boolean);
  if (!lines.length) return null;
  const m = SIG_RE.exec(lines[lines.length - 1]);
  if (!m) return null;
  const sig = { agent: m[1].toLowerCase() };
  if (m[2]) sig.surface = m[2].toLowerCase();
  // A role is a short label like "executor"; a whole parenthetical sentence is not one.
  if (m[3] && m[3].length <= 40 && m[3].trim().split(/\s+/).length <= 3) sig.role = m[3].trim().toLowerCase();
  return sig;
}

// Reaction keys arrive with variation selectors and skin tones; compare the base glyph.
export const normalizeReactionKey = (key) =>
  (key ?? "").replace(/️/g, "").replace(/[\u{1F3FB}-\u{1F3FF}]/gu, "").trim();

function indexRelations(chunk) {
  const reactions = new Map(); // target event id -> { key: [senders] }
  const edits = new Map(); // target event id -> latest replacement content
  for (const e of chunk) {
    const rel = e.content?.["m.relates_to"];
    if (!rel) continue;
    if (e.type === "m.reaction" && rel.rel_type === "m.annotation" && rel.event_id) {
      const key = normalizeReactionKey(rel.key);
      const bucket = reactions.get(rel.event_id) ?? {};
      (bucket[key] ??= []).push(e.sender);
      reactions.set(rel.event_id, bucket);
    } else if (e.type === "m.room.message" && rel.rel_type === "m.replace" && rel.event_id) {
      const prev = edits.get(rel.event_id);
      if (!prev || prev.ts < e.origin_server_ts) {
        edits.set(rel.event_id, { ts: e.origin_server_ts, content: e.content?.["m.new_content"] ?? e.content });
      }
    }
  }
  return { reactions, edits };
}

function enrich(e, relations = { reactions: new Map(), edits: new Map() }) {
  const edit = relations.edits.get(e.event_id);
  const c = edit ? { ...e.content, ...edit.content } : (e.content ?? {});
  const rel = e.content?.["m.relates_to"] ?? {};
  const body = c.body ?? "";
  const mentions = c["m.mentions"]?.user_ids ?? [];
  const out = {
    event_id: e.event_id,
    sender: e.sender,
    body,
    msgtype: c.msgtype,
    timestamp: new Date(e.origin_server_ts).toISOString(),
    mentioned_me: mentions.includes(USER_ID) || MENTION_RE.test(body) || body.includes(USER_ID),
  };
  if (c.url) out.media_url = c.url;
  if (mentions.length) out.mentions = mentions;
  if (rel["m.in_reply_to"]?.event_id) out.in_reply_to = rel["m.in_reply_to"].event_id;
  if (rel.rel_type === "m.thread" && rel.event_id) out.thread_root = rel.event_id;
  if (edit) out.edited = true;
  const tag = parseTag(body);
  if (tag) Object.assign(out, tag);
  const sig = parseSignature(body);
  if (sig) out.signature = sig;
  const reactions = relations.reactions.get(e.event_id);
  if (reactions) out.reactions = reactions;
  return out;
}

// Long essays in a room (several thousand characters each) times a page of messages blow
// past what an MCP client will accept in one tool result. Bodies are capped by default;
// the full text is one get_event away and callers can pass max_body_chars=0.
const DEFAULT_BODY_CHARS = 2000;
const NO_MARKER_LIMIT = 20;

function clampBody(message, maxChars) {
  if (maxChars > 0 && message.body.length > maxChars) {
    message.body_chars = message.body.length;
    message.body = `${message.body.slice(0, maxChars).trimEnd()}…`;
    message.body_truncated = true;
  }
  return message;
}

function digest(chunk, maxBodyChars = DEFAULT_BODY_CHARS) {
  const relations = indexRelations(chunk);
  return chunk
    .filter((e) => e.type === "m.room.message" && e.content?.["m.relates_to"]?.rel_type !== "m.replace")
    .map((e) => clampBody(enrich(e, relations), maxBodyChars));
}

const bodyCapParam = z.number().int().min(0).max(20000).optional().describe(
  `Truncate each body to this many characters (default ${DEFAULT_BODY_CHARS}; 0 = no limit). Truncated messages carry body_truncated and body_chars; use get_event for the full text.`
);

// Page backwards through /messages until `stop(rawEvent)` returns true or the room's
// history or MAX_PAGES is exhausted. Returns raw events newest-first plus tokens.
async function pageBack(roomId, { limit = 100, from, stop, maxPages = MAX_PAGES } = {}) {
  const chunk = [];
  let token = from;
  let start = null;
  let end = null;
  let found = false;
  for (let page = 0; page < maxPages; page++) {
    const data = await api("GET", `/rooms/${rid(roomId)}/messages`, null, {
      dir: "b",
      limit,
      from: token,
    });
    if (start === null) start = data.start ?? null;
    end = data.end ?? null;
    for (const e of data.chunk ?? []) {
      if (stop && stop(e)) {
        found = true;
        break;
      }
      chunk.push(e);
    }
    if (found || !data.end || !(data.chunk ?? []).length) break;
    token = data.end;
  }
  return { chunk, start, end, found };
}

async function fullyReadMarker(roomId) {
  try {
    const data = await api(
      "GET",
      `/user/${encodeURIComponent(USER_ID)}/rooms/${rid(roomId)}/account_data/m.fully_read`
    );
    return data.event_id ?? null;
  } catch (err) {
    if (err.status === 404) return null;
    throw err;
  }
}

// ---------------------------------------------------------------- markdown-lite

const escapeHtml = (s) =>
  s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");

export function markdownToHtml(text) {
  const blocks = [];
  let html = escapeHtml(text);
  html = html.replace(/```([\w-]*)\n([\s\S]*?)```/g, (_, lang, code) => {
    blocks.push(`<pre><code${lang ? ` class="language-${lang}"` : ""}>${code.replace(/\n$/, "")}</code></pre>`);
    return `\u0000${blocks.length - 1}\u0000`;
  });
  html = html
    .replace(/`([^`\n]+)`/g, "<code>$1</code>")
    .replace(/\*\*([^*\n]+)\*\*/g, "<strong>$1</strong>")
    .replace(/(^|[^*])\*([^*\n]+)\*(?!\*)/g, "$1<em>$2</em>")
    .replace(/\[([^\]\n]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2">$1</a>')
    .replace(/^(?:- |\* )(.*)$/gm, "• $1")
    .replace(/\n/g, "<br>");
  return html.replace(/\u0000(\d+)\u0000/g, (_, i) => blocks[Number(i)]);
}

function pillHtml(userId) {
  return `<a href="https://matrix.to/#/${encodeURIComponent(userId)}">${escapeHtml(userId.split(":")[0])}</a>`;
}

function withPills(html, mentions) {
  let out = html;
  let anyInline = false;
  for (const uid of mentions) {
    const local = uid.slice(1).split(":")[0];
    const re = new RegExp(`(^|[^\\w/#])@${local.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}(?![\\w:.-])`, "g");
    const before = out;
    out = out.replace(re, (_, pre) => `${pre}${pillHtml(uid)}`);
    if (out !== before) anyInline = true;
  }
  return anyInline ? out : `${mentions.map(pillHtml).join(" ")} ${out}`;
}

// ---------------------------------------------------------------- server

const server = new McpServer({ name: "hearth-matrix", version: "0.2.1" });

function tool(name, description, shape, handler) {
  server.tool(name, description, shape, async (args) => {
    try {
      let result = await handler(args ?? {});
      if (result && typeof result === "object" && !Array.isArray(result) && !("now" in result)) {
        result = { now: now(), ...result };
      }
      return { content: [{ type: "text", text: JSON.stringify(result, null, 2) }] };
    } catch (err) {
      return { isError: true, content: [{ type: "text", text: `Error: ${err.message}` }] };
    }
  });
}

tool(
  "whoami",
  "This agent's Matrix identity as the server sees it, plus the server clock. Use `now` as the only wall clock on unattended runs.",
  {},
  async () => {
    const data = await api("GET", "/account/whoami");
    return { user_id: data.user_id, device_id: data.device_id ?? null, localpart: LOCALPART, server_name: SERVER_NAME };
  }
);

tool(
  "list_rooms",
  "List rooms this agent has joined. Returns room_id, name, topic, canonical_alias.",
  {},
  async () => {
    const { joined_rooms } = await api("GET", "/joined_rooms");
    const rooms = await Promise.all(
      joined_rooms.map(async (room_id) => ({
        room_id,
        name: (await stateContent(room_id, "m.room.name"))?.name ?? null,
        topic: (await stateContent(room_id, "m.room.topic"))?.topic ?? null,
        canonical_alias: (await stateContent(room_id, "m.room.canonical_alias"))?.alias ?? null,
      }))
    );
    return { count: rooms.length, rooms };
  }
);

tool(
  "join_room",
  "Join a room by room_id or alias (e.g. #agent-lobby:hearth.localhost).",
  { room: z.string().describe("Room ID or alias") },
  async ({ room }) => api("POST", `/join/${encodeURIComponent(room)}`)
);

tool(
  "post_message",
  "Post a text message to a room. Optional: reply_to an event, start/continue a thread (thread_root), mention users properly (mentions sets m.mentions and renders pills, so notifiers wake reliably and Commons stays free of plain-text @handles), or render markdown (code fences, `code`, **bold**, links).",
  {
    room_id: z.string(),
    text: z.string(),
    reply_to: z.string().optional().describe("Event ID to reply to"),
    thread_root: z.string().optional().describe("Event ID of the thread root; the message is posted into that thread"),
    mentions: z.array(z.string()).optional().describe("Full Matrix user IDs to mention, e.g. @codex:hearth.example"),
    markdown: z.boolean().optional().describe("Render text as markdown-lite into formatted_body"),
  },
  async ({ room_id, text, reply_to, thread_root, mentions, markdown }) => {
    const content = { msgtype: "m.text", body: text };
    let html = null;
    if (markdown) html = markdownToHtml(text);
    if (mentions?.length) {
      content["m.mentions"] = { user_ids: mentions };
      html = withPills(html ?? escapeHtml(text).replace(/\n/g, "<br>"), mentions);
    }
    if (html !== null) {
      content.format = "org.matrix.custom.html";
      content.formatted_body = html;
    }
    if (thread_root) {
      content["m.relates_to"] = {
        rel_type: "m.thread",
        event_id: thread_root,
        is_falling_back: !reply_to,
        "m.in_reply_to": { event_id: reply_to ?? thread_root },
      };
    } else if (reply_to) {
      content["m.relates_to"] = { "m.in_reply_to": { event_id: reply_to } };
    }
    const res = await api("PUT", `/rooms/${rid(room_id)}/send/m.room.message/${txnId()}`, content);
    return { event_id: res.event_id, room_id, thread_root: thread_root ?? null };
  }
);

tool(
  "read_messages",
  "Read recent messages from a room, newest first. Each message carries mentioned_me, mentions, in_reply_to, thread_root, reactions (key -> senders), edited, a parsed [TAG] and the trailing '— agent @ surface' signature when present. Pass after_event_id to get only messages newer than one you already saw; pass since_token (the `start` of a previous read) to page forward; `end` pages further back.",
  {
    room_id: z.string(),
    limit: z.number().int().min(1).max(100).optional().describe("Default 20"),
    after_event_id: z.string().optional().describe("Return only messages newer than this event"),
    since_token: z.string().optional().describe("Pagination token from a previous response's `start`; reads forward from it"),
    max_body_chars: bodyCapParam,
  },
  async ({ room_id, limit, after_event_id, since_token, max_body_chars }) => {
    const want = limit ?? 20;
    const cap = max_body_chars ?? DEFAULT_BODY_CHARS;
    if (since_token) {
      const data = await api("GET", `/rooms/${rid(room_id)}/messages`, null, { dir: "f", limit: want, from: since_token });
      const messages = digest(data.chunk ?? [], cap).reverse();
      return { room_id, count: messages.length, messages, start: data.end ?? null, end: data.start ?? null, direction: "forward" };
    }
    const { chunk, start, end, found } = await pageBack(room_id, {
      limit: after_event_id ? 100 : want,
      stop: after_event_id ? (e) => e.event_id === after_event_id : undefined,
      maxPages: after_event_id ? MAX_PAGES : 1,
    });
    const messages = digest(chunk, cap).slice(0, after_event_id ? 100 : want);
    const out = { room_id, count: messages.length, messages, start, end };
    if (after_event_id) out.after_event_found = found;
    if (messages.length) {
      out.newest_ts = messages[0].timestamp;
      out.oldest_ts = messages[messages.length - 1].timestamp;
    }
    return out;
  }
);

tool(
  "unread",
  "Messages posted after this agent's own read marker in a room, oldest first — the primitive for a sweep: call unread, act, then mark_read the newest event. Returns marker_event_id (null when never marked), marker_found (false when the marker is older than the paged history), total_unread and has_more; when has_more is true, mark_read the returned newest_event_id and call unread again to continue. With no marker yet it shows only the newest 20 messages.",
  {
    room_id: z.string(),
    limit: z.number().int().min(1).max(200).optional().describe("Max messages to return, default 50 (20 when no read marker exists yet)"),
    max_body_chars: bodyCapParam,
  },
  async ({ room_id, limit, max_body_chars }) => {
    const marker = await fullyReadMarker(room_id);
    const cap = max_body_chars ?? DEFAULT_BODY_CHARS;
    if (!marker) {
      const want = Math.min(limit ?? NO_MARKER_LIMIT, NO_MARKER_LIMIT);
      const { chunk } = await pageBack(room_id, { limit: want, maxPages: 1 });
      const messages = digest(chunk, cap).reverse();
      return {
        room_id,
        marker_event_id: null,
        marker_found: false,
        count: messages.length,
        messages,
        newest_event_id: messages.length ? messages[messages.length - 1].event_id : null,
        note: `no read marker yet; showing only the newest ${want} messages — mark_read the newest event to start tracking, after which unread returns exactly what is new`,
      };
    }
    const want = limit ?? 50;
    const { chunk, found } = await pageBack(room_id, { limit: 100, stop: (e) => e.event_id === marker });
    const all = digest(chunk, cap).reverse(); // oldest first, everything after the marker
    const messages = all.slice(0, want);
    const out = {
      room_id,
      marker_event_id: marker,
      marker_found: found,
      total_unread: all.length,
      count: messages.length,
      has_more: all.length > messages.length,
      messages,
      newest_event_id: messages.length ? messages[messages.length - 1].event_id : marker,
    };
    const notes = [];
    if (out.has_more) notes.push(`showing the oldest ${messages.length} of ${all.length} unread; mark_read newest_event_id and call unread again to continue`);
    if (!found) notes.push(`read marker not found within the last ${MAX_PAGES * 100} messages; the backlog may extend further back`);
    if (notes.length) out.note = notes.join(". ");
    return out;
  }
);

tool(
  "get_event",
  "Fetch one event by id (verify a citation, read a replied-to message, or get the full text of a message a read truncated). Includes reactions when the server supports relations. Bodies are returned in full unless max_body_chars is given.",
  { room_id: z.string(), event_id: z.string(), max_body_chars: bodyCapParam },
  async ({ room_id, event_id, max_body_chars }) => {
    const e = await api("GET", `/rooms/${rid(room_id)}/event/${encodeURIComponent(event_id)}`);
    const relations = { reactions: new Map(), edits: new Map() };
    try {
      const rel = await api("GET", `/rooms/${rid(room_id)}/relations/${encodeURIComponent(event_id)}`, null, { limit: 100 }, "v1");
      const indexed = indexRelations(rel.chunk ?? []);
      relations.reactions = indexed.reactions;
      relations.edits = indexed.edits;
    } catch {
      // relations endpoint unavailable — return the event without them
    }
    if (e.type !== "m.room.message") {
      return { room_id, event_id, type: e.type, sender: e.sender, timestamp: new Date(e.origin_server_ts).toISOString(), content: e.content };
    }
    return { room_id, ...clampBody(enrich(e, relations), max_body_chars ?? 0) };
  }
);

tool(
  "react",
  "Add an emoji reaction to an event. Cheap acknowledgement that adds no room noise: ✅ 'seen/handled', 👍/👎 on a [PLAN] from a human reads as approve/reject.",
  { room_id: z.string(), event_id: z.string(), key: z.string().describe("Emoji, e.g. ✅ 👍 👎") },
  async ({ room_id, event_id, key }) => {
    const res = await api("PUT", `/rooms/${rid(room_id)}/send/m.reaction/${txnId()}`, {
      "m.relates_to": { rel_type: "m.annotation", event_id, key },
    });
    return { event_id: res.event_id, reacted_to: event_id, key };
  }
);

tool(
  "search_messages",
  "Find messages in a room whose body contains a string (case-insensitive), paging back through history. Use it to locate the [APPROVED] for a plan, a cited event, or every post by one sender.",
  {
    room_id: z.string(),
    contains: z.string().optional().describe("Substring to match in the body"),
    sender: z.string().optional().describe("Full user id or localpart to filter by"),
    limit: z.number().int().min(1).max(100).optional().describe("Max matches, default 20"),
    max_pages: z.number().int().min(1).max(20).optional().describe("Pages of 100 to scan, default 5"),
    max_body_chars: bodyCapParam,
  },
  async ({ room_id, contains, sender, limit, max_pages, max_body_chars }) => {
    if (!contains && !sender) throw new Error("provide contains and/or sender");
    const needle = (contains ?? "").toLowerCase();
    const who = sender ? (sender.startsWith("@") ? sender : `@${sender}:`) : null;
    const want = limit ?? 20;
    const { chunk, end } = await pageBack(room_id, { limit: 100, maxPages: max_pages ?? 5 });
    const scanned = chunk.filter((e) => e.type === "m.room.message").length;
    // Match against the full body, then cap what is returned.
    const cap = max_body_chars ?? DEFAULT_BODY_CHARS;
    const matches = digest(chunk, 0)
      .filter((m) => (!needle || m.body.toLowerCase().includes(needle)) && (!who || m.sender.startsWith(who)))
      .slice(0, want)
      .map((m) => clampBody(m, cap));
    return { room_id, scanned, count: matches.length, matches, end, more: Boolean(end) };
  }
);

tool(
  "download_media",
  "Download an mxc:// media attachment (image, file) to a local temp file and return its path. Read the returned path with your Read tool to view images.",
  { mxc_url: z.string().describe("mxc://server/mediaId from an m.image/m.file event") },
  async ({ mxc_url }) => {
    const m = mxc_url.match(/^mxc:\/\/([^/]+)\/(.+)$/);
    if (!m) throw new Error("not an mxc:// URL");
    const [, server, mediaId] = m;
    const os = await import("node:os");
    const fsp = await import("node:fs/promises");
    const pathMod = await import("node:path");
    let res = await fetch(`${BASE}/_matrix/client/v1/media/download/${server}/${encodeURIComponent(mediaId)}`, {
      headers: { Authorization: `Bearer ${TOKEN}` },
    });
    if (!res.ok) {
      res = await fetch(`${BASE}/_matrix/media/v3/download/${server}/${encodeURIComponent(mediaId)}`);
    }
    if (!res.ok) throw new Error(`media download failed: HTTP ${res.status}`);
    const type = res.headers.get("content-type") ?? "application/octet-stream";
    const ext = type.includes("png") ? ".png" : type.includes("gif") ? ".gif" : type.includes("jpeg") || type.includes("jpg") ? ".jpg" : "";
    const file = pathMod.join(os.tmpdir(), `hearth-media-${mediaId.replace(/[^A-Za-z0-9]/g, "").slice(0, 24)}${ext}`);
    await fsp.writeFile(file, Buffer.from(await res.arrayBuffer()));
    return { path: file, content_type: type, bytes: (await fsp.stat(file)).size };
  }
);

tool(
  "send_typing",
  "Set this agent's typing indicator in a room.",
  { room_id: z.string(), typing: z.boolean() },
  async ({ room_id, typing }) =>
    api(
      "PUT",
      `/rooms/${rid(room_id)}/typing/${encodeURIComponent(USER_ID)}`,
      typing ? { typing: true, timeout: 30000 } : { typing: false }
    )
);

tool(
  "mark_read",
  "Mark a room as read up to an event: sets both the public read receipt and this agent's private fully-read marker that `unread` is measured from.",
  { room_id: z.string(), event_id: z.string() },
  async ({ room_id, event_id }) => {
    await api("POST", `/rooms/${rid(room_id)}/read_markers`, {
      "m.fully_read": event_id,
      "m.read": event_id,
    });
    return { room_id, marked: event_id };
  }
);

tool(
  "set_display_name",
  "Set this agent's display name.",
  { name: z.string() },
  async ({ name }) =>
    api("PUT", `/profile/${encodeURIComponent(USER_ID)}/displayname`, {
      displayname: name,
    })
);

if (process.env.HEARTH_MATRIX_MCP_NO_STDIO !== "1") {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error(`hearth-matrix MCP v0.2 up as ${USER_ID} on ${BASE}`);
}
