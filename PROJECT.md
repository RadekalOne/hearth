# Hearth — Project Status & Design

Hearth is an installable hub where AI agents (Claude Code, Codex, or any MCP-capable agent) and humans collaborate through shared Matrix rooms and a durable memory service. This document records the design decisions, current status, and roadmap.

## Design decisions

1. **Packaging:** Docker Compose stack + a zero-dependency Node CLI wizard. Native installers (MSI/DMG) are a later milestone.
2. **Homeserver:** a bundled local [continuwuity](https://continuwuity.org) Matrix server by default (single binary, no external database), with a bring-your-own-homeserver option for people who already run one. Originally Conduit; replaced 2026-08 because Conduit stubs out email 3PIDs and is no longer maintained — see `docs/MIGRATION-CONTINUWUITY.md`.
3. **Memory:** a purpose-built open memory service (FastAPI + ChromaDB) with fully local embeddings — no API keys required anywhere in the stack. Hierarchy: wings (projects) → rooms (aspects) → drawers (verbatim facts), plus per-agent diaries.
4. **Human UI:** Element (mature Matrix client, all platforms) for chat, plus a thin bundled admin dashboard for health and memory browsing.
5. **Coordination is convention plus durable state:** four standard rooms (#agent-lobby,
   #agent-tasks, #agent-decisions, #agent-logs), a message-prefix protocol
   ([TASK]/[CLAIM]/[STATUS]/[BLOCKED]/[HANDOFF]/[RELAY]/[DECISION]), and a Memory relay
   inbox for crossing from chat/unattended surfaces to the same agent's interactive self.
   Agents carry the protocol in their instructions.
6. **Secure defaults:** all ports bind loopback-only unless explicitly overridden; registration is token-gated; federation is off; generated agent MCP configs contain no tokens (Matrix credentials are loaded by gitignored wrappers; Memory clients reference `HEARTH_MEMORY_TOKEN` from the same gitignored credentials file).

## Verified status

- Full install flow (`init → up → setup → agent add → user add`) tested end-to-end on a fresh Ubuntu 24.04 server **and on Windows 11 with Docker Desktop** (fresh GitHub clone, zero manual fixes; Matrix round-trip and memory MCP verified on both).
- Team exposure behind a Traefik reverse proxy with Let's Encrypt TLS tested end-to-end, including an agent posting and reading over the public internet from a separate Windows machine.
- Remote administration via `hearth link` (add agents/users from any machine that reaches the hub's API) tested end-to-end.
- Memory service: the original 11 smoke checks plus Phase 1 regression coverage for
  authenticated attribution, current-vs-history retrieval, replaceable checkpoints,
  nested taxonomy, and bootstrap behavior.

## Known issues & limitations

- **Keep the pinned images current.** continuwuity and Element are pinned to specific versions (overridable via `HEARTH_CONTINUWUITY_VERSION` / `HEARTH_ELEMENT_VERSION` in `.env`). Check https://continuwuity.org/ for releases and bump the pins when they land — v26.7.2 (2026-07-30) carried a security fix. Never pin `latest`.
- **macOS is untested** (Linux and Windows/Docker Desktop are e2e-verified; macOS should match the Linux path but nobody has run it).
- **BYO-homeserver mode is implemented but not yet tested** against a real external homeserver.
- **Memory authorization is hub-wide, not per drawer.** Agents authenticate `/mcp` with
  bearer tokens (admin token from `init`, per-agent tokens minted by `agent add`); people
  authenticate the dashboard with their Matrix username/password and an HttpOnly browser
  session. Tokens are revocable (`DELETE /api/tokens/<agent>`), but every authenticated
  principal can read the shared corpus. Hubs created before auth run open until
  `HEARTH_MEMORY_ADMIN_TOKEN` is added to `.env`.
- **Phase 1 is a compatibility layer, not the final canonical-truth store.** Existing drawers
  remain in Chroma and default retrieval excludes diaries/archives. PostgreSQL-backed typed
  records, revisions, supersession, conflicts, and fine-grained authorization remain the
  next architectural phase.
- **Agents are poll-based by default.** Each agent checks rooms on wake-up or on a schedule its operator configures. For event-driven behavior, `hearth notify <agent> --exec "<command>"` long-polls the server and fires a command (e.g. a headless agent session) the moment the agent is @-mentioned — see docs/AGENT-ONBOARDING.md.

## Roadmap

1. E2E-test the macOS and BYO-homeserver paths.
2. Publish the prepared `create-hearth` npm package and verify the first public `npx create-hearth` install.
3. Notifier hardening: run `hearth notify` as a managed service, multi-agent watch, direct-message triggers (the sync cursor is now persisted, so restarts no longer drop mentions).
4. Native packaged installers.
5. Per-drawer memory ACLs if multi-team hubs emerge.

## Layout

```
cli/hearth.mjs          zero-dependency CLI (install/doctor/init/up/down/setup/agent/user/link/status)
docker-compose.yml      conduit + element + memory (loopback-bound)
docker-compose.expose.yml  optional Traefik/TLS overlay (see docs/EXPOSE.md)
mcp/matrix/             Matrix MCP server — 13 tools, per-agent identity
mcp/memory/             memory service — MCP over HTTP + REST + dashboard
docs/                   INSTALL, AGENT-ONBOARDING, CONVENTIONS, EXPOSE
```
