# Relay execution under the provider-enforced zero-credit cap

> Use superpowers:executing-plans inline, TDD, and the existing Cowork review loop for the final independent review. No implementation delegation.

**Goal:** execute one explicitly approved relay task through the existing organizational Codex seat, with the provider's saved zero-credit cap checked at each dispatch, bounded proposal/test execution and honest usage receipts.

**Authority/spec:** Rad's direct laptop instruction to pick up Claude's task `$vfe2S_7ChyF2Fz72_J13uRlUUp3nOfLP0PuxS_1u96k`; amended B in that task; `docs/hearth2/ENTITLEMENT-PROBE-DRAFT-2026-11-10.md`. This supersedes the earlier independent-ceiling proposal `$YCvU79KvTzpakqDFHXnFAJjipTD3Zt8VpOfMfXPjYmY`. No new local monetary ledger/ceiling design.

**Architecture:** retain current Matrix work/review/approval binding and durable one-attempt state. Trusted controller reads authoritative admin evidence before each dispatch and checks native capacity separately. The reviewed model path returns only a bounded proposal; candidate code and tests run only in isolated credential-free network-none environments, never on the trusted Windows host. The existing installed relay remains intake-only throughout build and review.

**Tech stack:** existing Python stdlib controller, pinned Codex app-server, SQLite state, Windows Job ownership and cached trial test image. No app/SDK/global dependency installation, account change or new automation.

## Estimate and actual blocker

Estimate **3–4 working days** for the disabled execution-path implementation and credential-free acceptance, plus Claude review turnaround and the separately approved supervised run. Rough allocation: one day account evidence/approval composition, one day bounded turn/cleanup, one to two days isolated test composition and failure/restart acceptance. This is an engineering estimate, not a delivery commitment or evidence of current background activity.

Dependency: an authoritative **read-only per-dispatch source** for the seat's saved override and workspace credits-spent. The current native metadata transport exposes neither. Initial supervised acceptance can use fresh authenticated admin-console readback; unattended dispatch cannot reuse that indefinitely. First inspect existing approved admin/usage surfaces; document schema, account binding, observation freshness and failure behaviour. Do not guess an endpoint, scrape with a worker credential, install a new service or accept a caller boolean. If no supported unattended readback exists, deliver the supervised/manual-evidence boundary and keep unattended dispatch refused, identifying that exact remaining dependency. The provider cap itself is accepted as the financial boundary, not disputed.

## Global constraints

Model turns and paid runs require Rad's separate explicit `[APPROVED]`. Broader activation, merge, deploy and production contact are excluded. Keep the enabled installed intake-only relay, source pins, schedule, independent Pause action, unrelated jobs, and inactive 900-second/full-run policy unchanged. Branch code is not installed. No account/credential settings or purchases. No production contact. Per-task review and Rad approval remain independent authorities.

## File map and steps

### 1. Account evidence and dispatch authorization

Files: new `ops/hearth2/relay_financial.py`, `test/test_relay_financial.py`; later integrate `relay_native.py`, `relay_live.py`, `offline_relay.py` only in the disabled candidate.

- [ ] Identify and record the actual trusted read-only source for override and workspace spend. A tested normalizer with synthetic fields is not a live source.
- [ ] Write failing cases for wrong seat/workspace/route, absent or nonzero override, positive workspace spend, stale/future/unknown/partial readback, API-key/provider fallback, exhausted native quota and missing task approval.
- [ ] Implement validation bound to the authenticated account/workspace, exact task generation/base/scope/approval and immutable run intent. Persist evidence source/reference/hash and time before sending; no secrets/raw admin content in receipts. Numeric zeros must not admit booleans, NaN or omitted fields. A manually supplied snapshot must be explicitly labelled supervised, freshness-checked, and cannot enable unattended operation.
- [ ] Re-read at every dispatch immediately before model send, after any lengthy setup; consume no work generation while evidence is unavailable. Refuse without a thread or turn on failed preflight.
- [ ] Prove positive synthetic admission and all negative cases without credentials or a provider. Do not remove the installed refusal or auto-activate any branch build.

### 2. Composed bounded native proposal turn

Files: `ops/hearth2/relay_native.py`, `relay_launch.py`, `test/test_relay_native.py`, `test/test_relay_launch.py` (reuse reviewed request guard patterns, no fixture-only bypass).

- [ ] Write failing protocol tests for exact model/provider/request allowlist, returned effective sandbox/policy mismatch, pre/post-send revocation, silent output, event/byte overflow, tool requests, unmatched IDs, malformed/repeated closeout, wrong thread/turn and interrupted creation.
- [ ] Build the real transport path behind verified approval/evidence. Record thread/turn IDs and send progress durably, including ambiguous sends; forbid automatic retry/adoption. Model output cannot select commands, destinations or broaden paths.
- [ ] Tie independent whole-process cutoff/Job ownership to the original epoch/deadline; prove Pause, process crash and silent timeout stop all owned children. Unknown cleanup remains held and prevents re-dispatch. Do not silently expand the original deadline.
- [ ] Keep a separate tiny entitlement probe (0.159.1 on trial) and local relay native client pins distinct; a trial entitlement PASS does not accept Windows unattended runtime. Never substitute artifacts without a reviewed exact manifest.

### 3. Isolated candidate test and usage reconciliation

Files: new `ops/hearth2/relay_candidate_tests.py`, `test/test_relay_candidate_tests.py`; `relay_launch.py`, `relay_live.py`, install artifact builder only after composition is reviewed.

- [ ] Write failing tests for path traversal/base mismatch, host command injection, image/CID mismatch, credential/network/mount attempts, cutoff failure, missing/malformed test receipt, and concurrent task/restart handling.
- [ ] Compose bounded source snapshot/proposal application with a fixed trusted test command in an existing verified cached credential-free network-none trial environment. No model-selected command and no candidate-code execution on the controller. Prove empty/removal outside the worker before recording technical completion.
- [ ] Re-read same-scope workspace credits-spent after execution; >0 means financial FAIL. Missing/delayed/incomparable data remains unresolved, never PASS. Persist pre/post seat usage percentages and reset windows with source and attribution limits. No invented dollar estimate.
- [ ] Every executed-session status starts with two plain sentences and includes piece/test, run ID, seat usage %, actual evidence and next step. Understanding unknown, task state unchanged until separately accepted. Start the seven-day model-session reporting window only after an actual model session, not metadata polling.

### 4. Credential-free acceptance and review

- [ ] Run the positive synthetic path approval → preflight → thread/turn → proposal → isolated tests → stop proof → usage/status, with all real-provider and admin sources explicitly replaced by private fixtures. Test invalid/expired/revoked approvals, exhausted allowance, positive spend, cap changed between reads, silence/crash/ambiguous-send and Pause at critical boundaries.
- [ ] Run appropriate focused Windows and Linux tests, then the canonical full suite once final code is stable. Distinguish environment failures and fixtures from actual OS/provider acceptance.
- [ ] Post one exact-commit `[REVIEW]` to the existing loop, primarily Cowork, including source/artifact hashes, commands/times, exit/counts, unresolved sources and stop evidence. Avoid duplicate review wakeups across three Claude surfaces. Address findings before a runnable manifest is proposed.
- [ ] Freeze the exact reviewed execution manifest, prompt/fixture, numeric cutoffs and financial evidence requirements for the single conditional run approval. No scheduling, actual model send or installation under build authority. Any later activation needs Rad's explicit scope.

## Review focus

- A dated HM account observation is provenance, not a per-dispatch readback.
- Zero workspace spend is a workspace-wide stop condition; concurrent unrelated activity cannot be silently subtracted or attributed to this run.
- Quota percentage/reset is capacity evidence, not the cap readback; a live metadata PASS cannot open the turn gate.
- Post-send failure remains possibly sent and consumed; no rollback or restart creates a second attempt.
- Test-process exit alone is not empty-workload proof; uncertain children keep the task held.

## Work already complete

Task 1 from Claude's message is already closed: `08e88c1` pins both non-acceptance Dispatcher clocks and strengthens the neighbour assertion; `658e694` adds eight EST/EDT boundaries; `8b88623` requires New York zone data. Cowork independently tested `7847c4a`: module 20/20, relay 91/91, full 1,331 collected / 1,277 pass / 54 known Hearth 1 errors / zero failures. The final `8b88623` prerequisite has Windows 20/20 plus the deliberate missing-zone negative control and is submitted separately for exact-head Linux review. Do not reimplement this fix.

Current status: this plan and revised packet are prepared; execution-path tasks above have not been implemented. Installed runtime remains `f13de43` and its financial refusal stays closed.
