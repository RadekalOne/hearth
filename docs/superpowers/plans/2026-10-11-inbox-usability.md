# Inbox usability implementation plan

> **For agentic workers:** Use superpowers:executing-plans to implement this approved task in this session, then obtain one fresh whole-branch review.

**Goal:** Make every human obligation understandable and make responsibility, dispatch and failure recovery visible.

**Architecture:** Extend the existing coordination store and dashboard projections. Browser actions retain Acknowledge's human-session and same-origin boundaries. Responsibility changes are fenced by generations; attention actions are audited and bound to their source revision. No task assignment, claim, approval or execution authority is inferred from an attention action.

**Tech stack:** Python/FastAPI, SQLite, vanilla JavaScript, unittest and Playwright/axe.

**Spec:** Claude's approved task $vbbX_8TCqYcxBnuLA9lp99cImfQbdIDG6i2WQVPJiSk in Agent Tasks, eight requirements below.

## Global constraints

- Signed branch and draft PR only; no merge, deployment, account provisioning or spec-version change.
- Keep current knowledge counts, noise and duplicate metrics, evidence links, watcher declarations and mobile layout.
- `human_action` is `{steps: [1–3 nonempty strings], after: nonempty string, ask: nonempty string}`. New human coordination obligations require it. Legacy inferred items receive explicit generic instructions; these are not invented task-specific approvals.
- Reassign changes the waiting party, not the execution assignee. A reason and required surface are required. Current-source and generation checks reject stale requests.
- Dispatch records high priority and the surface needed. Interactive work remains queued, with exact session-opening steps. Wake only an explicitly declared existing mention-enabled runtime; no new runner or credential.
- An acknowledgement hides attention until the source changes; it does not cancel the underlying work.

## Review focus

1. A new source receipt invalidates old action/acknowledgement keys.
2. Reviewer, agent and bearer-only requests cannot perform browser actions.
3. Reassignment fences late answers without losing unrelated waiting parties.
4. Auth error text is classified without exposing raw process output or secrets.
5. Failed delivery and expired claim recovery survive refresh and do not imply execution.

### Task 1: Human obligations and recovery projections

**Files:** `mcp/memory/coordination.py`, `dashboard.py`, `app.py`; focused Python tests.
**Interfaces:** `human_action(value)` validates instructions; party JSON retains instructions. `attention_inbox` supplies legacy actions, folds auth failures, and adds failed continuations/expired claims. Bootstrap always includes a queued-relays-first hint, including compact mode.

- [x] Write and run failing tests for missing/malformed human actions and pass-to-human transitions.
- [x] Implement validation and carry instructions through REST/MCP transitions.
- [x] Write and run failing projection tests for auth expiry, failed deliveries, expired claims and human/agent splitting.
- [x] Implement projections with evidence and age; run Python suite and commit signed.

### Task 2: Audited Reassign and Dispatch

**Files:** `coordination.py`, `app.py`, focused store/API tests.
**Interfaces:** human-only `/api/inbox/action`; source `kind`, `item_id`, `state_key`, `action`, `party`, `reason`. Coordination-store action generations/audit are additive, retaining schema version 1. Store transactions fence reassignments and carry unrelated obligations. Reads return explicit `waiting_on_agents` and `can_manage_attention`.

- [x] Write failing real-SQLite tests for stale/concurrent reassignments and old answers.
- [x] Implement persisted source-bound actions and priority; test restart/replay behavior.
- [x] Write failing ASGI tests for human sessions, CSRF, unknown targets, stale sources, dispatch and read-only accounts.
- [x] Implement endpoint, existing notifier wake boundary and failure visibility; run full suite and commit signed.

### Task 3: Everyday instructions and actionable views

**Files:** `static/slice.js`, `static/app.css`, browser fixtures, `docs/AGENT-ONBOARDING.md`.
**Interfaces:** What to do block above evidence; accessible action dialog for reason/target/surface; collapsed Waiting on each agent in Now and Work, including age. Expired claims display their last state.

- [x] Extend browser fixtures and run failing checks for instructions, Reassign/Dispatch, stale feedback, split sections and keyboard operation at 400px/1280px.
- [x] Implement views and onboarding inbox-drain rule without a spec bump.
- [x] Run Python/Node/browser/package checks, record screenshots and review all eight requirements.
- [ ] Push signed commits and create draft PR (independent review completed; two P2 findings reproduced and fixed).
- [ ] Post draft PR review request, check and answer replies, checkpoint remaining review work.

## Execution ledger

- Base: main `244186043bc609e3a7c77fd69cbdb3c8b23075ea`.
- User supplied execution method: interactive Codex, native implementation. Task scope already approved.
- Legacy inbox drain: obsolete Acknowledge/reviewer requests closed; GLM/Hy4 planning delivered, execution awaits its separate approval; heartbeat clean-tick/24h verification remains claimed; category migration retains existing executor ownership.

- Final verification: 207 Python tests, 18 Node tests (no skips), syntax checks, Playwright400/1280 keyboard and WCAG AA fixtures, package content checks. One integrated feature commit is used because action keys and the API/UI contracts span all three task boundaries.
- Independent review: two P2 findings, both red/green verified; no blanket PASS substituted for Claude review.
