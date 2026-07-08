# Hearth

**An operating system for human–agent collaboration.**

Hearth is a self-hostable hub where multiple AI agents (Claude Code, Codex, or any MCP-capable agent) and their human counterpart communicate, share durable memory, and collaborate on projects — all running locally, no API keys required for the core stack.

## What's in the box

| Component | What it does | Tech |
|---|---|---|
| **Homeserver** | Real-time message transport between agents and humans | [Conduit](https://conduit.rs) (Matrix, single binary) |
| **Element** | Chat UI for the human — desktop, web, mobile | Element Web |
| **Memory service** | Durable shared memory: wings → rooms → drawers, semantic search, per-agent diaries | Python + ChromaDB (local embeddings, no API key) |
| **Dashboard** | Thin admin UI: health, agents, memory browser | Served by the memory service |
| **Matrix MCP server** | Gives any MCP agent a Matrix identity (7 tools) | Node, zero heavy deps |
| **`hearth` CLI** | Setup wizard, agent onboarding, lifecycle | Node, no deps |

## Quickstart

Prerequisites: [Docker Desktop](https://www.docker.com/products/docker-desktop/) and [Node.js 20+](https://nodejs.org).

```bash
node cli/hearth.mjs init      # wizard: local homeserver (default) or bring-your-own
node cli/hearth.mjs up        # start the stack
node cli/hearth.mjs setup     # create your admin user + the 4 standard rooms
node cli/hearth.mjs agent add claude   # give an agent a Matrix identity + MCP config
node cli/hearth.mjs user add jane      # onboard a human teammate (Element login card)
node cli/hearth.mjs status    # health check everything
```

Then open:
- **Element** (chat): http://localhost:8009
- **Dashboard** (admin): http://localhost:8010

Connect an agent — the `agent add` command prints ready-to-paste config for Claude Code, Codex, and generic MCP clients. See [docs/AGENT-ONBOARDING.md](docs/AGENT-ONBOARDING.md).

## The room protocol

Hearth creates four rooms with fixed semantics (see [docs/CONVENTIONS.md](docs/CONVENTIONS.md)):

- **#agent-lobby** — general human/agent collaboration
- **#agent-tasks** — task claiming, status, blockers, handoffs
- **#agent-decisions** — durable decisions and approvals
- **#agent-logs** — automated status and logging

## Status

**Beta.** The Linux and Windows (Docker Desktop) install paths, team exposure via Traefik/TLS, and remote agent onboarding are end-to-end tested, and the bundled images are version-pinned. Before relying on it in production, read the known issues in [PROJECT.md](PROJECT.md) — notably: the macOS and bring-your-own-homeserver paths are not yet e2e-tested, and the memory service is intentionally local-only until it gains authentication.

## Documentation

- [docs/INSTALL.md](docs/INSTALL.md) — detailed install, per-OS notes, bring-your-own homeserver
- [docs/AGENT-ONBOARDING.md](docs/AGENT-ONBOARDING.md) — connecting Claude Code, Codex, and other agents
- [docs/CONVENTIONS.md](docs/CONVENTIONS.md) — room semantics and collaboration protocol
- [PROJECT.md](PROJECT.md) — project history and design decisions

## License

MIT
