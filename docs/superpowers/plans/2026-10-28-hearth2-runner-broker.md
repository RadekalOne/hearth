# Hearth 2 runner and broker implementation plan

> **For agentic workers:** Use superpowers:executing-plans, with test-first implementation and one final fresh-context review.

**Goal:** Execute the approved piece-2 handoff on the isolated trial instance.

**Architecture:** A trusted controller owns the work record, broker, native-runtime connection and containment evidence. Workers receive only one ephemeral read-only memory capability, scoped to their current claim and selected memory wing/room. Every broker request is checked against the authoritative claim before reading upstream and again before releasing a response. Runtime activation remains disabled until account, tool enforcement and independent containment checks pass.

**Tech stack:** Existing Python/SQLite/FastAPI service and pinned Cloudroom 0.1.58. No production change or model substitution.

**Spec:** Approved piece-2 HC handoff, six-item VERIFY, `docs/hearth2/PIECE-1-SPEC.md`, `PREFLIGHT.md` and `RUNNER-RECORD-INTERFACES.md`. PR35 is merged at `6b6987b42a8560c78f9c367560ea604d8e407ca3`; its tree matches the passed `21cf340`.

## Boundaries and rulings

- Preserve native account settings, pinned runtime, approved rules 1.0, one active workload, the three-launch cap and the two-hour ceiling.
- Do not treat connected accounts, model catalog entries or receipts as billing, execution or containment PASS.
- Ruling: use an in-memory capability registry, so broker restart revokes all grants automatically; store only hashes of bearer capabilities. No mint/admin HTTP route. Trusted controller supplies scope; worker input cannot broaden it. Cost if wrong: controller must mint a fresh grant after broker restart or lease renewal.
- Ruling: broker allows only `memory_search` and `memory_get`, within a required wing and room. Root-only upstream callback owns credentials; no general memory URL/token is sent to workers. Cost if wrong: planners must provide relevant scoped knowledge rather than relying on unrelated wings.
- Runtime spike: pinned Codex adapter requests danger-full-access; Claude skips permissions and exposes managed delegation. An outer request containing a tool list does not itself enforce that list. Resolve actual enforcement before native prompts, without silently replacing the pinned runtime.
- Billing settings review completed by Rad on 29 October: both premium seats; retain Claude $75/month extra-usage limit; ChatGPT zero workspace credits and auto-reload off. Technical native acceptance gates remain.

## Review focus

Old claim/restore/role/plan/lease; worker tool/argument spoofing; scope leakage from search/get; revocation during an upstream read; token leakage and restart; adapter permission/delegation bypass; surviving descendants at deadline; measured usage versus unknown.

## Tasks

- [x] Broker core RED→GREEN: scoped ephemeral grants, exactly one active grant, fence on each read and response, scope/tool allowlist, bounded arguments, revocation/restart, no secret persistence.
- [x] Broker HTTP RED→GREEN: authenticated MCP read-only surface, no mint/admin route, forged methods and scopes refused, errors do not expose capabilities/upstream details.
- [ ] Runtime spike: establish a concrete enforceable tool/containment contract against pinned source and live host; return any pin-change requirement to Claude for review before installing it.
- [ ] Controller: account/allowance guards, claim-before-launch, durable dispatch/run identity, memory/rules context, polling/catch-up/missed windows, renewals, health tick and outside alarm.
- [ ] Containment: cap before prompt, deadline kill, independent empty proof, recovery/late closeout fencing, one incident/three attempts, unknown outcomes held.
- [ ] Native adapter/broker wiring and receipt fields; fixture tests first, no model fallback. Live exact-model acceptance waits for current usage evidence and preceding gates.
- [ ] A4/A6/A7/A8/A9/N2/N3 reproducible trial evidence, source regression suite, independent whole-branch review and Claude exact-commit review; human merge gate.
