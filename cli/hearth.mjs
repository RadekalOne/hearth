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

const PACKAGE_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const ROOT = path.resolve(process.env.HEARTH_ROOT ||
  (fs.existsSync(path.join(process.cwd(), "docker-compose.yml")) ? process.cwd() : PACKAGE_ROOT));
const CONFIG_PATH = path.join(ROOT, "hearth.config.json");
const ENV_PATH = path.join(ROOT, ".env");
const SECRETS = path.join(ROOT, "secrets");
const AGENT_NAME_RE = /^[a-z0-9][a-z0-9._=-]*$/;

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
function isHttpUrl(value) {
  try {
    return ["http:", "https:"].includes(new URL(value).protocol);
  } catch {
    return false;
  }
}
function isHostname(value) {
  return typeof value === "string" && value.length <= 253 &&
    /^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)*[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$/i.test(value);
}
function isSafeEnvMap(value) {
  return value && typeof value === "object" && !Array.isArray(value) &&
    Object.entries(value).every(([key, item]) =>
      /^[A-Z_]+$/.test(key) && typeof item === "string" && !/[\r\n]/.test(item));
}
function commandResult(command, args) {
  const result = spawnSync(command, args, { cwd: ROOT, encoding: "utf8" });
  return {
    ok: !result.error && result.status === 0,
    detail: (result.stdout || result.stderr || result.error?.message || "").trim().split(/\r?\n/)[0],
  };
}
function flagValue(args, name) {
  const exact = args.indexOf(name);
  if (exact >= 0) return args[exact + 1];
  const prefix = `${name}=`;
  return args.find((arg) => arg.startsWith(prefix))?.slice(prefix.length);
}
function readDeploymentConfig(file) {
  if (!file) return {};
  const resolved = path.resolve(process.cwd(), file);
  let cfg;
  try {
    cfg = JSON.parse(fs.readFileSync(resolved, "utf8"));
  } catch (err) {
    die(`could not read deployment config ${resolved}: ${err.message}`);
  }
  if (!cfg || typeof cfg !== "object" || Array.isArray(cfg)) die("deployment config must be a JSON object");
  if (cfg.mode && !["local", "byo"].includes(cfg.mode)) die("deployment config mode must be local or byo");
  if (cfg.mode === "byo" && !isHttpUrl(cfg.homeserverUrl)) {
    die("byo deployment config requires an http(s) homeserverUrl");
  }
  if (cfg.adminUsername && !/^[a-z0-9._=-]+$/i.test(cfg.adminUsername)) {
    die("deployment config adminUsername contains unsupported characters");
  }
  if (cfg.adminPasswordEnv && !/^[A-Z_][A-Z0-9_]*$/.test(cfg.adminPasswordEnv)) {
    die("deployment config adminPasswordEnv must be an environment variable name");
  }
  for (const [name, value] of Object.entries(cfg.ports ?? {})) {
    if (!/^(matrix|element|memory)$/.test(name) || !/^\d+$/.test(String(value)) ||
        Number(value) < 1 || Number(value) > 65535) {
      die(`invalid deployment port ${name}=${value}`);
    }
  }
  if (cfg.public !== undefined) {
    if (!cfg.public || typeof cfg.public !== "object" || Array.isArray(cfg.public)) {
      die("deployment config public must be a JSON object");
    }
    for (const name of ["elementHost", "matrixHost", "memoryHost"]) {
      if (cfg.public[name] !== undefined && !isHostname(cfg.public[name])) {
        die(`deployment config public.${name} must be a hostname without a URL scheme or path`);
      }
    }
    if (!cfg.public.elementHost || !cfg.public.matrixHost) {
      die("deployment config public requires elementHost and matrixHost");
    }
    for (const name of ["certResolver", "proxyNetwork"]) {
      if (cfg.public[name] !== undefined &&
          (typeof cfg.public[name] !== "string" || !/^[a-z0-9][a-z0-9._-]*$/i.test(cfg.public[name]))) {
        die(`deployment config public.${name} contains unsupported characters`);
      }
    }
    if (cfg.mode === "byo") die("deployment config public is only supported with the bundled local homeserver");
    cfg.homeserverUrl ??= `https://${cfg.public.matrixHost}`;
  }
  return cfg;
}
function runDoctor({ json = false } = {}) {
  const checks = [];
  const add = (name, passed, detail, fix = "") => checks.push({ name, passed, detail, fix });
  const major = Number(process.versions.node.split(".")[0]);
  add("Node.js 20+", major >= 20, `Node ${process.versions.node}`, "Install Node.js 20 or newer.");

  const docker = commandResult("docker", ["--version"]);
  add("Docker CLI", docker.ok, docker.detail || "not found", "Install Docker Desktop or Docker Engine.");
  const composeCheck = docker.ok
    ? commandResult("docker", ["compose", "version"])
    : { ok: false, detail: "Docker unavailable" };
  add("Docker Compose", composeCheck.ok, composeCheck.detail, "Install the Docker Compose plugin.");
  const daemon = composeCheck.ok
    ? commandResult("docker", ["info", "--format", "{{.ServerVersion}}"])
    : { ok: false, detail: "Docker unavailable" };
  add("Docker daemon", daemon.ok, daemon.ok ? `server ${daemon.detail}` : daemon.detail,
    "Start Docker Desktop or the Docker service.");

  try {
    fs.accessSync(ROOT, fs.constants.R_OK | fs.constants.W_OK);
    add("Hearth directory", true, ROOT);
  } catch (err) {
    add("Hearth directory", false, err.message, "Choose a writable install directory.");
  }
  const composePath = path.join(ROOT, "docker-compose.yml");
  add("Compose bundle", fs.existsSync(composePath), composePath, "Reinstall the Hearth package.");
  if (fs.existsSync(CONFIG_PATH)) {
    try {
      JSON.parse(fs.readFileSync(CONFIG_PATH, "utf8"));
      add("Existing configuration", true, CONFIG_PATH);
    } catch (err) {
      add("Existing configuration", false, err.message, "Repair or restore hearth.config.json.");
    }
  }

  const passed = checks.every((check) => check.passed);
  if (json) {
    console.log(JSON.stringify({ passed, checks }, null, 2));
  } else {
    console.log("\nHearth doctor\n");
    for (const check of checks) {
      console.log(`${check.passed ? "✓" : "✗"} ${check.name}: ${check.detail}`);
      if (!check.passed && check.fix) console.log(`  fix: ${check.fix}`);
    }
    console.log(passed
      ? "\nReady to install Hearth.\n"
      : "\nResolve the failed checks, then run `hearth doctor` again.\n");
  }
  return { passed, checks };
}
function compose(...args) {
  const res = spawnSync("docker", ["compose", ...args], { cwd: ROOT, stdio: "inherit" });
  if (res.error) die("Docker not found. Install Docker Desktop: https://www.docker.com/products/docker-desktop/");
  if (res.status !== 0) die(`docker compose ${args[0]} failed`);
}

function composeFileArgs(env) {
  const files = [];
  if (env.HEARTH_EXPOSE === "1") {
    files.push("-f", "docker-compose.yml", "-f", "docker-compose.expose.yml");
  }
  if (env.HEARTH_PUBLIC_MEMORY_HOST) {
    if (!files.length) files.push("-f", "docker-compose.yml");
    files.push("-f", "docker-compose.expose-memory.yml");
  }
  return files;
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

async function cmdInit(options = {}) {
  console.log("\n🔥 Hearth setup wizard\n");
  const mode = String(options.mode ??
    await ask("Homeserver mode — 'local' (bundled, recommended) or 'byo'", "local")).toLowerCase();
  if (!["local", "byo"].includes(mode)) die("mode must be 'local' or 'byo'");

  let serverName, homeserverUrl, ports = {};
  if (mode === "local") {
    serverName = String(options.serverName ??
      await ask("Server name (domain part of user IDs)", "hearth.localhost"));
    ports.matrix = String(options.ports?.matrix ?? await ask("Matrix port", "6167"));
    ports.element = String(options.ports?.element ?? await ask("Element port", "8009"));
    homeserverUrl = String(options.homeserverUrl ?? `http://localhost:${ports.matrix}`);
  } else {
    homeserverUrl = String(options.homeserverUrl ??
      await ask("Existing homeserver URL (e.g. https://matrix.example.org)"));
    if (!homeserverUrl) die("homeserver URL is required in byo mode");
    serverName = String(options.serverName ??
      await ask("Server name (domain in your user IDs)", new URL(homeserverUrl).hostname));
  }
  ports.memory = String(options.ports?.memory ??
    await ask("Memory service / dashboard port", "8010"));
  const publicConfig = options.public;

  const registrationToken = randomBytes(24).toString("base64url");
  writeEnvFile(ENV_PATH, {
    HEARTH_MODE: mode,
    HEARTH_SERVER_NAME: serverName,
    HEARTH_HOMESERVER_URL: homeserverUrl,
    HEARTH_REGISTRATION_TOKEN: registrationToken,
    HEARTH_MEMORY_ADMIN_TOKEN: randomBytes(32).toString("base64url"),
    HEARTH_MEMORY_URL: publicConfig?.memoryHost
      ? `https://${publicConfig.memoryHost}`
      : `http://localhost:${ports.memory}`,
    HEARTH_MATRIX_PORT: ports.matrix ?? "6167",
    HEARTH_ELEMENT_PORT: ports.element ?? "8009",
    HEARTH_MEMORY_PORT: ports.memory,
    ...(publicConfig ? {
      HEARTH_EXPOSE: "1",
      HEARTH_PUBLIC_ELEMENT_HOST: publicConfig.elementHost,
      HEARTH_PUBLIC_MATRIX_HOST: publicConfig.matrixHost,
      HEARTH_PUBLIC_MEMORY_HOST: publicConfig.memoryHost ?? "",
      HEARTH_CERTRESOLVER: publicConfig.certResolver ?? "letsencrypt",
      HEARTH_PROXY_NETWORK: publicConfig.proxyNetwork ?? "hearth-proxy",
    } : {}),
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
  if (env.HEARTH_PUBLIC_MEMORY_HOST) {
    if (!env.HEARTH_MEMORY_ADMIN_TOKEN) die("refusing to expose memory without HEARTH_MEMORY_ADMIN_TOKEN (no auth)");
  }
  compose(...composeFileArgs(env), "up", "-d", "--build");
  ok("Stack is starting. Run `hearth status` to check health.");
}
async function cmdDown() {
  compose("down");
  ok("Stack stopped.");
}

async function cmdDoctor(flags) {
  const result = runDoctor({ json: flags.includes("--json") });
  if (!result.passed) process.exitCode = 1;
}

async function cmdInstall(flags) {
  if (flags.includes("--help") || flags.includes("-h")) {
    console.log(`Install Hearth in one guided flow.

Usage:
  create-hearth [--directory hearth] [--yes] [--config deployment.json] [--skip-doctor]
  hearth install [--yes] [--config deployment.json] [--skip-doctor]

--directory <path> install files into this directory (default: ./hearth)
--yes              noninteractive; requires HEARTH_ADMIN_PASSWORD if setup is incomplete
--config <file>    JSON defaults (mode, serverName, homeserverUrl, ports, adminUsername,
                   adminPasswordEnv, public)
--skip-doctor      bypass prerequisite checks (not recommended)`);
    return;
  }

  const yes = flags.includes("--yes");
  const configFile = flagValue(flags, "--config");
  const hasConfigFlag = flags.some((flag) => flag === "--config" || flag.startsWith("--config="));
  if (hasConfigFlag && (!configFile || configFile.startsWith("--"))) {
    die("--config requires a JSON file path");
  }
  const deployment = readDeploymentConfig(configFile);
  if (!flags.includes("--skip-doctor")) {
    const diagnosis = runDoctor();
    if (!diagnosis.passed) die("prerequisite checks failed");
  }

  if (!fs.existsSync(CONFIG_PATH)) {
    if (yes) {
      deployment.mode ??= "local";
      deployment.serverName ??= deployment.mode === "byo"
        ? new URL(deployment.homeserverUrl).hostname
        : "hearth.localhost";
      deployment.ports = {
        matrix: "6167",
        element: "8009",
        memory: "8010",
        ...deployment.ports,
      };
    }
    await cmdInit(deployment);
  } else {
    ok(`Using existing configuration at ${CONFIG_PATH}`);
  }

  await cmdUp();
  const cfg = loadConfig();
  const adminEnv = readEnvFile(path.join(SECRETS, "admin.env"));
  const roomsComplete = ROOMS.every((room) => cfg.rooms?.[room.alias]);
  if (adminEnv.MATRIX_ACCESS_TOKEN && roomsComplete) {
    ok("Admin identity and standard rooms already configured");
    if (!readEnvFile(ENV_PATH).HEARTH_MATRIX_TOKEN) {
      await configureDashboardObserver(cfg, adminEnv.MATRIX_ACCESS_TOKEN);
    }
  } else {
    const passwordEnv = deployment.adminPasswordEnv || "HEARTH_ADMIN_PASSWORD";
    const password = yes ? process.env[passwordEnv] : undefined;
    if (yes && !password) {
      die(`noninteractive setup requires the administrator password in ${passwordEnv}`);
    }
    await cmdSetup({ adminUsername: deployment.adminUsername, adminPassword: password });
  }

  await cmdStatus();
  console.log(`\nHearth installation complete.

Next:
  hearth agent add <name>
  hearth user add <name>

Element and dashboard addresses are shown by \`hearth status\`.\n`);
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

async function cmdSetup(options = {}) {
  const cfg = loadConfig();
  const env = readEnvFile(ENV_PATH);
  await waitForHomeserver(cfg.homeserverUrl);

  console.log("\nCreate your (human) admin account:");
  const username = String(options.adminUsername ?? await ask("Admin username", "admin"));
  const password = String(options.adminPassword ?? await ask("Admin password (stored only in secrets/)"));
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
  await configureDashboardObserver(cfg, creds.access_token);
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

async function configureDashboardObserver(cfg, adminToken) {
  const env = readEnvFile(ENV_PATH);
  const observerPath = path.join(SECRETS, "dashboard.env");
  let observer = readEnvFile(observerPath);

  if (!observer.MATRIX_ACCESS_TOKEN && cfg.mode === "local") {
    try {
      const password = randomBytes(32).toString("base64url");
      const creds = await registerUser(cfg.homeserverUrl, "hearth-dashboard", password,
        env.HEARTH_REGISTRATION_TOKEN);
      await joinStandardRooms(cfg, adminToken, creds);
      observer = {
        MATRIX_HOMESERVER_URL: cfg.homeserverUrl,
        MATRIX_USER_ID: creds.user_id,
        MATRIX_ACCESS_TOKEN: creds.access_token,
      };
      writeEnvFile(observerPath, observer);
      ok(`Created dedicated dashboard observer ${creds.user_id}`);
    } catch (err) {
      console.log(`⚠ Could not create a dedicated dashboard observer (${err.message}); using the admin Matrix token.`);
    }
  }

  const observerToken = observer.MATRIX_ACCESS_TOKEN || adminToken;
  if (!observerToken) die("dashboard observer requires an admin Matrix token");
  const updatedEnv = { ...env, HEARTH_MATRIX_TOKEN: observerToken };
  writeEnvFile(ENV_PATH, updatedEnv);
  compose(...composeFileArgs(updatedEnv), "up", "-d", "--force-recreate", "memory");
  ok("Dashboard Matrix activity observer configured");
}

async function cmdDashboardConfigure() {
  const cfg = loadConfig();
  const adminEnv = readEnvFile(path.join(SECRETS, "admin.env"));
  if (!adminEnv.MATRIX_ACCESS_TOKEN) die("No admin credentials — run `hearth setup` first.");
  await configureDashboardObserver(cfg, adminEnv.MATRIX_ACCESS_TOKEN);
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

function mcpSnippets(cfg, name, wrapperPath, memoryUrl, memoryToken) {
  const mcpUrl = `${memoryUrl}/mcp`;
  const w = wrapperPath.replaceAll("\\", "\\\\");
  const memClaude = memoryToken
    ? `claude mcp add-json hearth-memory '${`{ "type": "http", "url": "${mcpUrl}", "headers": { "Authorization": "Bearer \${HEARTH_MEMORY_TOKEN}" } }`}'`
    : `claude mcp add --transport http hearth-memory ${mcpUrl}`;
  const memJson = memoryToken
    ? `{ "type": "http", "url": "${mcpUrl}", "headers": { "Authorization": "Bearer \${HEARTH_MEMORY_TOKEN}" } }`
    : `{ "type": "http", "url": "${mcpUrl}" }`;
  const memCodex = memoryToken
    ? `
[mcp_servers.hearth-memory]
url = "${mcpUrl}"
bearer_token_env_var = "HEARTH_MEMORY_TOKEN"`
    : `
[mcp_servers.hearth-memory]
url = "${mcpUrl}"`;
  return `
── Connect this agent ─────────────────────────────────────────────

▸ Claude Code:
  claude mcp add hearth-matrix -- node "${wrapperPath}"
  ${memClaude}

▸ Codex (~/.codex/config.toml):
  [mcp_servers.hearth-matrix]
  command = "node"
  args = ["${w}"]
  ${memCodex.trimStart()}

▸ Generic MCP (.mcp.json style):
  { "mcpServers": {
      "hearth-matrix": { "command": "node", "args": ["${w}"] },
      "hearth-memory": ${memJson} } }

Bootstrap: add to the agent's instructions — "Read and follow docs/AGENT-SPEC.md
in the hearth repo; bootstrap per its checklist." It self-configures from there.

Credentials: ${path.join(SECRETS, "agents", `${name}.env`)}  (gitignored; treat like a password)
${memoryToken
    ? `Memory access is token-authenticated. Set HEARTH_MEMORY_TOKEN in the client process
from that credentials file before starting Claude Code or Codex. The snippets reference
the environment variable and do not print or store the live token.`
    : `No memory token issued — the agent gets Matrix only until the memory service is reachable.`}
───────────────────────────────────────────────────────────────────`;
}

async function cmdAgentAdd(name, flags) {
  if (!name || !AGENT_NAME_RE.test(name)) die("usage: hearth agent add <name>  (lowercase, no spaces)");
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

  // Mint a memory token so this agent can use the shared memory service.
  const memoryUrl = (env.HEARTH_MEMORY_URL || `http://localhost:${cfg.ports?.memory ?? 8010}`).replace(/\/$/, "");
  let memoryToken = null;
  if (env.HEARTH_MEMORY_ADMIN_TOKEN) {
    try {
      const res = await fetch(`${memoryUrl}/api/tokens`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${env.HEARTH_MEMORY_ADMIN_TOKEN}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ agent: name }),
      });
      if (res.ok) {
        memoryToken = (await res.json()).token;
        ok(`memory token minted for ${name}`);
      } else {
        console.log(`⚠ memory token mint failed (HTTP ${res.status}) — is the stack up-to-date and running?`);
      }
    } catch {
      console.log(`⚠ memory service unreachable at ${memoryUrl} — agent gets Matrix only (re-run later or use an SSH tunnel)`);
    }
  }

  const agentEnvPath = path.join(SECRETS, "agents", `${name}.env`);
  writeEnvFile(agentEnvPath, {
    MATRIX_HOMESERVER_URL: cfg.homeserverUrl,
    MATRIX_USER_ID: creds.user_id,
    MATRIX_ACCESS_TOKEN: creds.access_token,
    ...(memoryToken ? { HEARTH_MEMORY_URL: memoryUrl, HEARTH_MEMORY_TOKEN: memoryToken } : {}),
  });
  const wrapperPath = writeAgentWrapper(name);
  ensureMatrixDeps();
  if (!cfg.agents.some((a) => a.name === name)) {
    cfg.agents.push({ name, userId: creds.user_id });
    saveConfig(cfg);
  }
  console.log(mcpSnippets(cfg, name, wrapperPath, memoryUrl, memoryToken));
}

async function cmdUserAdd(name) {
  if (!name || !AGENT_NAME_RE.test(name)) die("usage: hearth user add <name>  (lowercase, no spaces)");
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

// Move an existing agent identity to another machine: export prints a code
// containing the agent's credentials; import (inside a hearth checkout on the
// other machine) recreates the env file + wrapper and prints MCP config.
async function cmdAgentExport(name) {
  const envPath = path.join(SECRETS, "agents", `${name}.env`);
  const vars = readEnvFile(envPath);
  if (!vars.MATRIX_ACCESS_TOKEN) die(`no credentials at ${envPath}`);
  const code = "HEARTHAGENT1." + Buffer.from(JSON.stringify({ v: 1, name, vars })).toString("base64url");
  console.log(`Agent transfer code for '${name}' — CONTAINS LIVE CREDENTIALS, transfer securely:\n`);
  console.log(code);
  console.log(`\nOn the other machine, inside a hearth checkout:\n  node cli/hearth.mjs agent import <code>`);
}

async function cmdAgentImport(code) {
  if (!code?.startsWith("HEARTHAGENT1.")) die("usage: hearth agent import HEARTHAGENT1.…");
  let p;
  try {
    p = JSON.parse(Buffer.from(code.slice(13), "base64url").toString());
  } catch {
    die("could not decode agent code (truncated?)");
  }
  if (p?.v !== 1 || typeof p.name !== "string" || !AGENT_NAME_RE.test(p.name) ||
      !isSafeEnvMap(p.vars) || !isHttpUrl(p.vars.MATRIX_HOMESERVER_URL) ||
      !p.vars.MATRIX_USER_ID?.startsWith("@") || !p.vars.MATRIX_ACCESS_TOKEN) {
    die("invalid agent transfer code");
  }
  const envPath = path.join(SECRETS, "agents", `${p.name}.env`);
  writeEnvFile(envPath, p.vars);
  const wrapperPath = writeAgentWrapper(p.name);
  ensureMatrixDeps();
  // No hub config on this machine is fine — the wrapper is self-contained.
  if (fs.existsSync(CONFIG_PATH)) {
    const cfg = loadConfig();
    cfg.agents ??= [];
    if (!cfg.agents.some((a) => a.name === p.name)) {
      cfg.agents.push({ name: p.name, userId: p.vars.MATRIX_USER_ID });
      saveConfig(cfg);
    }
  }
  ok(`Imported ${p.vars.MATRIX_USER_ID}`);
  console.log(mcpSnippets({ ports: {} }, p.name, wrapperPath,
    (p.vars.HEARTH_MEMORY_URL || "http://localhost:8010").replace(/\/$/, ""),
    p.vars.HEARTH_MEMORY_TOKEN || null));
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
      memoryUrl: env.HEARTH_MEMORY_URL || "",
      memoryAdminToken: env.HEARTH_MEMORY_ADMIN_TOKEN || "",
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
    if (p?.v !== 1 || typeof p.serverName !== "string" || !p.serverName ||
        !isHttpUrl(p.homeserverUrl) || !isSafeEnvMap(p.admin) ||
        !p.admin.MATRIX_ACCESS_TOKEN || typeof p.registrationToken !== "string" ||
        /[\r\n]/.test(p.registrationToken) ||
        (p.memoryUrl && !isHttpUrl(p.memoryUrl)) ||
        (p.memoryAdminToken && (typeof p.memoryAdminToken !== "string" || /[\r\n]/.test(p.memoryAdminToken)))) {
      die("invalid hub link code");
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
      ...(p.memoryUrl ? { HEARTH_MEMORY_URL: p.memoryUrl } : {}),
      ...(p.memoryAdminToken ? { HEARTH_MEMORY_ADMIN_TOKEN: p.memoryAdminToken } : {}),
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
  const env = readEnvFile(ENV_PATH);
  const memoryUrl = (env.HEARTH_MEMORY_URL ||
    `http://localhost:${cfg.ports?.memory ?? 8010}`).replace(/\/$/, "");
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
  if (cmd === "install") await cmdInstall([sub, ...rest].filter(Boolean));
  else if (cmd === "doctor") await cmdDoctor([sub, ...rest].filter(Boolean));
  else if (cmd === "init") await cmdInit();
  else if (cmd === "up") await cmdUp();
  else if (cmd === "down") await cmdDown();
  else if (cmd === "setup") await cmdSetup();
  else if (cmd === "agent" && sub === "add") await cmdAgentAdd(rest[0], rest.slice(1));
  else if (cmd === "agent" && sub === "export") await cmdAgentExport(rest[0]);
  else if (cmd === "agent" && sub === "import") await cmdAgentImport(rest[0]);
  else if (cmd === "user" && sub === "add") await cmdUserAdd(rest[0]);
  else if (cmd === "dashboard" && sub === "configure") await cmdDashboardConfigure();
  else if (cmd === "link") await cmdLink(sub);
  else if (cmd === "notify") await cmdNotify(sub, rest);
  else if (cmd === "status") await cmdStatus();
  else {
    console.log(`Hearth — human–agent collaboration hub

  hearth install [--yes]      check prerequisites, configure, start, and set up
    [--config <file>]         use a deployment JSON file for unattended rollout
  hearth doctor [--json]     verify Node, Docker, Compose, and local files
  hearth init                 configure the hub (wizard)
  hearth up | down            start/stop the Docker stack
  hearth setup                create admin user + standard rooms
  hearth agent add <name>     onboard an agent (add --existing for a pre-made user)
  hearth agent export <name>  print a transfer code to move this agent to another machine
  hearth agent import <code>  recreate an exported agent here (env + wrapper + MCP config)
  hearth user add <name>      onboard a human teammate (Element login card)
  hearth dashboard configure configure/recover the dashboard Matrix observer
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
