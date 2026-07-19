import assert from "node:assert/strict";
import { execFileSync, spawnSync } from "node:child_process";
import fs from "node:fs";
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
});
