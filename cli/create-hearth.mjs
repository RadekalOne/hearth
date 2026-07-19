#!/usr/bin/env node

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const args = process.argv.slice(2);
const help = args.includes("--help") || args.includes("-h");
const directoryIndex = args.findIndex((arg) => arg === "--directory" || arg.startsWith("--directory="));
let directory = "hearth";
if (directoryIndex >= 0) {
  const flag = args[directoryIndex];
  directory = flag.includes("=") ? flag.slice(flag.indexOf("=") + 1) : args[directoryIndex + 1];
  if (!directory) {
    console.error("error: --directory requires a path");
    process.exit(1);
  }
  args.splice(directoryIndex, flag.includes("=") ? 1 : 2);
}

if (!help) {
  const packageRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
  const target = path.resolve(process.cwd(), directory);
  const marker = path.join(target, "cli", "hearth.mjs");
  const existingDeployment = fs.existsSync(marker);
  if (fs.existsSync(target) && fs.readdirSync(target).length > 0 && !fs.existsSync(marker)) {
    console.error(`error: ${target} is not empty and is not an existing Hearth deployment`);
    process.exit(1);
  }
  fs.mkdirSync(target, { recursive: true });
  for (const item of [
    ".env.example", "cli", "config", "docs", "mcp", "docker-compose.yml",
    "docker-compose.expose.yml", "docker-compose.expose-memory.yml", "LICENSE",
    "PROJECT.md", "README.md",
  ]) {
    if (existingDeployment && item === "config") continue;
    fs.cpSync(path.join(packageRoot, item), path.join(target, item), {
      recursive: true,
      force: true,
      filter: (source) => !["node_modules", "data", "secrets", "__pycache__"]
        .includes(path.basename(source)),
    });
  }
  const gitignore = path.join(target, ".gitignore");
  if (!fs.existsSync(gitignore)) {
    fs.copyFileSync(path.join(packageRoot, "config", "gitignore.template"), gitignore);
  }
  process.env.HEARTH_ROOT = target;
  process.chdir(target);
  console.log(`\nHearth files ready at ${target}`);
}

process.argv = [process.execPath, fileURLToPath(new URL("./hearth.mjs", import.meta.url)), "install", ...args];
await import("./hearth.mjs");
