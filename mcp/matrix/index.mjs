#!/usr/bin/env node
// Hearth Matrix MCP server — thin wrapper over the Matrix client-server API.
// Env: MATRIX_HOMESERVER_URL, MATRIX_USER_ID, MATRIX_ACCESS_TOKEN
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

async function api(method, path, body, query) {
  const url = new URL(`${BASE}/_matrix/client/v3${path}`);
  for (const [k, v] of Object.entries(query ?? {})) {
    if (v !== undefined) url.searchParams.set(k, String(v));
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
    throw new Error(`${res.status} ${data.errcode ?? ""} ${data.error ?? ""}`.trim());
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

const server = new McpServer({ name: "hearth-matrix", version: "0.1.0" });

function tool(name, description, shape, handler) {
  server.tool(name, description, shape, async (args) => {
    try {
      const result = await handler(args ?? {});
      return { content: [{ type: "text", text: JSON.stringify(result, null, 2) }] };
    } catch (err) {
      return { isError: true, content: [{ type: "text", text: `Error: ${err.message}` }] };
    }
  });
}

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
  "Post a text message to a room. Optionally reply to an event.",
  {
    room_id: z.string(),
    text: z.string(),
    reply_to: z.string().optional().describe("Event ID to reply to"),
  },
  async ({ room_id, text, reply_to }) => {
    const content = { msgtype: "m.text", body: text };
    if (reply_to) {
      content["m.relates_to"] = { "m.in_reply_to": { event_id: reply_to } };
    }
    const txn = `hearth-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    return api(
      "PUT",
      `/rooms/${encodeURIComponent(room_id)}/send/m.room.message/${txn}`,
      content
    );
  }
);

tool(
  "read_messages",
  "Read recent messages from a room, newest first.",
  {
    room_id: z.string(),
    limit: z.number().int().min(1).max(100).optional().describe("Default 20"),
  },
  async ({ room_id, limit }) => {
    const data = await api("GET", `/rooms/${encodeURIComponent(room_id)}/messages`, null, {
      dir: "b",
      limit: limit ?? 20,
    });
    const messages = (data.chunk ?? [])
      .filter((e) => e.type === "m.room.message")
      .map((e) => ({
        event_id: e.event_id,
        sender: e.sender,
        body: e.content?.body ?? "",
        msgtype: e.content?.msgtype,
        timestamp: new Date(e.origin_server_ts).toISOString(),
      }));
    return { count: messages.length, messages };
  }
);

tool(
  "send_typing",
  "Set this agent's typing indicator in a room.",
  { room_id: z.string(), typing: z.boolean() },
  async ({ room_id, typing }) =>
    api(
      "PUT",
      `/rooms/${encodeURIComponent(room_id)}/typing/${encodeURIComponent(USER_ID)}`,
      typing ? { typing: true, timeout: 30000 } : { typing: false }
    )
);

tool(
  "mark_read",
  "Mark a room as read up to an event.",
  { room_id: z.string(), event_id: z.string() },
  async ({ room_id, event_id }) =>
    api(
      "POST",
      `/rooms/${encodeURIComponent(room_id)}/receipt/m.read/${encodeURIComponent(event_id)}`,
      {}
    )
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

const transport = new StdioServerTransport();
await server.connect(transport);
console.error(`hearth-matrix MCP up as ${USER_ID} on ${BASE}`);
