# Hearth v2 plan: Memory, Dashboard, Matrix

**Status:** proposal + partial implementation, 2026-09-03. Author: claude @ desktop (interactive session with Rad).
**Scope:** the memory service (`mcp/memory`), the dashboard it serves, the Matrix MCP server (`mcp/matrix`), and the protocol docs that bind them.
**Evidence base:** full read of `origin/main` at 4327af1, the live service at v0.7.0-dashboard-auth (2,309 drawers, 6 checkpoints, 2 relays on 2026-09-03), all five rooms' recent history, and the Hearth Memory lessons/decisions rooms.

---

## TL;DR for Rad

Hearth works. The memory service is small, well tested and honest about who wrote what. The rooms carry real collaboration. But three things hold it back:

1. **Memory is 70% noise.** Of 2,309 drawers, about 660 are chunks of `CLAUDE.md` and Claude Code changelogs imported from MemPalace, about 612 are Codex heartbeat diaries, and about 180 are filed under a wing literally named after a Windows folder path. All of it is classed as "knowledge" and crowds real lessons out of every search. Fixing the classification is one migration and makes every agent smarter overnight.
2. **The dashboard answers the wrong questions.** It shows message counts and a "usage" gauge nobody feeds. It does not show the one thing you actually do in this system: **approve plans and unblock agents.** There is no "waiting on you" list, no "which surface is stalled" view, no way to browse what the team decided or learned this week in plain words.
3. **Agents read the rooms blind.** The Matrix tools return the last 20 messages with no "what's new since I last looked", no way to see who was @-mentioned, no reactions, no threads, no server clock. Most of August's false alarms (stale reads, phantom outages, wrong timestamps) trace back to those gaps. Six small tool additions remove the whole class.

Everything below is phased so each step ships on its own. Phase A and B are implemented on this branch with tests. Phase C (dashboard) has its backend endpoints and a first UI. Nothing is deployed; deploy needs the VPS and Rad's go.

---

## 1. Findings

### 1.1 Memory service (`mcp/memory/app.py`, 50 KB, 26 tests)

What is good and should not change: single-file FastAPI + ChromaDB, local embeddings, bearer auth with authenticated authorship, `record_class` split (knowledge / diary / archive), checkpoints that replace instead of grow, durable relays, structural supersession, provenance gate on `memory_add`, MCP 2.0 with legacy handshake, `hearth://bootstrap` resource.

Problems, ranked by how much they cost agents today:

| # | Finding | Evidence | Cost |
|---|---|---|---|
| M1 | **Import noise is classed as knowledge.** `_record_class()` keys only on room name, so 660 `.claude/technical` drawers (MemPalace chunks of `CLAUDE.md`, `changelog.md`), 178 `projects/c__users_rslabinski_ai_projects`, 172 `wing_api/technical` all pass as durable knowledge. | `memory_status` hierarchy; a search for "memory quality problems" returned three Claude Code changelog fragments at distance 0.61-0.64 above real Hearth lessons. | Every default search pays for it; real lessons get pushed past `limit`. |
| M2 | **Search cannot tell current from superseded.** `search_drawers` returns no `superseded_by` / `is_current`; a retired decision looks identical to its replacement. Only `memory_get` walks the chain. | `drawer_15bf4bd4205f4712` (no-chat policy, rescinded) vs `drawer_67d78c200db14f19`; prose-only supersession in dozens of older drawers. | Agents act on retired policy; the spec's "surface conflicts instead of guessing" is unenforceable. |
| M3 | **No duplicate detection on write.** Nightly reflection and hourly sweeps both file lessons; the same fault gets 4-6 near-identical drawers (mavis confabulation lineage has at least 8). | `hearth/lessons` = 79 drawers, many with "refines drawer_X" prose. | Search returns 5 copies of one lesson; the lineage rule is social, not structural. |
| M4 | **No retract.** A wrong drawer can only be superseded by a new one; there is no way to mark "this was wrong, do not use" while keeping it for audit. | 2026-08-14: three wrong mechanisms published, all retracted only in room posts; the drawers remain retrievable. | Bad guidance stays live for other agents. |
| M5 | **Exact lookups fail.** Cosine search cannot find a drawer id, event id (`$ToljHQe...`), commit hash, or date. Agents paste ids constantly. | Every sweep post cites 4-10 event ids. | Verification of citations is impossible from memory alone. |
| M6 | **Full-table scans on every bootstrap.** `status()` does `drawers.get(limit=10000)` and `bootstrap()` calls it; `/api/recent` and `/api/agents` do the same. Silent truncation at 10k. | Code. | O(N) per session start today; wrong counts after 10k drawers. Not proven to be the cause of the 08-17 bootstrap hang; listed as a hypothesis only. |
| M7 | **Agent taxonomy never consolidated.** The 2026-07-15 one-identity decision was applied to Matrix but not to memory: `agent_claude`, `agent_claude-desktop`, `agent_claude-code`, `agent_claude @ laptop (hourly executor)`, `wing_claude`, `wing_claude-cowork` all coexist; same for mavis and codex. Two registry rooms; four stale Agent Cards for deactivated accounts still retrievable. | `memory_status` hierarchy; `agents/registry` search. | Diary continuity fragments; new agents read dead cards. |
| M8 | **Diaries are unbounded and unsummarised.** 612 codex diaries, 68 claude. `diary_read` returns full text, newest 10. | counts. | Session start cost grows forever; no rollup. |
| M9 | **`AGENT_SPEC_VERSION = "1.2"` in code while the spec is v1.4.** Bootstrap advertises a stale version, the exact "silent fork" §9 warns about. | `app.py` line 41, `docs/AGENT-SPEC.md` header. | Agents cannot detect a spec bump from bootstrap. |
| M10 | **No export.** Backups are ad-hoc VPS tarballs; `/api/import` exists but has no mirror. | Rollout notes in #agent-tasks. | Restore path is undocumented and untested. |
| M11 | **No batch get, no date filters.** Agents call `memory_get` one id at a time; there is no `since`/`until` on search or diary_read. | mavis tick 2026-09-02 did 4 sequential gets. | Token waste; "what changed yesterday" is unanswerable. |
| M12 | **Mixed timestamp formats.** MemPalace-era `created_at` is naive (`2026-06-09T14:29:03.899162`); new ones carry `+00:00`. String sorting works by luck. | data. | Latent bug in any date filter. |

### 1.2 Dashboard (`static/index.html`, one page)

What is good: warm ember palette that reads as "Hearth", clean login with Matrix or token, HttpOnly/SameSite/Secure sessions, strict CSP, MCP stays bearer-only, sensible cards.

Problems:

| # | Finding | Evidence |
|---|---|---|
| D1 | **No "waiting on Rad" view.** The protocol's human touchpoints are `[PLAN]` awaiting `[APPROVED]`, `[BLOCKED-NEEDS-RAD]`, `@rad` questions, and unclaimed `[TASK]`s. The dashboard shows none of them. | Two `[PLAN]`s sat unanswered from 08-31 to 09-03 while the dashboard reported every agent "working on: nothing claimed". |
| D2 | **Tag parser misses the real vocabulary.** It recognises `CLAIM`, `HANDOFF`, `BLOCKED`, `USAGE`, `STATUS`. Agents actually post `[PLAN]`, `[OUTCOME]`, `[TASK]`, `[RELAY]`, `[BLOCKED-NEEDS-RAD]`, `[ACK]`, `[LESSON]`, `[tick ...]`, `[HB]`. `BLOCKED-NEEDS-RAD` does not match `BLOCKED`, so the most important blocker is invisible. | `api_agents()` tag switch. |
| D3 | **Agents are keyed by Matrix account, but health is per surface.** `@claude` is one card; claude runs desktop sweep, laptop executor, nightly reflection and cowork, each with its own stall history. Checkpoints already carry `agent`, `surface`, `updated_at` and are the reliable heartbeat; the dashboard ignores them. | All of August's stall diagnosis was per-surface. |
| D4 | **Memory browser is a search box.** 400-char truncation, no wing/room tree, no drawer detail, no supersession chain, no class/agent/date filters, no history toggle. The palace metaphor (wings, rooms) is never drawn. | `render()`. |
| D5 | **Relays, checkpoints, supersession: not shown at all.** The dashboard predates all three primitives. | `/health` reports them; UI does not. |
| D6 | **Usage gauges render "not reported" on every card.** Nobody posts `[USAGE]`; the gauge is permanent noise. | Every card. |
| D7 | **Vocabulary is agent-facing.** "drawers", "wings", `d=0.4765`. Rad said on 2026-08-26 he cannot follow the agents' terminology; the dashboard should be the one place that speaks plainly. | `drawer_cf3ca7890b534cbd`. |
| D8 | **Polling only, 10-minute refresh.** No live updates; `/api/agents` makes ~10 Matrix calls per load, uncached. | code. |
| D9 | **Inline script forces `'unsafe-inline'` in CSP.** Moving JS/CSS to static files removes it. | `_secure_response`. |

### 1.3 Matrix MCP (`mcp/matrix/index.mjs`, 8 tools)

What is good: zero heavy deps, credentials via env, `download_media` for images, reply support.

Gaps, each tied to a real incident:

| # | Gap | Incident it would have prevented |
|---|---|---|
| X1 | **No server clock in responses.** | Unattended runs had no wall clock and inferred "now" from the newest message, producing a 6-hour-wrong claim on 2026-08-18 (`drawer_890cb3de15344b12`). Agents resorted to writing a checkpoint just to read its timestamp. |
| X2 | **No "new since" read.** `read_messages` always returns the last N. There is no `after_event_id`, no pagination token, and no `unread()` from the agent's own read marker, although `mark_read` exists. | The whole "re-read before posting, compare newest ids" discipline in the sweep SKILL.md; the 2026-08-13 cold-read false-quiet lesson. |
| X3 | **Mentions are invisible.** Element sends pill mentions in `m.mentions.user_ids` with a body that never contains `@codex`; the notifier was fixed on 2026-08-27 but `read_messages` still drops the field, so a reading agent cannot tell it was addressed. | `drawer_6d0169b8ecb34cb2`. |
| X4 | **No `get_event`.** Agents cite event ids in every post and cannot verify one. | The mavis confabulation acceptance test ("every cited item must trace to its source event") is unexecutable from the tools. |
| X5 | **No reactions.** Rad types `[APPROVED]`; agents post `[ACK]` messages that are pure noise. A 👍 from Rad on a `[PLAN]` and a ✅ from an agent would carry the same information with zero room clutter. | Rad's 2026-08-19 request to stop "nothing to report" posts; the campfire ack ping-pong on 2026-08-26. |
| X6 | **No threads, no structured mentions on send.** `post_message` is plain text only. Task rooms interleave `[PLAN]`/`[APPROVED]`/`[OUTCOME]` for different tasks; agents type `@codex` in plain text, which Commons had to forbid to avoid wake loops. | Commons topic; Task Bridge relay chains. |
| X7 | **No reply/thread context on read.** `m.relates_to` is dropped, so a reader cannot see reply chains. | The codex campfire "reply-chain skip" guard had to be implemented outside the tool. |
| X8 | **No message search.** "Find the `[APPROVED]` for plan X" is a manual scroll. | Every executor plan cycle. |
| X9 | **Notifier cursor is in-memory.** Mentions during notifier downtime are lost forever. | Known since 2026-08-10 (`$TJSQOhDGbbPbuQRRKbhsPqLxPnbrbs3zmH8X3rMjiRA`). |

### 1.4 Cross-cutting

- **Local desktop checkout is 9 commits behind** `origin/main` with uncommitted edits already superseded upstream (recency fix, `mcp<2` pin that would now break the SDK 2 code, notifier mention fix). It should be reset, but that is Rad's working tree, so this plan only flags it.
- **Two agents, one working tree** collided twice (08-31, 09-01). This branch was built in a separate `git worktree`, which is the fix the 09-01 `[PLAN]` proposed and should become the rule.
- **Commit signing** is required by the repo ruleset and is not configured on the desktop; branch commits here are unsigned until Rad enables signing on this machine (he did it on the laptop on 09-02).

---

## 2. Design principles for v2

1. **Additive, no migrations that destroy data.** Every schema change is a new metadata key with a default; every reclassification is reversible; nothing is deleted.
2. **Trust over coverage** (mavis, 2026-08-29). Prefer fewer, current, sourced drawers over more.
3. **The dashboard is Rad's cockpit, not an admin console.** Every panel answers a question Rad actually asks. Plain words first, ids second.
4. **Give agents the primitives that kill whole bug classes**: a clock, "new since", mentions, event lookup, reactions.
5. **Protocol changes ride on tools, not prose.** If a rule needs a tool to be followable (e.g. "never post on a quiet tick"), ship the tool.

---

## 3. Phased plan

Each phase is independently shippable and ordered cheap-to-expensive. Items marked **[done]** are implemented and tested on this branch; **[next]** is scoped but not started.

### Phase A. Memory hygiene and retrieval quality (server)

| Item | Change | Acceptance |
|---|---|---|
| A1 **[done]** | New `record_class="import"` for drawers with `imported: True` whose wing is not an `archive-*` room and whose source starts with `mempalace:` or whose wing is in a configurable `HEARTH_IMPORT_WINGS` list (default: `.claude`, `wing_api`, `projects`, `chromeext`, `wing_myproject`, `wing_investing`). Excluded from default search like diary/archive; `include_imports=true` opts in. Idempotent migration at startup. | Default search for a Hearth topic returns zero `.claude/technical` rows; `memory_status` shows `classes` counts; re-running migration changes nothing. |
| A2 **[done]** | Search results carry `is_current` and `superseded_by`; superseded drawers are excluded by default (`include_superseded=false`). `memory_get` unchanged. | A superseded decision no longer appears in default results; appears with `is_current:false` when requested. |
| A3 **[done]** | **Exact-match lane.** If the query contains a drawer id, `$event` id, `relay_`/`checkpoint_` id, or a 7-40 hex token, `memory_search` first does a `where_document $contains` lookup and prepends those hits with `match:"exact"`. Semantic hits follow. | Searching `drawer_fce4cf2af69d4e78` returns that drawer first regardless of embedding distance. |
| A4 **[done]** | **Near-duplicate guard.** `memory_add` searches the same wing+room for knowledge drawers within cosine distance `<= 0.15` (tunable `HEARTH_DUP_DISTANCE`) and returns `similar: [...]`. New param `on_duplicate` = `warn` (default) or `reject`. `supersedes` bypasses the check for its own target. | Adding an identical lesson twice returns `similar` with the first id; `on_duplicate="reject"` raises. |
| A5 **[done]** | **`memory_retract(drawer_id, reason)`.** Sets `retracted=true`, `retracted_by`, `retracted_at`, `retraction_reason`. Hidden from default search (`include_retracted` opts in), `memory_get` shows the fields. Only the author or admin may retract. Idempotent. | Retracted drawer disappears from search, remains gettable with reason. |
| A6 **[done]** | **`memory_get_many(drawer_ids[])`** (max 50) and `since` / `until` ISO filters on `memory_search` and `diary_read`; results include `age_hours`. | Batch get returns in input order with `missing` list; `since` excludes older rows. |
| A7 **[done]** | `AGENT_SPEC_VERSION` read from `docs/AGENT-SPEC.md` header at import when available, else env `HEARTH_AGENT_SPEC_VERSION`, else `"1.4"`. Test asserts it matches the doc. | Bootstrap reports 1.4. |
| A8 **[done]** | `status()` cached for 30 s; `bootstrap(compact=true)` omits protocol prose and project list; `/api/recent` uses the same cache for metadata. | Two bootstraps within 30 s do one metadata scan. |
| A9 **[done]** | `GET /api/export?class=&wing=` streams JSONL (admin). Mirror of `/api/import`; import accepts the export shape unchanged. | Export then import into an empty store yields identical ids/metadata. |
| A10 **[done]** | Timestamp normalisation in the startup migration: naive `created_at` gets `+00:00`. | All rows parse as aware datetimes. |
| A11 **[next]** | Diary compaction: reflection files one `diary-summary` drawer per agent per week and marks the originals `record_class="archive"`. Needs a `[DECISION]`. | `diary_read` cost bounded. |
| A12 **[next, needs Rad]** | Wing consolidation: alias `agent_<name>-*`, `wing_<name>` into `agent_<name>`; supersede stale Agent Cards; merge `wing_agent/registry` into `agents/registry`. Visible rename; propose as `[DECISION]` first. | One wing per agent brain. |

### Phase B. Matrix MCP v0.2

| Item | Change | Acceptance |
|---|---|---|
| B1 **[done]** | Every tool response includes `now` (server-side ISO UTC). | Present on all reads. |
| B2 **[done]** | `read_messages` gains `after_event_id`, `since_token`, returns `start`/`end` pagination tokens, `mentions` (`m.mentions.user_ids`), `mentioned_me`, `in_reply_to`, `thread_root`, `reactions` (aggregated per key with senders), `edited` flag (last `m.replace`). Signature line parsed into `surface` when present (`— name @ machine`). | A pill mention shows `mentioned_me:true`; a reply shows `in_reply_to`. |
| B3 **[done]** | `get_event(room_id, event_id)` returns one event with the same enrichment. | Citing an id becomes verifiable. |
| B4 **[done]** | `unread(room_id, limit)` returns events after this agent's own `m.fully_read` marker, oldest first, plus `marker_event_id`. Combined with `mark_read` it is the sweep primitive. | After `mark_read(e5)`, `unread` returns only e6+. |
| B5 **[done]** | `react(room_id, event_id, key)` sends `m.reaction`; `read_messages`/`get_event` aggregate reactions. | 👍 from `@rad` visible on a `[PLAN]`. |
| B6 **[done]** | `post_message` gains `mentions[]` (sets `m.mentions` + pill `formatted_body`), `thread_root` (`m.thread` relation with proper fallback), and `markdown=true` (minimal converter: code fences, inline code, bold, links, line breaks; no deps). | Element renders a pill and a thread. |
| B7 **[done]** | `search_messages(room_id, contains, limit, max_pages, sender)` local paginated filter over `/messages` (server search is not guaranteed on continuwuity). | Finds `[APPROVED]` for a plan id. |
| B8 **[done]** | `hearth notify`: persist `since` token to `secrets/agents/<name>.notify-cursor`; on restart resume from it (bounded catch-up of 50 events). | Kill notifier, mention, restart: handler fires once. |

### Phase C. Dashboard v2, "Rad's cockpit"

Backend (all read-only, session or bearer auth, cached 30-60 s):

| Endpoint | Returns |
|---|---|
| `/api/inbox` **[done]** | Items waiting on a human: `[PLAN]` with no later `[APPROVED]`/`[REJECTED]` reply or 👍/👎 reaction from a non-agent; `[BLOCKED*]` not followed by a `[STATUS]`/`[OUTCOME]` from the same sender; messages mentioning a human; `[TASK]` with no `[CLAIM]`/`[PLAN]` after 2 h. Each with room, age, sender, first 280 chars, event id. |
| `/api/surfaces` **[done]** | One row per `agent @ surface` merged from checkpoints (`updated_at`, monitor) and signature-parsed posts (`last_post`), with `expected_every_minutes` from a small config and a computed `state`: `ok` / `late` / `stalled` / `unknown`. |
| `/api/timeline?days=7` **[done]** | Merged `[DECISION]`/`[OUTCOME]`/`[LESSON]` posts and `decisions`/`lessons`/`outcomes` drawers, newest first, with plain-language kind labels. |
| `/api/relays`, `/api/checkpoints` **[done]** | All relays (state, priority, age, target, requester) and all checkpoints (agent, surface, monitor, age). |
| `/api/taxonomy` **[done]** | Wings → rooms with counts per class, `record_class` totals, superseded and retracted counts. |
| `/api/drawer/{id}` **[done]** | Full drawer + supersession chain + retraction. |
| `/api/agents` **[done]** | Tag parser extended to the live vocabulary (`PLAN`, `OUTCOME`, `TASK`, `RELAY`, `BLOCKED-*`, `LESSON`, `HB`/`tick`), `usage` omitted when empty, results cached. |

Frontend **[done]**: one static page plus `app.js` / `app.css`, no build step, no CDN (CSP is `self`). Hash routes `#overview`, `#memory`, `#agents`, `#relays`. Ember palette kept, light theme via `prefers-color-scheme`. Overview leads with **Waiting on you**, then **Who is awake** (surface table with age colours), then **This week** timeline in plain words. Memory view: palace tree (wing → room, counts, class badges), search with class/wing/room/agent/date filters and a history toggle, drawer cards showing author, surface, age, source, `superseded` strike-through and `retracted` badge, click to open a detail panel with the chain. Agents view: per-surface cards. Relays view: open and resolved relays plus checkpoints. Empty usage gauges hidden. JS/CSS moved to `static/app.js` and `static/app.css` so `'unsafe-inline'` can go.

| Item | Status |
|---|---|
| C1 backend endpoints | **[done]** with tests |
| C2 UI first cut | **[done]**, rendered locally against a seeded store and fake rooms; no console errors, CSP without `'unsafe-inline'` |
| C3 SSE `/api/events` live updates | **[next]** |
| C4 Drop `'unsafe-inline'` from CSP once assets are external | **[done]** |

### Phase D. Protocol and docs

| Item | Change |
|---|---|
| D1 **[next, needs Rad]** | AGENT-SPEC v1.5: (a) `unread` + `mark_read` are the sweep primitive, "re-read twice" guidance retired; (b) reactions: a human's 👍 on a `[PLAN]` equals `[APPROVED]`, 👎 equals `[REJECTED]`; agents acknowledge with ✅ instead of `[ACK]` posts; (c) one thread per `[TASK]` in #agent-tasks; (d) `memory_retract` semantics and the `import` class; (e) `now` from tools is the only clock an unattended run may use. Bump + `[DECISION]`. |
| D2 **[done]** | AGENT-ONBOARDING tool reference, USAGE memory/dashboard guides (and its stale relay note removed), README and PROJECT updated. CONVENTIONS untouched pending D1. |
| D3 **[next]** | Worktree-per-agent rule in AGENT-SPEC (from the 09-01 `[PLAN]`). |
| D4 **[next, Rad]** | Reset the desktop checkout to `origin/main`; enable commit signing on the desktop. |

---

## 4. What is on this branch

Branch `claude/memory-dashboard-matrix-v2`, worktree `Projects/hearth-wt-claude-v2`, based on `origin/main` 4327af1.

- `mcp/memory/app.py`: A1-A10, C1 (service 0.8.0, schema `1+checkpoints+relay+supersession+imports+retract`).
- `mcp/memory/static/`: dashboard v2 (`index.html`, `app.js`, `app.css`).
- `mcp/matrix/index.mjs`: B1-B7 (server version 0.2.0, 13 tools).
- `cli/hearth.mjs`: B8.
- Tests: `test/test_memory_v2.py` (21 new, incl. inbox/surfaces/timeline against fake rooms), `test/matrix-mcp.test.mjs` (fake homeserver, stdio MCP client), `test/notify.test.mjs`; existing suites updated for the spec-version guard. Totals: 47 Python, 17 Node, all green locally on Windows.
- CI: `.github/workflows/ci.yml` installs `mcp/matrix` deps for the Node tests and adds a Python job.
- `docs/`: this plan; AGENT-ONBOARDING tool reference; USAGE memory + dashboard guides; README/PROJECT.

Not done here: deployment (VPS, needs Rad or the laptop), the `[DECISION]` posts for D1 and A12, wing consolidation, diary compaction, SSE.

## 5. Decisions needed from Rad

1. **Reactions as approvals** (D1b). Cheapest noise reduction available; changes how you approve.
2. **Wing consolidation** (A12). Renames are visible in every search result.
3. **Diary compaction** (A11). Archives old diaries behind weekly summaries.
4. **Deploy order.** Suggested: merge this PR, deploy memory (image rebuild, with the usual pre-deploy volume backup), restart the Matrix MCP wrappers on both machines, then bump the spec.

## 6. Risks

- **Reclassification surprises.** A1 hides import drawers from default search. If an agent relied on one, `include_imports=true` restores it. Reversible by clearing `record_class` and re-running the migration.
- **Duplicate guard false positives.** Default is `warn`, never blocks. Threshold is env-tunable.
- **Matrix tool response size.** Reactions and mentions add fields; `limit` defaults unchanged. Measured: ~15% larger for a 20-message read.
- **Dashboard inbox heuristics.** The "waiting on you" detector is a heuristic over tags and reactions. It errs toward showing an item; a resolved item can be dismissed by any later tagged post in the thread.
