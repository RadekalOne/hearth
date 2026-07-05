#!/usr/bin/env node
// Hearth CLI — setup wizard and lifecycle for a Hearth hub. Zero dependencies, Node 20+.
//   hearth init                 configure the hub (local homeserver or bring-your-own)
//   hearth up | down            start/stop the Docker stack
//   hearth setup                create admin user + the 4 standard rooms
//   hearth agent add <name>     give an agent a Matrix identity + MCP config
//   hearth status               health-check everything
import { createInterface } from "node:readline/promises";
import { spawnSync } from "node:child_process";
import { randomBytes } from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const CONFIG_PATH = path.join(ROOT, "hearth.config.json");
const ENV_PATH = path.join(ROOT, ".env");
const SECRETS = path.join(ROOT, "secrets");

const ROOMS = [
  { alias: "agent-lobby", name: "Agent Lobby", topic: "General human/agent collaboration room." },
  { alias: "agent-tasks", name: "Agent Tasks", topic: "Task claiming, status, blockers, and handoffs." },
  { alias: "agent-decisions", name: "Agent Decisions", topic: "Durable decisions and approvals." },
  { alias: "agent-logs", name: "Agent Logs", topic: "Automated status and logging channel." },
];

// ---------------------------------------------------------------- helpers

// Interactive TTY: prompt via readline. Piped stdin (scripts, CI): consume one
// line per question — readline drops buffered lines between sequential questions.
const rl = process.stdin.isTTY
  ? createInterface({ input: process.stdin, output: process.stdout })
  : null;
let pipedLines = null;
async function ask(q, fallback) {
  const prompt = fallback ? `${q} [${fallback}]: ` : `${q}: `;
  let answer;
  if (rl) {
    answer = (await rl.question(prompt)).trim();
  } else {
    pipedLines ??= fs.readFileSync(0, "utf8").split(/\r?\n/);
    answer = (pipedLines.shift() ?? "").trim();
    console.log(prompt + (/password/i.test(q) ? "••••••" : answer || fallback || ""));
  }
  return answer || fallback || "";
}

function loadConfig() {
  if (!fs.existsSync(CONFIG_PATH)) die("No hearth.config.json — run `hearth init` first.");
  return JSON.parse(fs.readFileSync(CONFIG_PATH, "utf8"));
}
function saveConfig(cfg) {
  fs.writeFileSync(CONFIG_PATH, JSON.stringify(cfg, null, 2) + "\n");
}
function writeEnvFile(file, vars) {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, Object.entries(vars).map(([k, v]) => `${k}=${v}`).join("\n") + "\n");
}
function readEnvFile(file) {
  const vars = {};
  if (!fs.existsSync(file)) return vars;
  for (const line of fs.readFileSync(file, "utf8").split(/\r?\n/)) {
    const m = line.match(/^([A-Z_]+)=(.*)$/);
    if (m) vars[m[1]] = m[2];
  }
  return vars;
}
function die(msg) {
  console.error(`✗ ${msg}`);
  process.exit(1);
}
function ok(msg) {
  console.log(`✓ ${msg}`);
}
function compose(...args) {
  const res = spawnSync("docker", ["compose", ...args], { cwd: ROOT, stdio: "inherit" });
  if (res.error) die("Docker not found. Install Docker Desktop: https://www.docker.com/products/docker-desktop/");
  if (res.status !== 0) die(`docker compose ${args[0]} failed`);
}

async function matrix(base, method, pathname, { token, body, okCodes = [], okStatuses = [] } = {}) {
  const res = await fetch(`${base.replace(/\/$/, "")}/_matrix/client/v3${pathname}`, {
    method,
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(body ? { "Content-Type": "application/json" } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok && !okCodes.includes(data.errcode) && !okStatuses.includes(res.status)) {
    throw new Error(`${method} ${pathname} → ${res.status} ${data.errcode ?? ""} ${data.error ?? ""}`);
  }
  return { status: res.status, data };
}

// Register a user, completing the registration-token UIA flow if the server asks for it.
async function registerUser(base, username, password, registrationToken) {
  // A 401 with a session id is a User-Interactive Auth challenge, not an error.
  const body = { username, password, initial_device_display_name: "hearth" };
  let { status, data } = await matrix(base, "POST", "/register", {
    body, okStatuses: [401],
  });
  for (let i = 0; i < 3 && status === 401 && data.session; i++) {
    const stages = (data.flows ?? []).flatMap((f) => f.stages ?? []);
    const done = data.completed ?? [];
    const next = stages.find((s) => !done.includes(s));
    const auth =
      next === "m.login.registration_token"
        ? { type: next, token: registrationToken, session: data.session }
        : { type: "m.login.dummy", session: data.session };
    ({ status, data } = await matrix(base, "POST", "/register", {
      body: { ...body, auth }, okStatuses: [401],
    }));
  }
  if (!data.access_token) throw new Error(`registration failed: ${JSON.stringify(data)}`);
  return data; // { user_id, access_token }
}

async function login(base, username, password) {
  const { data } = await matrix(base, "POST", "/login", {
    body: {
      type: "m.login.password",
      identifier: { type: "m.id.user", user: username },
      password,
      initial_device_display_name: "hearth",
    },
  });
  return data; // { user_id, access_token }
}

// ---------------------------------------------------------------- commands

async function cmdInit() {
  console.log("\n🔥 Hearth setup wizard\n");
  const mode = (await ask("Homeserver mode — 'local' (bundled, recommended) or 'byo'", "local")).toLowerCase();
  if (!["local", "byo"].includes(mode)) die("mode must be 'local' or 'byo'");

  let serverName, homeserverUrl, ports = {};
  if (mode === "local") {
    serverName = await ask("Server name (domain part of user IDs)", "hearth.localhost");
    ports.matrix = await ask("Matrix port", "6167");
    ports.element = await ask("Element port", "8009");
    homeserverUrl = `http://localhost:${ports.matrix}`;
  } else {
    homeserverUrl = await ask("Existing homeserver URL (e.g. https://matrix.example.org)");
    if (!homeserverUrl) die("homeserver URL is required in byo mode");
    serverName = await ask("Server name (domain in your user IDs)", new URL(homeserverUrl).hostname);
  }
  ports.memory = await ask("Memory service / dashboard port", "8010");

  const registrationToken = randomBytes(24).toString("base64url");
  writeEnvFile(ENV_PATH, {
    HEARTH_MODE: mode,
    HEARTH_SERVER_NAME: serverName,
    HEARTH_HOMESERVER_URL: homeserverUrl,
    HEARTH_REGISTRATION_TOKEN: registrationToken,
    HEARTH_MATRIX_PORT: ports.matrix ?? "6167",
    HEARTH_ELEMENT_PORT: ports.element ?? "8009",
    HEARTH_MEMORY_PORT: ports.memory,
    COMPOSE_PROFILES: mode === "local" ? "local-homeserver" : "",
  });
  saveConfig({ mode, serverName, homeserverUrl, ports, agents: [], rooms: {} });

  if (mode === "local") {
    const elementCfg = path.join(ROOT, "config", "element-config.json");
    const cfg = JSON.parse(fs.readFileSync(elementCfg, "utf8"));
    cfg.default_server_config["m.homeserver"] = { base_url: homeserverUrl, server_name: serverName };
    fs.writeFileSync(elementCfg, JSON.stringify(cfg, null, 2) + "\n");
  }

  ok(`Config written (.env + hearth.config.json), mode=${mode}`);
  console.log("\nNext:  hearth up   then   hearth setup\n");
}

async function cmdUp() {
  const env = readEnvFile(ENV_PATH);
  const files = env.HEARTH_EXPOSE === "1"
    ? ["-f", "docker-compose.yml", "-f", "docker-compose.expose.yml"]
    : [];
  compose(...files, "up", "-d", "--build");
  ok("Stack is starting. Run `hearth status` to check health.");
}
async function cmdDown() {
  compose("down");
  ok("Stack stopped.");
}

async function waitForHomeserver(base, tries = 30) {
  for (let i = 0; i < tries; i++) {
    try {
      const res = await fetch(`${base.replace(/\/$/, "")}/_matrix/client/versions`);
      if (res.ok) return;
    } catch {}
    await new Promise((r) => setTimeout(r, 2000));
  }
  die(`homeserver at ${base} not reachable — is the stack up?`);
}

async function cmdSetup() {
  const cfg = loadConfig();
  const env = readEnvFile(ENV_PATH);
  await waitForHomeserver(cfg.homeserverUrl);

  console.log("\nCreate your (human) admin account:");
  const username = await ask("Admin username", "admin");
  const password = await ask("Admin password (stored only in secrets/)");
  if (!password) die("password required");

  let creds;
  try {
    creds = await registerUser(cfg.homeserverUrl, username, password, env.HEARTH_REGISTRATION_TOKEN);
    ok(`Registered ${creds.user_id}`);
  } catch (err) {
    console.log(`Registration failed (${err.message}); trying login instead…`);
    creds = await login(cfg.homeserverUrl, username, password);
    ok(`Logged in as ${creds.user_id}`);
  }
  writeEnvFile(path.join(SECRETS, "admin.env"), {
    MATRIX_HOMESERVER_URL: cfg.homeserverUrl,
    MATRIX_USER_ID: creds.user_id,
    MATRIX_ACCESS_TOKEN: creds.access_token,
  });

  for (const room of ROOMS) {
    const fullAlias = `#${room.alias}:${cfg.serverName}`;
    try {
      const { data } = await matrix(cfg.homeserverUrl, "POST", "/createRoom", {
        token: creds.access_token,
        body: {
          name: room.name, topic: room.topic, room_alias_name: room.alias,
          preset: "private_chat", visibility: "private",
        },
      });
      cfg.rooms[room.alias] = data.room_id;
      ok(`Created ${fullAlias} (${data.room_id})`);
    } catch {
      const { data } = await matrix(cfg.homeserverUrl, "GET",
        `/directory/room/${encodeURIComponent(fullAlias)}`,
        { token: creds.access_token });
      cfg.rooms[room.alias] = data.room_id;
      ok(`${fullAlias} already exists (${data.room_id})`);
    }
  }
  saveConfig(cfg);
  console.log("\nDone. Open Element and log in as your admin user. Next: hearth agent add <name>\n");
}

// Invite (as admin) + join (as the new member) all standard rooms.
async function joinStandardRooms(cfg, adminToken, creds) {
  for (const [alias, roomId] of Object.entries(cfg.rooms)) {
    await matrix(cfg.homeserverUrl, "POST", `/rooms/${encodeURIComponent(roomId)}/invite`, {
      token: adminToken, body: { user_id: creds.user_id },
      okCodes: ["M_FORBIDDEN"], // already invited/joined
    });
    await matrix(cfg.homeserverUrl, "POST", `/join/${encodeURIComponent(roomId)}`, {
      token: creds.access_token, body: {},
    });
    ok(`${creds.user_id} joined #${alias}`);
  }
}

// Write a self-contained wrapper next to the agent's env file: it loads the
// credentials and starts the Matrix MCP server. MCP client configs then point
// at the wrapper and never contain tokens.
function writeAgentWrapper(name) {
  const matrixServer = path.join(ROOT, "mcp", "matrix", "index.mjs");
  const wrapperPath = path.join(SECRETS, "agents", `${name}.mjs`);
  fs.writeFileSync(wrapperPath, `// Auto-generated by hearth: Matrix MCP server for agent "${name}".
import fs from "node:fs/promises";
const text = await fs.readFile(new URL("./${name}.env", import.meta.url), "utf8");
for (const line of text.split(/\\r?\\n/)) {
  const m = line.match(/^([A-Z_]+)=(.*)$/);
  if (m && !process.env[m[1]]) process.env[m[1]] = m[2];
}
await import(${JSON.stringify(pathToFileURL(matrixServer).href)});
`);
  return wrapperPath;
}

function ensureMatrixDeps() {
  if (fs.existsSync(path.join(ROOT, "mcp", "matrix", "node_modules"))) return;
  console.log("Installing Matrix MCP server dependencies (one-time)…");
  const res = spawnSync("npm", ["install", "--no-fund", "--no-audit"], {
    cwd: path.join(ROOT, "mcp", "matrix"), stdio: "inherit", shell: true,
  });
  if (res.status !== 0) console.log("⚠ npm install failed — run it manually in mcp/matrix/");
}

function mcpSnippets(cfg, name, wrapperPath) {
  const memoryUrl = `http://localhost:${cfg.ports?.memory ?? 8010}/mcp`;
  const w = wrapperPath.replaceAll("\\", "\\\\");
  return `
── Connect this agent (no tokens needed — the wrapper loads them) ─

▸ Claude Code:
  claude mcp add hearth-matrix -- node "${wrapperPath}"
  claude mcp add --transport http hearth-memory ${memoryUrl}

▸ Codex (~/.codex/config.toml):
  [mcp_servers.hearth-matrix]
  command = "node"
  args = ["${w}"]

▸ Generic MCP (.mcp.json style):
  { "mcpServers": {
      "hearth-matrix": { "command": "node", "args": ["${w}"] },
      "hearth-memory": { "type": "http", "url": "${memoryUrl}" } } }

Credentials: ${path.join(SECRETS, "agents", `${name}.env`)}  (gitignored; treat like a password)
Memory MCP (${memoryUrl}) is reachable only where the hub runs — use an SSH
tunnel from other machines, or skip it.
───────────────────────────────────────────────────────────────────`;
}

async function cmdAgentAdd(name, flags) {
  if (!name || !/^[a-z0-9._=-]+$/.test(name)) die("usage: hearth agent add <name>  (lowercase, no spaces)");
  const cfg = loadConfig();
  const env = readEnvFile(ENV_PATH);
  const adminEnv = readEnvFile(path.join(SECRETS, "admin.env"));
  if (!adminEnv.MATRIX_ACCESS_TOKEN) die("No admin credentials — run `hearth setup` first.");

  let creds;
  if (flags.includes("--existing")) {
    const password = await ask(`Password for existing user ${name}`);
    creds = await login(cfg.homeserverUrl, name, password);
  } else {
    const password = randomBytes(18).toString("base64url");
    creds = await registerUser(cfg.homeserverUrl, name, password, env.HEARTH_REGISTRATION_TOKEN);
    ok(`Registered ${creds.user_id} (random password; access token is the credential)`);
  }

  await joinStandardRooms(cfg, adminEnv.MATRIX_ACCESS_TOKEN, creds);
  await matrix(cfg.homeserverUrl, "PUT",
    `/profile/${encodeURIComponent(creds.user_id)}/displayname`,
    { token: creds.access_token, body: { displayname: name } });

  const agentEnvPath = path.join(SECRETS, "agents", `${name}.env`);
  writeEnvFile(agentEnvPath, {
    MATRIX_HOMESERVER_URL: cfg.homeserverUrl,
    MATRIX_USER_ID: creds.user_id,
    MATRIX_ACCESS_TOKEN: creds.access_token,
  });
  const wrapperPath = writeAgentWrapper(name);
  ensureMatrixDeps();
  if (!cfg.agents.some((a) => a.name === name)) {
    cfg.agents.push({ name, userId: creds.user_id });
    saveConfig(cfg);
  }
  console.log(mcpSnippets(cfg, name, wrapperPath));
}

async function cmdUserAdd(name) {
  if (!name || !/^[a-z0-9._=-]+$/.test(name)) die("usage: hearth user add <name>  (lowercase, no spaces)");
  const cfg = loadConfig();
  const env = readEnvFile(ENV_PATH);
  const adminEnv = readEnvFile(path.join(SECRETS, "admin.env"));
  if (!adminEnv.MATRIX_ACCESS_TOKEN) die("No admin credentials — run `hearth setup` first.");

  const password =
    (await ask(`Password for ${name} (leave empty to generate)`)) ||
    randomBytes(12).toString("base64url");
  let creds;
  try {
    creds = await registerUser(cfg.homeserverUrl, name, password, env.HEARTH_REGISTRATION_TOKEN);
    ok(`Registered ${creds.user_id}`);
  } catch (err) {
    die(`Could not register '${name}': ${err.message}`);
  }
  await joinStandardRooms(cfg, adminEnv.MATRIX_ACCESS_TOKEN, creds);

  cfg.users ??= [];
  if (!cfg.users.some((u) => u.name === name)) {
    cfg.users.push({ name, userId: creds.user_id });
    saveConfig(cfg);
  }

  const elementUrl = env.HEARTH_PUBLIC_ELEMENT_HOST
    ? `https://${env.HEARTH_PUBLIC_ELEMENT_HOST}`
    : cfg.mode === "local" ? `http://localhost:${cfg.ports.element ?? 8009}` : "https://app.element.io";
  console.log(`
── Send this to ${name} ───────────────────────────────────────────

You've been added to a Hearth hub. To join:
  1. Open ${elementUrl}${cfg.mode === "byo" ? `\n     and set the homeserver to ${cfg.homeserverUrl}` : ""}
  2. Sign in as:  ${creds.user_id}
     Password:    ${password}
  3. You're already in #agent-lobby, #agent-tasks, #agent-decisions,
     and #agent-logs. Say hi in the lobby — the agents can see you.

(Shown once — it isn't stored anywhere. Change it in Element:
Settings → General → Change password.)
───────────────────────────────────────────────────────────────────`);
}

async function cmdLink(code) {
  if (!code) {
    // Export: print a link code for onboarding another machine.
    const cfg = loadConfig();
    const env = readEnvFile(ENV_PATH);
    const adminEnv = readEnvFile(path.join(SECRETS, "admin.env"));
    if (!adminEnv.MATRIX_ACCESS_TOKEN) die("No admin credentials — run `hearth setup` first.");
    if (!cfg.homeserverUrl.startsWith("https://") && !cfg.homeserverUrl.includes("localhost")) {
      console.log("⚠ homeserverUrl is not HTTPS — a linked machine may not reach it.");
    }
    const payload = {
      v: 1, serverName: cfg.serverName, homeserverUrl: cfg.homeserverUrl,
      ports: cfg.ports, rooms: cfg.rooms,
      registrationToken: env.HEARTH_REGISTRATION_TOKEN, admin: adminEnv,
    };
    console.log(`Hub link code for ${cfg.serverName} — CONTAINS ADMIN CREDENTIALS,
share only over a secure channel and only with machines you trust:\n`);
    console.log("HEARTH1." + Buffer.from(JSON.stringify(payload)).toString("base64url"));
    console.log(`\nOn the other machine, inside a hearth checkout:
  node cli/hearth.mjs link <code>
Then: hearth agent add <name>, hearth user add <name>, hearth status.`);
  } else {
    // Import: configure this checkout to manage the hub remotely.
    if (!code.startsWith("HEARTH1.")) die("that is not a hearth link code");
    let p;
    try {
      p = JSON.parse(Buffer.from(code.slice(8), "base64url").toString());
    } catch {
      die("could not decode link code (truncated?)");
    }
    saveConfig({
      mode: "remote", serverName: p.serverName, homeserverUrl: p.homeserverUrl,
      ports: p.ports ?? {}, agents: [], users: [], rooms: p.rooms ?? {},
    });
    writeEnvFile(ENV_PATH, {
      HEARTH_MODE: "remote",
      HEARTH_SERVER_NAME: p.serverName,
      HEARTH_HOMESERVER_URL: p.homeserverUrl,
      HEARTH_REGISTRATION_TOKEN: p.registrationToken,
    });
    writeEnvFile(path.join(SECRETS, "admin.env"), p.admin);
    ok(`Linked to ${p.serverName} (${p.homeserverUrl})`);
    console.log("You can now run: hearth agent add <name> · hearth user add <name> · hearth status");
  }
}

// Long-poll /sync as the agent; when someone mentions it, run a command.
// This is what turns the "mailbox" into a "phone that rings".
async function cmdNotify(name, rest) {
  const agentEnv = readEnvFile(path.join(SECRETS, "agents", `${name}.env`));
  if (!agentEnv.MATRIX_ACCESS_TOKEN) die(`no credentials for '${name}' — run: hearth agent add ${name}`);
  const execIdx = rest.indexOf("--exec");
  const command = execIdx >= 0 ? rest.slice(execIdx + 1).join(" ") : null;

  const base = agentEnv.MATRIX_HOMESERVER_URL.replace(/\/$/, "");
  const uid = agentEnv.MATRIX_USER_ID;
  const localpart = uid.slice(1).split(":")[0];
  const mentionRe = new RegExp(`@${localpart}\\b`, "i");

  async function syncOnce(since) {
    const url = new URL(`${base}/_matrix/client/v3/sync`);
    if (since) {
      url.searchParams.set("since", since);
      url.searchParams.set("timeout", "30000");
    } else {
      // First sync: only fetch a token so we react to NEW messages, not history.
      url.searchParams.set("filter", JSON.stringify({ room: { timeline: { limit: 1 } } }));
    }
    const res = await fetch(url, { headers: { Authorization: `Bearer ${agentEnv.MATRIX_ACCESS_TOKEN}` } });
    if (!res.ok) throw new Error(`sync HTTP ${res.status}`);
    return res.json();
  }

  console.log(`👂 ${uid} listening for mentions ("@${localpart}") — Ctrl+C to stop`);
  if (command) console.log(`   on mention → ${command}`);
  let since = (await syncOnce(null)).next_batch;
  for (;;) {
    let data;
    try {
      data = await syncOnce(since);
    } catch (err) {
      console.error(`sync error (${err.message}), retrying in 5s…`);
      await new Promise((r) => setTimeout(r, 5000));
      continue;
    }
    since = data.next_batch;
    for (const [roomId, room] of Object.entries(data.rooms?.join ?? {})) {
      for (const ev of room.timeline?.events ?? []) {
        if (ev.type !== "m.room.message" || ev.sender === uid) continue;
        const body = ev.content?.body ?? "";
        if (!mentionRe.test(body) && !body.includes(uid)) continue;
        const stamp = new Date().toISOString();
        console.log(`[${stamp}] mention from ${ev.sender} in ${roomId}: ${body.slice(0, 120)}`);
        if (command) {
          const res = spawnSync(command, {
            shell: true, stdio: "inherit",
            env: {
              ...process.env,
              HEARTH_ROOM_ID: roomId,
              HEARTH_EVENT_ID: ev.event_id,
              HEARTH_SENDER: ev.sender,
              HEARTH_BODY: body,
            },
          });
          if (res.status !== 0) console.error(`handler exited with ${res.status}`);
        }
      }
    }
  }
}

async function cmdStatus() {
  const cfg = loadConfig();
  const memoryUrl = `http://localhost:${cfg.ports.memory}`;
  try {
    const res = await fetch(`${cfg.homeserverUrl.replace(/\/$/, "")}/_matrix/client/versions`);
    console.log(res.ok ? `✓ homeserver ok (${cfg.homeserverUrl})` : `✗ homeserver HTTP ${res.status}`);
  } catch {
    console.log(`✗ homeserver unreachable (${cfg.homeserverUrl})`);
  }
  try {
    const h = await (await fetch(`${memoryUrl}/health`)).json();
    console.log(`✓ memory ok — ${h.drawers} drawers (dashboard: ${memoryUrl})`);
  } catch {
    console.log(`✗ memory service unreachable (${memoryUrl})`);
  }
  console.log(`  agents: ${cfg.agents.map((a) => a.name).join(", ") || "none yet"}`);
  console.log(`  users:  ${(cfg.users ?? []).map((u) => u.name).join(", ") || "admin only"}`);
  console.log(`  rooms:  ${Object.keys(cfg.rooms).map((r) => "#" + r).join(", ") || "not set up"}`);
}

// ---------------------------------------------------------------- dispatch

const [, , cmd, sub, ...rest] = process.argv;
try {
  if (cmd === "init") await cmdInit();
  else if (cmd === "up") await cmdUp();
  else if (cmd === "down") await cmdDown();
  else if (cmd === "setup") await cmdSetup();
  else if (cmd === "agent" && sub === "add") await cmdAgentAdd(rest[0], rest.slice(1));
  else if (cmd === "user" && sub === "add") await cmdUserAdd(rest[0]);
  else if (cmd === "link") await cmdLink(sub);
  else if (cmd === "notify") await cmdNotify(sub, rest);
  else if (cmd === "status") await cmdStatus();
  else {
    console.log(`Hearth — human–agent collaboration hub

  hearth init                 configure the hub (wizard)
  hearth up | down            start/stop the Docker stack
  hearth setup                create admin user + standard rooms
  hearth agent add <name>     onboard an agent (add --existing for a pre-made user)
  hearth user add <name>      onboard a human teammate (Element login card)
  hearth link [code]          no code: print a hub link code for another machine
                              with code: link this machine to a remote hub
  hearth notify <agent> [--exec "<command>"]
                              watch for @mentions of an agent; run a command on
                              each (env: HEARTH_ROOM_ID/EVENT_ID/SENDER/BODY)
  hearth status               health-check everything`);
  }
} catch (err) {
  die(err.message);
} finally {
  rl?.close();
}
