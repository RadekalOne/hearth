import assert from "node:assert/strict";
import { execFile, execFileSync, spawnSync } from "node:child_process";
import { promisify } from "node:util";
import fs from "node:fs";
import http from "node:http";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const REPO = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

function fixture() {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "hearth-cli-test-"));
  fs.mkdirSync(path.join(root, "cli"), { recursive: true });
  fs.mkdirSync(path.join(root, "mcp", "matrix", "node_modules"), { recursive: true });
  fs.copyFileSync(path.join(REPO, "cli", "hearth.mjs"), path.join(root, "cli", "hearth.mjs"));
  fs.copyFileSync(path.join(REPO, "cli", "create-hearth.mjs"), path.join(root, "cli", "create-hearth.mjs"));
  return root;
}

function fixtureEnv(root) {
  return { ...process.env, HEARTH_ROOT: root };
}

function transferCode(payload) {
  return "HEARTHAGENT1." + Buffer.from(JSON.stringify(payload)).toString("base64url");
}

test("agent import rejects path traversal and option-like names", () => {
  for (const name of ["../../../escaped", "--help"]) {
    const root = fixture();
    const result = spawnSync(process.execPath, [path.join(root, "cli", "hearth.mjs"), "agent", "import",
      transferCode({
        v: 1,
        name,
        vars: {
          MATRIX_HOMESERVER_URL: "https://matrix.example.test",
          MATRIX_USER_ID: "@codex:example.test",
          MATRIX_ACCESS_TOKEN: "secret",
        },
      })], { encoding: "utf8", env: fixtureEnv(root) });

    assert.equal(result.status, 1);
    assert.match(result.stderr, /invalid agent transfer code/);
    assert.equal(fs.existsSync(path.join(root, "escaped.env")), false);
  }
});

test("agent import prints token-free Memory config for Claude and Codex", () => {
  const root = fixture();
  const token = "live-memory-token-must-not-print";
  const output = execFileSync(process.execPath, [path.join(root, "cli", "hearth.mjs"), "agent", "import",
    transferCode({
      v: 1,
      name: "codex",
      vars: {
        MATRIX_HOMESERVER_URL: "https://matrix.example.test",
        MATRIX_USER_ID: "@codex:example.test",
        MATRIX_ACCESS_TOKEN: "matrix-token",
        HEARTH_MEMORY_URL: "https://memory.example.test",
        HEARTH_MEMORY_TOKEN: token,
      },
    })], { encoding: "utf8", env: fixtureEnv(root) });

  assert.match(output, /\[mcp_servers\.hearth-memory\]/);
  assert.match(output, /bearer_token_env_var = "HEARTH_MEMORY_TOKEN"/);
  assert.match(output, /Bearer \$\{HEARTH_MEMORY_TOKEN\}/);
  assert.doesNotMatch(output, new RegExp(token));
  assert.match(fs.readFileSync(path.join(root, "secrets", "agents", "codex.env"), "utf8"), new RegExp(token));
});

// Regression: `agent add` used to write the env file from a fresh object, so any run
// where the memory-token mint failed silently dropped HEARTH_MEMORY_* from an existing
// agent — Matrix kept working, memory died, exit code 0. Those tokens live in the memory
// service's own store and survive a homeserver rebuild, so the old value stays valid.
test("agent add keeps existing memory credentials when the mint fails", async () => {
  const root = fixture();
  const keptToken = "pre-existing-memory-token";

  // One listener plays both roles: the homeserver registers fine, the memory service
  // rejects the mint. A dead port would work too but does not refuse promptly on
  // Windows, which hangs the run instead of failing it.
  const homeserver = http.createServer((req, res) => {
    req.resume();
    res.setHeader("Content-Type", "application/json");
    // Reject the existing token, so the CLI decides it must mint...
    if (req.url === "/api/status") {
      res.statusCode = 401;
      res.end(JSON.stringify({ error: "invalid token" }));
      return;
    }
    // ...and then the mint itself fails. That combination is what used to wipe the file.
    if (req.url === "/api/tokens") {
      res.statusCode = 503;
      res.end(JSON.stringify({ error: "memory service down" }));
      return;
    }
    if (req.url === "/_matrix/client/v3/register") {
      res.end(JSON.stringify({ user_id: "@codex:example.test", access_token: "freshly-minted-matrix-token" }));
      return;
    }
    res.end("{}");
  });
  await new Promise((resolve) => homeserver.listen(0, "127.0.0.1", resolve));
  const homeserverUrl = `http://127.0.0.1:${homeserver.address().port}`;

  try {
    fs.writeFileSync(path.join(root, "hearth.config.json"), JSON.stringify({
      mode: "local", homeserverUrl, ports: { memory: "8010" },
      agents: [{ name: "codex", userId: "@codex:example.test" }], users: [], rooms: {},
    }));
    // Admin token present, memory pointed at a dead port so the mint hits the catch.
    fs.writeFileSync(path.join(root, ".env"),
      `HEARTH_REGISTRATION_TOKEN=tok\nHEARTH_MEMORY_ADMIN_TOKEN=admin\nHEARTH_MEMORY_URL=${homeserverUrl}\n`);
    fs.mkdirSync(path.join(root, "secrets", "agents"), { recursive: true });
    fs.writeFileSync(path.join(root, "secrets", "admin.env"), "MATRIX_ACCESS_TOKEN=admin-matrix-token\n");
    fs.writeFileSync(path.join(root, "secrets", "agents", "codex.env"),
      `MATRIX_HOMESERVER_URL=${homeserverUrl}\nMATRIX_USER_ID=@codex:example.test\n` +
      `MATRIX_ACCESS_TOKEN=stale-matrix-token\nHEARTH_MEMORY_URL=https://memory.example.test\n` +
      `HEARTH_MEMORY_TOKEN=${keptToken}\n`);

    // Async, not execFileSync: the stub server lives in this process, and a synchronous
    // child would block the event loop so the server could never answer it.
    await promisify(execFile)(process.execPath,
      [path.join(root, "cli", "hearth.mjs"), "agent", "add", "codex"],
      { encoding: "utf8", env: fixtureEnv(root) });

    const env = fs.readFileSync(path.join(root, "secrets", "agents", "codex.env"), "utf8");
    assert.match(env, new RegExp(`HEARTH_MEMORY_TOKEN=${keptToken}`),
      "memory token must survive a failed mint");
    assert.match(env, /HEARTH_MEMORY_URL=https:\/\/memory\.example\.test/);
    assert.match(env, /MATRIX_ACCESS_TOKEN=freshly-minted-matrix-token/,
      "the Matrix token should still be rotated");
  } finally {
    await new Promise((resolve) => homeserver.close(resolve));
  }
});

// Regression: re-adding an agent used to mint a new memory token unconditionally. The
// memory MCP holds its bearer token in the *client's* config, which this CLI never
// writes, so rotating silently broke memory access with no way for the client to learn
// about it. A still-valid token must be left alone.
test("agent add reuses a still-valid memory token instead of rotating it", async () => {
  const root = fixture();
  const keptToken = "already-valid-memory-token";
  let mintCalls = 0;

  const server = http.createServer((req, res) => {
    req.resume();
    res.setHeader("Content-Type", "application/json");
    if (req.url === "/api/status") {
      const ok = (req.headers.authorization || "") === `Bearer ${keptToken}`;
      res.statusCode = ok ? 200 : 401;
      res.end("{}");
      return;
    }
    if (req.url === "/api/tokens") { mintCalls++; res.end(JSON.stringify({ token: "freshly-minted" })); return; }
    if (req.url === "/_matrix/client/v3/register") {
      res.end(JSON.stringify({ user_id: "@codex:example.test", access_token: "new-matrix-token" }));
      return;
    }
    res.end("{}");
  });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  const url = `http://127.0.0.1:${server.address().port}`;

  try {
    fs.writeFileSync(path.join(root, "hearth.config.json"), JSON.stringify({
      mode: "local", homeserverUrl: url, ports: { memory: "8010" },
      agents: [{ name: "codex", userId: "@codex:example.test" }], users: [], rooms: {},
    }));
    fs.writeFileSync(path.join(root, ".env"),
      `HEARTH_REGISTRATION_TOKEN=tok\nHEARTH_MEMORY_ADMIN_TOKEN=admin\nHEARTH_MEMORY_URL=${url}\n`);
    fs.mkdirSync(path.join(root, "secrets", "agents"), { recursive: true });
    fs.writeFileSync(path.join(root, "secrets", "admin.env"), "MATRIX_ACCESS_TOKEN=admin-matrix-token\n");
    fs.writeFileSync(path.join(root, "secrets", "agents", "codex.env"),
      `MATRIX_HOMESERVER_URL=${url}\nMATRIX_USER_ID=@codex:example.test\n` +
      `MATRIX_ACCESS_TOKEN=stale\nHEARTH_MEMORY_URL=${url}\nHEARTH_MEMORY_TOKEN=${keptToken}\n`);

    await promisify(execFile)(process.execPath,
      [path.join(root, "cli", "hearth.mjs"), "agent", "add", "codex"],
      { encoding: "utf8", env: fixtureEnv(root) });

    const env = fs.readFileSync(path.join(root, "secrets", "agents", "codex.env"), "utf8");
    assert.equal(mintCalls, 0, "a valid memory token must not be rotated");
    assert.match(env, new RegExp(`HEARTH_MEMORY_TOKEN=${keptToken}`));
    assert.match(env, /MATRIX_ACCESS_TOKEN=new-matrix-token/, "the Matrix token should still rotate");

    // ...but --rotate-memory-token is an explicit opt-in.
    await promisify(execFile)(process.execPath,
      [path.join(root, "cli", "hearth.mjs"), "agent", "add", "codex", "--rotate-memory-token"],
      { encoding: "utf8", env: fixtureEnv(root) });
    assert.equal(mintCalls, 1, "explicit rotation must still mint");
    assert.match(fs.readFileSync(path.join(root, "secrets", "agents", "codex.env"), "utf8"),
      /HEARTH_MEMORY_TOKEN=freshly-minted/);
  } finally {
    await new Promise((resolve) => server.close(resolve));
  }
});

test("status checks the configured remote Memory URL", () => {
  const root = fixture();
  fs.writeFileSync(path.join(root, "hearth.config.json"), JSON.stringify({
    homeserverUrl: "http://127.0.0.1:9",
    ports: { memory: "8010" },
    agents: [], users: [], rooms: {},
  }));
  fs.writeFileSync(path.join(root, ".env"), "HEARTH_MEMORY_URL=http://127.0.0.1:8\n");

  const output = execFileSync(process.execPath,
    [path.join(root, "cli", "hearth.mjs"), "status"], { encoding: "utf8", env: fixtureEnv(root) });
  assert.match(output, /memory service unreachable \(http:\/\/127\.0\.0\.1:8\)/);
});

test("create-hearth exposes the one-command installer help", () => {
  const output = execFileSync(process.execPath,
    [path.join(REPO, "cli", "create-hearth.mjs"), "--help"], { encoding: "utf8" });
  assert.match(output, /create-hearth \[--directory hearth\] \[--yes\]/);
  assert.match(output, /--directory/);
});

test("doctor emits machine-readable prerequisite results", () => {
  const root = fixture();
  fs.writeFileSync(path.join(root, "docker-compose.yml"), "services: {}\n");
  const result = spawnSync(process.execPath,
    [path.join(root, "cli", "hearth.mjs"), "doctor", "--json"], {
      encoding: "utf8", env: fixtureEnv(root),
    });
  assert.ok([0, 1].includes(result.status));
  const report = JSON.parse(result.stdout);
  assert.equal(typeof report.passed, "boolean");
  assert.ok(report.checks.some((check) => check.name === "Node.js 20+"));
  assert.ok(report.checks.some((check) => check.name === "Docker Compose"));
});

test("noninteractive install validates deployment config before starting Docker", () => {
  const root = fixture();
  const config = path.join(root, "deployment.json");
  fs.writeFileSync(config, JSON.stringify({ mode: "local", ports: { memory: 70000 } }));
  const result = spawnSync(process.execPath,
    [path.join(root, "cli", "hearth.mjs"), "install", "--yes", "--skip-doctor", "--config", config], {
      encoding: "utf8", env: fixtureEnv(root),
    });
  assert.equal(result.status, 1);
  assert.match(result.stderr, /invalid deployment port memory=70000/);
});

test("noninteractive install rejects malformed public deployment hosts before Docker", () => {
  const root = fixture();
  const config = path.join(root, "deployment.json");
  fs.writeFileSync(config, JSON.stringify({
    mode: "local",
    public: {
      elementHost: "https://hearth.example.test",
      matrixHost: "hearth-matrix.example.test",
    },
  }));
  const result = spawnSync(process.execPath,
    [path.join(root, "cli", "hearth.mjs"), "install", "--yes", "--skip-doctor", "--config", config], {
      encoding: "utf8", env: fixtureEnv(root),
    });
  assert.equal(result.status, 1);
  assert.match(result.stderr, /public\.elementHost must be a hostname/);
  assert.doesNotMatch(result.stderr, /Docker not found/);
});

test("public deployment config writes proxy hosts and public service URLs", () => {
  const root = fixture();
  fs.mkdirSync(path.join(root, "config"), { recursive: true });
  fs.copyFileSync(path.join(REPO, "config", "element-config.json"),
    path.join(root, "config", "element-config.json"));
  const config = path.join(root, "deployment.json");
  fs.writeFileSync(config, JSON.stringify({
    mode: "local",
    serverName: "hearth.example.test",
    public: {
      elementHost: "hearth.example.test",
      matrixHost: "hearth-matrix.example.test",
      memoryHost: "hearth-memory.example.test",
      certResolver: "letsencrypt",
      proxyNetwork: "hearth-proxy",
    },
  }));
  spawnSync(process.execPath,
    [path.join(root, "cli", "hearth.mjs"), "install", "--yes", "--skip-doctor", "--config", config], {
      encoding: "utf8", env: { ...fixtureEnv(root), HEARTH_ADMIN_PASSWORD: "test-only-password" },
    });

  const env = fs.readFileSync(path.join(root, ".env"), "utf8");
  assert.match(env, /HEARTH_EXPOSE=1/);
  assert.match(env, /HEARTH_PUBLIC_MATRIX_HOST=hearth-matrix\.example\.test/);
  assert.match(env, /HEARTH_MEMORY_URL=https:\/\/hearth-memory\.example\.test/);
  assert.match(env, /HEARTH_PROXY_NETWORK=hearth-proxy/);
  const element = JSON.parse(fs.readFileSync(path.join(root, "config", "element-config.json"), "utf8"));
  assert.equal(element.default_server_config["m.homeserver"].base_url,
    "https://hearth-matrix.example.test");
});

test("help includes dashboard observer recovery", () => {
  const root = fixture();
  const output = execFileSync(process.execPath,
    [path.join(root, "cli", "hearth.mjs")], { encoding: "utf8", env: fixtureEnv(root) });
  assert.match(output, /hearth dashboard configure/);
});

test("create-hearth scaffolds a durable directory and preserves deployment config", () => {
  const parent = fs.mkdtempSync(path.join(os.tmpdir(), "create-hearth-test-"));
  const target = path.join(parent, "hub");
  const deployment = path.join(parent, "invalid.json");
  fs.writeFileSync(deployment, JSON.stringify({ mode: "local", ports: { memory: 70000 } }));
  const args = [path.join(REPO, "cli", "create-hearth.mjs"), "--directory", target,
    "--yes", "--skip-doctor", "--config", deployment];

  const first = spawnSync(process.execPath, args, { encoding: "utf8" });
  assert.equal(first.status, 1);
  assert.equal(fs.existsSync(path.join(target, "docker-compose.yml")), true);
  assert.equal(fs.existsSync(path.join(target, "cli", "hearth.mjs")), true);
  assert.match(fs.readFileSync(path.join(target, ".gitignore"), "utf8"), /secrets\//);

  const elementConfig = path.join(target, "config", "element-config.json");
  fs.writeFileSync(elementConfig, "preserve-me\n");
  const second = spawnSync(process.execPath, args, { encoding: "utf8" });
  assert.equal(second.status, 1);
  assert.equal(fs.readFileSync(elementConfig, "utf8"), "preserve-me\n");
});

test("create-hearth scaffolds when npm installs it below node_modules", () => {
  const parent = fs.mkdtempSync(path.join(os.tmpdir(), "create-hearth-npm-test-"));
  const packageRoot = path.join(parent, "node_modules", "create-hearth");
  for (const item of [
    ".env.example", "cli", "config", "docs", "mcp", "docker-compose.yml",
    "docker-compose.expose.yml", "docker-compose.expose-memory.yml", "LICENSE",
    "PROJECT.md", "README.md",
  ]) {
    fs.cpSync(path.join(REPO, item), path.join(packageRoot, item), {
      recursive: true,
      filter: (source) => !path.relative(REPO, source).split(path.sep).some((part) =>
        ["node_modules", "data", "secrets", "__pycache__"].includes(part)),
    });
  }
  const target = path.join(parent, "hub");
  const result = spawnSync(process.execPath,
    [path.join(packageRoot, "cli", "create-hearth.mjs"), "--directory", target,
      "--yes", "--skip-doctor", "--config", "missing.json"], {
      cwd: parent, encoding: "utf8",
    });

  assert.equal(result.status, 1);
  assert.match(result.stderr, /could not read deployment config/);
  assert.equal(fs.existsSync(path.join(target, "cli", "hearth.mjs")), true);
  assert.equal(fs.existsSync(path.join(target, "docker-compose.yml")), true);
  assert.equal(fs.existsSync(path.join(target, "docs", "HOSTINGER.md")), true);
  assert.equal(fs.existsSync(path.join(target, "docs", "USAGE.md")), true);
});
