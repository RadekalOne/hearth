# Piece 2 walking skeleton — 10 November 2026

One credential-free task now goes from assignment through a claimed native turn
to a persisted receipt on the trial VPS. Rad needs no new approval for this
fixture; activation, paid/provider runs and production changes remain gated.

This is the shape of A4/A8/A9, not their full live acceptance. It is not a
shipping runner, full RootLifecycleDriver composition or an account-entitlement
test. The frozen credential-inventory track was not reopened.

## What ran

Exact host `srv2065995`, root controller, existing isolated Codex 0.159.1 binary
`f1cd7fa4ac866c724122f173d408a95385257cbcc9ac5ce5ddba42669c74ba97`.
Every provider request retained model `gpt-6.1-sol`; only the fixture configuration
selected the explicitly synthetic loopback provider. No real login/auth files,
provider credentials, outside network, provider calls or paid inference.

The controller created a synthetic project/plan/approval/task in a new SQLite
record, scanned the queue once, and atomically claimed/reserved/consumed the
dispatch. A second poll found no dispatchable task. The reviewed model guard,
root model-decision journal, stdio client and thread adapter started one idle
thread. A fixture-only bounded extension then sent one `turn/start`.

The real native client processed two synthetic Responses streams inside that
one turn. The first requested `memory_get`; the second was returned only after
the model request contained the scoped Broker's unpredictable synthetic memory
challenge. The native tool call crossed a container loopback HTTP / private Unix
socket bridge to the real root-side `Broker`, with a minted claim-bound read
capability. No worker received SQLite access, upstream authentication or writes.

The final message carried the structured closeout back on stdio. After native
stdin closed, the actual container main process exited **0**. A root observer
outside the worker checked stopped/Pid0, the captured original cgroup empty or
removed, and exact container removal. Only then did the controller call existing
`DispatchRegistry.record_native_result`, committing the receipt and releasing
the slot. Understanding and actual seat charge remain unknown; no human result
acceptance was recorded.

## Acceptance observations

Final evidence root:
`/root/hearth-runner-trial/walking-cf1fb4d1c726419c9908e5b18f7275a0`.

| Control | Actual run ID | Result |
| --- | --- | --- |
| Positive A4/A9 shape | `run_17b112bd24e64cf2bd3af57d278fff77` | Real scoped memory read, completed native turn, exit0, verified empty, valid closeout, task `review`, claim closed, slot released |
| Missing-closeout A8 shape | `run_973734c3cf5242b9acd8a421548d5290` | Real scoped memory read and completed native turn, exit0, verified empty; closeout `missing`, task `ready`, one incident, slot released; no retry launched |

Both finite independent root watchdogs finished without firing. All walking
fixture containers were absent on the final inventory. All **309** previously
recorded baseline paths/resolutions/hashes were unchanged within that inventory's
coverage; this does not prove absence of unknown consumers. The default installed
client and unrelated services/configurations were not changed. Tmpfs homes vanished
with their containers; no host-side candidate home or account login was used.

## Real links and explicit stubs

| Link | Status | Shortest replacement work |
| --- | --- | --- |
| Work record, approval validation, claim, one-instance reservation, consume, receipt/incident settlement | Real existing Store/DispatchRegistry, on an isolated synthetic database | Connect approved real task source and controller polling entry point |
| Approval and assignment input | Synthetic fixture principals/decision only | Bind actual authenticated human/thread approval, never reinterpret this fixture as approval |
| Wake/poll loop | One foreground bounded snapshot scan | Real scheduler/wake integration and A4 runner-down, allowance and backlog variants |
| Model catalog/request guard and fresh model-list evidence | Real reviewed modules and pinned actual binary/catalog | Retain the same boundary in composed root launcher |
| Native turn/terminal-output adapter | Fixture-only extension, not shipped into production RPC port | Integrate reviewed one-shot turn and output settlement with native lifecycle IDs |
| Memory scope/expiry/claim authorization | Real Broker on root host | Use normal reviewed HTTP transport rather than this minimal fixture bridge |
| Memory data | One synthetic drawer/challenge | Approved real HM upstream callback; root retains its credentials |
| Model provider | Synthetic loopback Responses server; exact model string retained | Approved account/allowance gate and reviewed provider-egress route; paid turn requires Rad's `[APPROVED]` |
| Closeout transport and storage | Actual native stdio to trusted root settlement; persisted in `runs.closeout` | Ship the bounded controller output bridge; no broker worker-write API was added |
| Plan artifact | Synthetic `produced` reference only, no plan document transport/storage | Define bounded document artifact storage and record linkage |
| OS launch/claim fence/deadline/cleanup | Actual Docker isolation and root observations, but fixture-specific composition and finite watchdog | Resolve immutable assembly / native stdio contract with RootLifecycleDriver; keep v1 unchanged until reviewed |

RootLifecycleDriver v1 still forbids these bind mounts and interactive stdio.
This fixture did not silently relax it. Docker network-none, read-only rootfs,
UID1000, dropped capabilities, no-new-privileges and resource limits were used.
The Unix socket mount is deliberate local IPC, not evidence of zero host IPC.
Hostile-root isolation is not claimed. Shell remains disabled; the known bundled
bubblewrap warning remains open before any shell enablement.

## Tests, failures and review

- Test-first composition: four initial failures before implementation; additional
  regressions reproduced missing read-only tool metadata, unknown native output,
  cleanup/setup failure, expiry and the optimized-Python host check.
- Final **106 focused tests PASS**, exit0, 3.306s. Includes the 10 new fixture
  controls, existing guard/thread tests, claims, Broker, dispatch and native
  settlement. All **10 fixture controls also PASS under `python -O`**, exit0,
  0.528s. Final actual native pair: exit0 and both expected outcomes above.
- Broader discovery was attempted: **853 tests, 99 errors**, exit1. The staging
  host Python lacks `fastapi`, `httpx` and `yaml`; HTTP modules failed imports and
  frozen-track YAML-dependent tests reported unsupported-input errors. No
  full-suite PASS is claimed. Exact failing names and log SHA are in the evidence
  JSON; no unrelated dependency or frozen-track changes were made to hide this.
- One fresh-context read-only source review found Important cleanup/setup
  exception safety and an optimized-away `assert` host boundary. Both were fixed
  with RED→GREEN controls. Cleanup now independently attempts stop/inspection,
  revocation, listener close and evidence; uncertain outcomes stay held. An
  uncertain workload retains its independent cutoff. Expired claims use unknown
  reconciliation rather than inventing native completion. No second independent
  review or Claude PASS is claimed.
- Three initial diagnostic pairs failed because the fixture omitted MCP read-only
  annotations; the real client's `approval_policy=never` refused the read. Those
  six actual containers were confirmed stopped/empty/removed. Their original
  receipts/events remain intact; fresh absence checks plus unknown reconciliation
  now leave all six tasks/claims held. They are not relabelled passing or retried.
- An earlier successful pair preceded the final failure-path review fixes; the
  final pair above reran the exact final source. Evidence hashes identify both.

Staging logs, source and diagnostic recovery evidence:
`/root/hearth-runner-trial/walking-skeleton-20261110`.
Portable summary: `evidence/walking-skeleton-2026-11-10.json`.

## What this leaves open

Full live A4–A9/N2/N3, real entitlement/allowance and provider egress, composed
root lifecycle/recovery, real HM callback, shipped native-turn/output bridge and
artifact documents remain open. Pieces 3–5 were not started. The next planning
item is the bounded entitlement-probe decision packet, **prepare only**, plus
the five definition answers from Claude's task; neither was executed here.
