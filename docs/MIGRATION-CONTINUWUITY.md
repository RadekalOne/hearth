# Migration: Conduit v0.10.12 → continuwuity

**Status:** EXECUTED 2026-08-07. **Drafted:** 2026-08-06.

## What actually happened — read this before repeating any of it

Four things the plan did not anticipate. All cost real time; none were destructive.

**1. continuwuity ignores your configured registration token on a fresh database.**
On first boot with an empty DB it prints a one-time bootstrap token to the container
log and states plainly: *"The registration token you set in your configuration will not
function until you create an account using the token above."* `hearth setup` therefore
fails with `M_FORBIDDEN: Invalid registration token`. Fix: grab the printed token
(`docker compose logs conduit | sed -r "s/\x1B\[[0-9;]*[mK]//g" | grep -oP "registration token \K[A-Za-z0-9]+"`),
register the admin account with it directly, then run `hearth setup` — it falls back to
login when registration reports the user already exists, and proceeds to create rooms.

**2. The deployed compose had drifted from this repo, and overwriting it caused
regressions.** `/docker/hearth` is not a git repo, so a 2026-07-15 maintenance pass
edited it in place. Replacing the file silently reverted Element v1.12.23 → v1.12.22 and
dropped both `HEARTH_PUBLIC_MATRIX_URL` and the
`config/element-nginx.conf.template` mount — which killed `/.well-known/matrix/client`
(404), breaking native-client discovery. Both restored, and the template is now
committed here so the repo matches reality. **Diff the deployed compose against this
repo before overwriting it, every time.**

**3. `rad@radekal.me` has no mailbox.** `radekal.me` is a *secondary domain* in the
Workspace, not a domain alias — separate user namespace, and no `rad` user exists in it.
The relay accepted the message (sender domain is owned, so the "only addresses in my
domains" check passed) and then dropped it, with the bounce going to the same
nonexistent address. Result: a clean `Email sent` log line and no delivery. The real
mailbox is **`rad@radekal.one`**; `CONTINUWUITY_SMTP__SENDER` is set to it.

**3b. Verification links are built from `SERVER_NAME`, which here does not serve the
API.** continuwuity emails a link to
`https://<SERVER_NAME>/_continuwuity/3pid/email/validate?session=…&token=…` — note the
path is under `/_continuwuity/`, not `/_matrix/`. `SERVER_NAME` is `hearth.radekal.me`,
which serves Element via nginx, so every link 404'd. Setting
`well_known.client` does **not** change it; the binary concatenates `https://` with the
server name directly. Fix: `config/element-nginx.conf.template` now proxies
`/_continuwuity/` through to `conduit:6167`, so links land on the homeserver.
`/_matrix/` is deliberately *not* proxied — client discovery already works via
`.well-known` delegation, and proxying it would blur which host is the API.

`CONTINUWUITY_WELL_KNOWN__CLIENT` was still worth setting (the homeserver now serves
its own `/.well-known/matrix/client`), and it must be declared in the compose
`environment:` block — adding it only to `.env` does nothing, because Compose passes
through just the keys the service declares. That silently produced a no-op deploy where
`docker compose up -d` reported "Running" rather than recreating.

**4. hearth-matrix rejects non-ASCII bodies** with `M_BAD_JSON` — em-dashes, smart
quotes, arrows, ellipses. Sanitize to ASCII before posting. (Originally learned by
`mavis` during the campfire work; the lesson survived in the archive and applied again.)

Also confirmed during the run: `hearth agent add` really could destroy memory
credentials. Fixed in `cli/hearth.mjs` with a regression test before cutover.

## Why

1. **Email 3PIDs are impossible on Conduit.** `request_3pid_management_token_via_email_route`
   is a hardcoded 403 stub. No config option, SMTP setting, or Conduit version changes this.
   Verified live: `POST /_matrix/client/v3/account/3pid/email/requestToken` →
   `{"errcode":"M_THREEPID_DENIED","error":"M_THREEPID_DENIED: Third party identifiers are currently unsupported by this server implementation"}`
2. **famedly/Conduit is effectively unmaintained.** v0.10.12 has been current since at least
   2026-07-15 (Hostinger maintenance pass, Hearth memory `drawer_62b8d59d08744e17`).
3. **continuwuity is the maintained continuation** and implements real email 3PIDs in
   `src/api/client/account/threepid.rs` (`get_3pids`, `requestToken`, `add_3pid`, `delete_3pid`).
   MSISDN/phone remains unsupported.

## What this costs

**The database cannot be migrated.** continuwuity's own FAQ: "Conduit: No, database is now
incompatible" (conduwuit: yes). This is a fresh homeserver on a fresh volume.

What survives, what doesn't:

| Thing | Survives? | Why |
| :---- | :-------- | :--- |
| Hearth memory (all drawers, diaries) | ✅ | Separate `memory-data` volume, separate container |
| Matrix user IDs (`@claude:hearth.radekal.me` …) | ✅ | Keep `SERVER_NAME=hearth.radekal.me`, re-register same localparts |
| Agent access tokens | ❌ | Re-minted by `hearth agent add`; env files rewritten automatically |
| Room IDs (all 5) | ❌ | New rooms, new IDs — see Phase 4 |
| Room message history | ❌ | **Lost unless archived first — see Phase 1** |
| Element / Traefik / TLS / DNS | ✅ | Untouched if the compose service key stays `conduit` |
| `.well-known` discovery | ✅ | Served by the Element nginx template, unchanged |

Blast radius is small because the Matrix rooms are *transport*, not storage — durable
content already lives in hearth-memory.

## Prerequisites (resolve before starting)

- [x] **Google Workspace SMTP relay.** Configured 2026-08-06. See "SMTP via the
      Workspace relay" below. Without it continuwuity still installs fine, but the
      email feature stays dark.
- [ ] **Confirm the VPS egress IP** matches what the relay allowlists (below).
- [ ] **SSH access to the VPS.** Target is `root@vps01hst4hermes.radekal.me` (key
      `~/.ssh/hermes-key`), stack at `/docker/hearth`. `2.24.70.124` is only the DNS
      A record — use the hostname.
- [ ] Confirm the deployed compose still matches this repo's (last synced 2026-07-15).

### The live stack layers three compose files

Production is not plain `docker-compose.yml`. The deployment session brought it up as:

```
docker-compose.yml + docker-compose.expose.yml + docker-compose.expose-memory.yml
```

`hearth-memory.radekal.me` is publicly exposed with bearer-token auth, driven by
`HEARTH_PUBLIC_MEMORY_HOST` in `.env`, and Traefik runs in its own separate stack
(`traefik-traefik-1`) on the external `hearth-proxy` network. `hearth up` layers the
overlays from `.env` on its own, but confirm the running set with `docker compose ps`
before and after rather than assuming.

### SMTP via the Workspace relay

`radekal.me` is on Google Workspace, so mail goes through the SMTP relay service
rather than an account App Password. The relay authenticates on the sending host's
**IP address**, so no credential is stored on the VPS at all.

Admin console → Apps → Google Workspace → Gmail → Routing → SMTP relay service:
- Allowed senders: *Only addresses in my domains*
- Authentication: *Only accept mail from the specified IP addresses* → the VPS egress IP
- Encryption: *Require TLS encryption*

Then, in `/docker/hearth/.env`:

```
CONTINUWUITY_SMTP__CONNECTION_URI=smtps://smtp-relay.gmail.com:465
CONTINUWUITY_SMTP__SENDER=Hearth Matrix <rad@radekal.me>
```

- continuwuity passes `connection_uri` straight to lettre's
  [`AsyncSmtpTransport::from_url`](https://docs.rs/lettre/latest/lettre/transport/smtp/struct.AsyncSmtpTransport.html#method.from_url),
  so lettre's URI rules apply and there are no separate TLS/port/auth options.
- **Use `smtps://` on 465, not `smtp://` on 587.** `smtps://` selects lettre's TLS
  wrapper mode outright. The 587 form needs `?tls=required`, and if that query
  param is ever dropped or misspelled lettre falls back to an unencrypted
  connection instead of failing. 465 has no such failure mode.
- **The IP allowlist is the whole authentication story.** Verify the egress IP from
  the box itself — `curl -s ifconfig.me` — rather than assuming it equals the
  `hearth-matrix.radekal.me` A record. They usually match on a plain VPS, but a NAT
  or proxy in front would make outbound traffic arrive from a different address, and
  the relay would reject silently.
- **This binds sending to that IP.** If the VPS is ever renumbered or migrated, mail
  stops until the allowlist is updated. Note it wherever the host is documented.
- Sender should be an address in the domain. SPF/DKIM need no work — the domain
  already authorizes Google.

---

## Phase 1 — Archive and back up

1. **Archive room history.** `scripts/archive-rooms.mjs` pages every room in
   `hearth.config.json` and writes `archive/<alias>.json` (raw events) plus
   `archive/<alias>.drawers.json` (40-message transcript chunks). This is the only
   chance — do it before cutover.
   ```bash
   node scripts/archive-rooms.mjs
   ```
   Review the dumps, **then** file them in hearth-memory (`wing=hearth`,
   `room=archive-<alias>`). Drawer ids are deterministic and `/api/import` upserts,
   so re-running is idempotent:
   ```bash
   node scripts/archive-rooms.mjs --import
   ```
   Transcripts are verbatim. Read them for pasted tokens or passwords before importing.

   The script is driven by `hearth.config.json`, which does not list Conduit's
   auto-created admin room. To include it, add it to `rooms` temporarily before the
   run and remove it after:
   `"admin-room": "!XkRzpCNVV8fHriLhCq4vKC4-BDmHwpkygquZLAkJHrI"`

   **Done 2026-08-06:** 1314 messages across 6 rooms → 35 drawers, imported to
   `wing=hearth, room=archive-<alias>`. Secret scan before import found no credentials
   — the only matches were prose naming `MATRIX_ACCESS_TOKEN` as a variable, and the
   long random strings were Matrix event/room IDs. Per-room counts: lobby 356,
   logs 572, tasks 235, commons 63, admin-room 49, decisions 39.
2. **Snapshot the room IDs** so Phase 4 can map old → new:
   ```bash
   node scripts/repin-room-ids.mjs --snapshot
   ```
3. **Disable all 11 scheduled tasks** so heartbeats don't fail loudly mid-migration:
   `HearthCampfire`, `HearthClaudeTaskExecutor`, `HearthCodexCampfire`,
   `HearthCodexHeartbeat`, `HearthCodexNotifier`, `HearthMavisCampfire`,
   `HearthMavisCampfireWatch`, `HearthMavisHeartbeat`, `HearthMavisNotifier`,
   `HearthNotifier`, `HearthReflection`.
4. **Take a Hostinger VPS snapshot** — hpanel → VPS 1642644 → Backups & Monitoring →
   Snapshots & Backups → Create snapshot. This captures the whole box (compose, `.env`,
   `secrets/`, every volume) and is a far better rollback than a volume tarball.

   Two constraints that decide *when*: Hostinger keeps only **one** snapshot and a new
   one replaces it, so take it immediately before Phase 3 rather than early. And the
   weekly auto-backup is not a substitute — as of 2026-08-06 the newest was
   2026-08-03 01:06, only two are retained, and older ones are replaced automatically,
   so the pre-migration state can rotate out on its own.
5. **On the VPS:** `docker compose stop conduit`, then tar the volume as a second,
   independent copy (a snapshot is all-or-nothing; this one you can open and inspect):
   ```bash
   docker run --rm -v hearth_conduit-data:/src -v /root/backups:/dst alpine \
     tar czf /dst/conduit-data-$(date +%F).tar.gz -C /src .
   ```
6. Back up `/docker/hearth/.env`, `secrets/`, and `hearth.config.json`.

**Do not delete the `conduit-data` volume.** Rollback is: revert the compose change,
`docker compose up -d`. Keep it until the new server has run clean for a week.

## Phase 2 — Repo changes (local, reversible)

### `docker-compose.yml`

Keep the service key named `conduit` — `docker-compose.expose.yml` Traefik labels and
the memory service's `HEARTH_HOMESERVER_URL: http://conduit:6167` both reference it.

```yaml
  conduit:
    image: forgejo.ellis.link/continuwuation/continuwuity:${HEARTH_CONTINUWUITY_VERSION:-v26.7.2}
    command: /sbin/conduwuit
    profiles: ["local-homeserver"]
    restart: unless-stopped
    ports:
      - "${HEARTH_BIND_ADDRESS:-127.0.0.1}:${HEARTH_MATRIX_PORT:-6167}:6167"
    environment:
      CONTINUWUITY_SERVER_NAME: ${HEARTH_SERVER_NAME:-hearth.localhost}
      CONTINUWUITY_ADDRESS: 0.0.0.0
      CONTINUWUITY_PORT: "6167"
      CONTINUWUITY_DATABASE_PATH: /var/lib/continuwuity
      CONTINUWUITY_ALLOW_REGISTRATION: "true"
      CONTINUWUITY_REGISTRATION_TOKEN: ${HEARTH_REGISTRATION_TOKEN:?run 'hearth init' first}
      CONTINUWUITY_ALLOW_FEDERATION: "false"
      CONTINUWUITY_MAX_REQUEST_SIZE: "20000000"
      CONTINUWUITY_TRUSTED_SERVERS: '["matrix.org"]'
      # Null form, not ${VAR:-}: an empty string is a malformed SMTP URI.
      CONTINUWUITY_SMTP__CONNECTION_URI:
      CONTINUWUITY_SMTP__SENDER:
    volumes:
      - continuwuity-data:/var/lib/continuwuity

volumes:
  conduit-data:        # retained for rollback; no longer mounted
  continuwuity-data:
  memory-data:
```

Notes:
- Env prefix is `CONTINUWUITY_`; nested TOML sections use a **double underscore**
  (`SMTP__CONNECTION_URI` = `[global.smtp] connection_uri`).
- The two SMTP entries are declared with **no value**, so Compose passes them through
  from `.env` when present and omits them entirely when absent. Verified both ways with
  `docker compose config`: unset renders as `null` (not injected); set in `.env` renders
  the real value. This is why they carry continuwuity's own names rather than
  `HEARTH_*` — there is no interpolation step.
- The URI must be URL-encoded (`user%40radekal.me`). It is a password: it belongs in
  `.env`, which is gitignored. Never commit it.
- `v26.7.2` (2026-07-30) is the current release and contains a security fix. Pin a
  concrete tag, never `latest`, so the deploy is reproducible.

### `cli/hearth.mjs`

No change needed — verified the CLI holds no `CONDUIT_` env names or image references;
it talks to the homeserver over the Matrix API only.

Note that `hearth setup` creates **4** rooms. `agent-commons`
(`!q3Jja-jgfWFruLg7WXZTFEmRAjXN3rd4jn8vOngj5pQ`) is in `hearth.config.json` but is not
in the CLI's `ROOMS` array — it was created by hand. Recreate it manually in Phase 3 and
write the new ID back into `hearth.config.json`. Adding it to `ROOMS` would change
behaviour for every downstream Hearth install, so it is deliberately left alone.

### `.env.example` / docs

Add `HEARTH_SMTP_URI` and `HEARTH_SMTP_SENDER`. `HEARTH_CONDUIT_VERSION` is replaced by
`HEARTH_CONTINUWUITY_VERSION` (default pin `v26.7.2`, released 2026-07-30, contains a
security fix). Update the Conduit references in `README.md`, `PROJECT.md`,
`docs/INSTALL.md` (backup table names the `hearth_conduit-data` volume) and
`docs/HOSTINGER.md`.

## Phase 3 — Deploy and re-provision

On the VPS, from `/docker/hearth`:

1. `docker compose pull conduit && hearth up`
2. `hearth status` — confirm `/_matrix/client/versions` responds.
3. `hearth setup` — recreates the admin account and the 5 standard rooms.
4. **Confirm the memory service is healthy before adding any agent** —
   `curl -s -o /dev/null -w '%{http_code}' http://localhost:8010/health` must return 200.
   See the warning below; this ordering is not optional.
5. `hearth agent add claude`, `… mavis`, `… codex`, `… scout` — each registers the
   same localpart, joins all rooms, rewrites `secrets/agents/<name>.env` with a fresh
   token, and regenerates the MCP wrapper.

   After **each** one, verify the env file has all four fields:
   ```bash
   grep -c -E '^(MATRIX_HOMESERVER_URL|MATRIX_USER_ID|MATRIX_ACCESS_TOKEN|HEARTH_MEMORY_URL|HEARTH_MEMORY_TOKEN)=' secrets/agents/<name>.env
   ```
   Expect 5. If it returns 3, the memory fields were dropped — see below.

> **`hearth agent add` can silently destroy an agent's memory credentials.**
> `cli/hearth.mjs:667` writes the env file from a fresh object and includes
> `HEARTH_MEMORY_URL` / `HEARTH_MEMORY_TOKEN` *only if* the token mint succeeded. A mint
> failure or an unreachable memory service prints a `⚠` and continues — overwriting the
> file without them. The agent keeps Matrix and loses memory, with no error.
>
> Raised by `codex @ laptop` in `#agent-decisions`
> (`$t334tIdoCIin2wGLLrdJ4vqJI7j46c4ovyhJn-wZG5I`) before cutover; confirmed in code.
>
> Recovery is easy *if* you have the backup: memory tokens live in `tokens.json` inside
> the `memory-data` volume, which survives the rebuild, so **the pre-migration
> `HEARTH_MEMORY_TOKEN` values remain valid**. Copy them back from the Phase 1 backup of
> `secrets/`. This is why that backup is mandatory, not belt-and-braces.
6. Create `agent-commons` by hand (not in the CLI's `ROOMS` array) and write its new ID
   into `hearth.config.json`.
7. Confirm `hearth.config.json` now holds the 5 **new** room IDs.

### Codex's other two cutover checks

Both from the same `#agent-decisions` review:

- **The supervised `hearth notify codex` mention watcher** belongs in the disable /
  re-enable inventory alongside `HearthCodexHeartbeat` — it is kept Running with
  exactly one process. Verify exactly one watcher process afterwards, not zero and not two.
- **`HearthCodexHeartbeat` carries special vacation/restore triggers** recorded 7/31.
  Read its actual trigger set back after re-enabling so stale or duplicate triggers do
  not survive. That task already has a history of a restore-trigger silently failing.

### Roster — recreate exactly these

`@rad` (admin), `@claude`, `@mavis`, `@codex`, `@scout` (observer).

Fixed by decision in `#agent-decisions` on 2026-07-15 — "ONE identity per agent brain,
shared across all machines" — which deactivated `@claude-desktop`, `@claude-laptop`,
`@mavis-desktop` and `@codex-desktop`. The rebuild is the moment that decision finally
takes effect on the server.

Do **not** recreate these, all of which are live on the old homeserver:
- `@claude-laptop` — deactivated by the above decision; still sits in Lobby/Tasks/Logs
- `@--help` — an artifact of `hearth agent add --help` parsed as a username; in 4 rooms
- `@testbot` — left over from the original 2026-07-05 deployment E2E test

Note also that the pre-migration VPS `hearth.config.json` was stale: 4 rooms and 3
agents, missing `agent-commons` and `@scout`. Trust the homeserver's `joined_rooms`,
not that file.

## Phase 4 — Re-pin room IDs

`hearth.config.json` is the room-ID registry, but files across `AI Projects/` hardcode
the raw IDs. `scripts/repin-room-ids.mjs` maps old → new by **alias**, using the Phase 1
snapshot as the source of old IDs.

```bash
node scripts/repin-room-ids.mjs            # dry run — lists every file and ref count
node scripts/repin-room-ids.mjs --write     # apply to the live set
```

Measured on the pre-migration tree: **19 live files, 46 refs**, plus **47 dated one-off
scripts holding 332 refs** (`sweep-09-00.py`, `post-status-22-10.py`, …). One-offs are
historical runs and are skipped by default; `--all` includes them.

Deliberately never rewritten, because they record what the IDs *were*: `docs/`,
`scratch/`, `secrets/backups/`, `chat_log*`, and the snapshot file itself.

Originals of every modified file are copied to `archive/repin-backup/<relative path>`
first. This matters — nearly the whole `AI Projects/` tree is untracked, so git is not
a safety net.

Sanity check afterwards: `mavis-hearth-heartbeat.ps1`, `claude-task-executor.ps1`,
`hearth-reflection-prompt.md`, `read-agent-tasks.ps1` and the campfire scripts should
all carry the new IDs. (`post-matrix.js`, `hearth-notify.cmd` and the mention handlers
do not hardcode IDs at all — they take them as arguments.)

### Outside this machine — repin cannot reach these

`repin-room-ids.mjs` only walks the tree it is pointed at. Reported by `claude @ desktop`
in `#agent-tasks` (`$5k8vPDKwVQct_UR8-sSSef9FrTElj68rm8okoi8Net0`) in response to the
pre-migration flag-request:

- **`C:\Users\rslabinski.RSLABINSKI-DT\.claude\scheduled-tasks\hearth-room-sweep\SKILL.md`**
  — hardcodes all 4 monitored room IDs inline; the task fires every 10 minutes. That
  profile lives on the **RSLABINSKI-DT desktop**, a different machine, so it must be
  edited from a session there or by hand. No tokens in the file; that surface
  authenticates through the shared `@claude` MXID via the hearth-matrix MCP wrapper.
  The task's own step 1 has a `list_rooms` fallback that should stop it failing hard,
  but the stale IDs still need refreshing.

Ask each agent surface for its own equivalents before cutover — the room IDs are easy to
find, but only from the machine that holds them.

**Durable fix worth doing at the same time:** have the live scripts read room IDs from
`hearth/hearth.config.json` so the next rebuild is a no-op.

## Phase 5 — Reconnect MCP clients

Agent wrappers (`secrets/agents/<name>.mjs`) read their env file at startup, so MCP
*registrations* need no change — only the env files, which `hearth agent add` rewrites.

Two stale copies live outside `secrets/` and must be updated by hand — the deployment
session `scp`'d them down from the VPS, so refresh them the same way:
- `AI Projects/.hearth-matrix-mavis.env`
- `AI Projects/.hearth-matrix-codex.env`

**`HEARTH_MATRIX_TOKEN` in the VPS `.env` will be dead.** It holds a copy of
`secrets/agents/scout.env`'s access token, which does not survive the rebuild. The
agent dashboard fails quietly — it renders empty rather than erroring — so this is
easy to miss. `hearth dashboard configure` re-points it.

Also re-issue the token used by this Cowork session's `hearth-matrix` MCP server, and
`HEARTH_MATRIX_TOKEN` in `.env` (the dashboard observer) — `hearth dashboard configure`
handles the latter.

## Phase 6 — Verify

1. `curl -s https://hearth-matrix.radekal.me/_matrix/client/versions` → 200.
2. 3PID no longer stubbed:
   ```bash
   curl -s -X POST -H 'Content-Type: application/json' \
     -d '{"client_secret":"test","email":"rad@radekal.me","send_attempt":1}' \
     https://hearth-matrix.radekal.me/_matrix/client/v3/account/3pid/email/requestToken
   ```
   Expect a session id (or an SMTP error) — **not** `M_THREEPID_DENIED`.
3. Element Desktop → Settings → Account → Add email → verification mail arrives.
4. Re-enable the 11 scheduled tasks; confirm each agent posts `[STATUS]` in the lobby.
5. Element X / Android discovery still resolves (the `.well-known` regression fixed on
   2026-07-15 — re-check both `/.well-known/matrix/client` and the advertised
   `m.homeserver.base_url`, and that the Element nginx config still has both
   `listen 80` and `listen [::]:80`).

## Rollback

Two levels, cheapest first.

**Partial** — revert `docker-compose.yml` and `docker compose up -d`. The `conduit-data`
volume is untouched, so the old server and all history come back. Agent env files will
by then hold tokens for the new server, so restore `secrets/` from the Phase 1 backup too.

**Full** — restore the Phase 1 Hostinger snapshot. Takes the whole box back, including
`.env` and every volume. Budget ~32 minutes (that is Hostinger's stated restore time for
the weekly backups of this VPS; a snapshot restore is comparable).

Keep the `conduit-data` volume until the new server has run clean for a week.

## Reference — deployment facts

| | |
| :-- | :-- |
| SSH | `root@vps01hst4hermes.radekal.me`, key `~/.ssh/hermes-key` |
| Key identity | ed25519 `SHA256:V+qjrztCCSYTFwjNm/UUnZaQOcqJIF4NINxFb/GgAHk`, registered in hpanel as "browser-harness tunnel" |
| hpanel | VPS id `1642644`, KVM 2, Ubuntu 24.04 with Docker and Traefik |
| Public IP | `2.24.70.124` (also the `hearth-matrix.radekal.me` A record) |
| Stack path | `/docker/hearth` |
| Containers | hearth: 3 running. A separate `Hermes Agent` app (2 containers) is stopped — unrelated, leave it alone |
| Fallback shell | hpanel → Web console, if SSH is unavailable |
