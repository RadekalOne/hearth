# Hearth-Codex-Offline-Relay — reconciled implementation plan, 12 November 2026

Status: PREPARED; awaiting approval of this concrete plan. No product code,
scheduler registration, worker session, WSL start, tests or service activation.
Task: codex-20261112-212920. Existing relay_8cd89cb609ed4819 is the SAME work,
claimed here; it must not create a second execution. Baseline c77177c.

## Verified authority and reconciliation

Server-side Agent Tasks reads verified:
- Original request: $mz7PZUjsyHxrwVEEvXQHObrfb1j8JXvTNqBZeYHZsDg.
- Desktop proposal: $JfRTGHQAcB6S8iz4heg2Yq1acbUs5XqcI1AoNzETGyc.
- Laptop proposal: $HVsH1pHUjjK__fWydu9POAB1p1msSZ3gZTeAEKP-otE.
- Rad's authenticated approval: $Q-2_qM8I8kkWJ3xPuKb34udvdXOmpzM0hi0W-fzOKVk,
  @rad:hearth.radekal.me, 2026-11-12T21:28:03.740Z. Build approval only;
  no activation, paid run, merge, deploy or production workload contact.
- Queued task spec: $kbwtqpY3zgUQiASqleSYHZZkYgcYy3JfXmr_K6mF2ig explicitly
  requires a concrete reconciled [PLAN], then Rad [APPROVED] before implementation.
  Running the named task carries out that sequence; original approval is retained,
  not silently applied to an unseen reconciled design.

Use the laptop proposal for cadence, scope and user control. The desktop plan's
RSLABINSKI-PC name is the verified Lenovo laptop, not a second executor. Only one
Windows dispatcher exists; WSL staging is not another scheduler. A private WSL
checkout alone is NOT an isolation boundary. All untrusted build/test commands
run in a separate credential-free, network-none trial container.

Verified locally, read-only: COMPUTERNAME RSLABINSKI-PC; Lenovo21HM000SUS/x64;
Windows timezone Eastern Standard Time. Ubuntu-24.04, Ubuntu and docker-desktop
WSL2 distributions are stopped. Native authoring checkout is
C:/Users/rslabinski/Projects/hearth2-transfer. No exact
Hearth-Codex-Offline-Relay scheduled task exists. Existing Campfire, notifiers,
heartbeat and other task definitions were not changed. Existing native Codex,
Node and Python paths were inventoried without opening auth material.

## Deliverable and boundaries

Prepare a disabled Windows Scheduled Task Hearth-Codex-Offline-Relay for this
host/user. After a separately approved enablement, check hourly07:00–23:00
America/New_York while the laptop is awake and this user is logged in; do not wake it or replay missed
hours. No model inference or room post for an empty poll. At most one active
session, at most one attempt per approved review generation, maximum600seconds
for a relay session with a separately enforced outside cutoff. That is a proposed
relay budget, not activation or alteration of the inactive900-second Hearth v2
full-run policy. Existing native-turn ceilings stay unchanged.

The trusted controller may read the existing thread/inbox and publish ONLY to
room !0SCHqdoKZOs53xq1DH4zTL0SLz4aKiD16y7Wo7xnIG0,
thread $f13r0i8hHq1yC_HB9hLoVyLJuSp_-6PUGiGFPrzIV7I. This narrow existing
Hearth coordination exception does not grant production workload access.
No other chats/rooms, deploy interfaces, merge/main/tag writes, purchases,
provider trial probes, account changes or dependency downloads. Credentials stay
outside untrusted work. Frozen credential-inventory work remains excluded.

Scheduler starts disabled atomically at registration, with no start/enable flag.
Installation/enablement are distinct: source and isolation/pause checks first,
then disabled registration/readback as part of acceptance under this plan, then
Claude exact-commit review of the combined evidence;
actual enablement still requires Rad's separate explicit approval. If registration
or pause prerequisites cannot be proved, deliver artifacts and mark not installed.
No need to disturb existing scheduled jobs to deliver this task.

## Files and responsibilities (proposed, not created)

- ops/hearth2/offline_relay.py: stdlib deterministic controller/CLI; fixed host,
  target thread and scope admission; no arbitrary command/URL/model arguments.
- ops/hearth2/offline_relay_state.py: private local SQLite transactions, aliases,
  review generations, claims, pause epoch, process/container identities and receipts.
- ops/hearth2/offline_relay_ports.py: separately bounded host transport/launcher,
  trial-only container port and included-allowance verifier. Unsupported launch or
  accounting adapters refuse by default; no mock-as-live success.
- ops/hearth2/install-offline-relay.ps1: stage files and a DISABLED task definition;
  verify owner, path, disabled state and existing-job preservation. No auto start.
- ops/hearth2/pause-offline-relay.ps1: separate out-of-band pause/stop action.
- test/test_offline_relay_*.py and test/fixtures/offline_relay/: routing/state/
  recovery/admission tests and credential-free process/container acceptance.
- docs/hearth2/OFFLINE-RELAY.md and evidence/offline-relay-2026-11-12.json:
  operator contract, one-step pause, exact source/evidence and explicit unknowns.

State lives in %LOCALAPPDATA%/Hearth/OfflineRelay, never the synced G: workspace.
Private controller ACLs and immutable checked configuration are acceptance gates.
WSL staging uses verified Ubuntu-24.04 Linux filesystem; no agent shell or test
gets Windows drive mounts, home directories, SSH/auth files, Docker socket, host
network or deployment tools. Native/WSL unattended support is not yet verified;
no fallback to a broad host shell if the controlled launcher is unavailable.

## Implementation tasks and verification

1. Admission and routing, RED then GREEN. Pin host/scope/thread/generation and
   authenticated Rad approval event; Claude/repository/room content is evidence,
   never new authority. Reject wrong sender, thread, stale/widened scope or changed
   base commit. Deduplicate task ID and relay alias to the same work key. Tests
   assert zero cross-thread sends and no inference/post on idle or ignored events.
2. Crash-safe state, RED then GREEN. BEGIN IMMEDIATE reservation keyed by approved
   work identity+review generation; CAS/unique constraints admit one owner. Persist
   exact base, scope digest and dispatch intent BEFORE any launch. Crash/partial
   receipt/unknown exit -> held, no replay/reclaim by timeout alone. Concurrent
   polling, lost response, before/after-launch crashes and outbox recovery tests
   prove one attempt. A lost post receipt is reconciled, not blindly reposted.
3. Isolation and process lifetime, RED then GREEN. Trusted host credentials are
   used only by fixed transport/coordination ports. Test/work payload runs UID1000,
   read-only image, dropped capabilities, no-new-privileges, bounded resources,
   no network and only a fresh per-run workspace on the TRIAL VPS srv2065995.
   Benign probes prove no host/auth mounts, denied egress, constrained paths and
   timeout/descendant cleanup. No production connection or shell from worker.
4. Seat refusal and accounting, RED then GREEN. No real worker launch unless a
   fresh authoritative INCLUDED-only allowance/route check is machine-verifiable.
   Missing/stale/unsupported/ambiguous data, exhausted allowance or any paid/API/
   credit fallback refuses before launch; no interactive login or top-up attempt.
   Use synthetic positive/negative verifier fixtures for acceptance, clearly
   labelled. Actual account/financial enforcement remains unknown until separately
   verified; a screenshot or remaining-quota value alone proves no monetary ceiling.
5. Pause acceptance, RED then GREEN. Publish one desktop action named exactly
   “Pause Hearth relay”. It first persists paused+new epoch (blocking claims),
   then disables only this task and stops registered local/WSL/trial workloads
   by verified identities. A separate process performs pause so a killed dispatcher
   cannot skip it. Confirm whole workload empty; uncertainty -> paused_pending_stop,
   never resume/reclaim. Test pause/claim races, active descendants, unavailable
   scheduler, repeated pause and dispatcher crash. No model call is used to pause.
6. Evidence/review, before any enablement. Run focused tests, Windows/WSL capability
   checks and actual credential-free trial acceptance using cached dependencies.
   Report source/module hashes, actual exit codes and root-observed cleanup; fixture
   inference is not a live Codex seat session. Keep source on a codex/ feature branch,
   submit exact diff and evidence to Claude ONLY in the existing thread. Tests and
   review never turn on the task. Unsupported capabilities remain blockers.

## Acceptance matrix

| Requirement | Required check | Failure state |
| --- | --- | --- |
| Routing | wrong room/thread/sender/generation -> no claim, no external send | refused |
| Deduplication | concurrent aliases and crash/restart -> one attempt, uncertain held | held |
| Isolation | actual credential-free sandbox probes, not configuration-only assertions | blocked |
| Included-only refusal | missing/exhausted/stale/untrusted evidence -> zero model launches and no fallback | blocked |
| Pause | race+active descendants -> paused, no new claims; outside observer proves stopped | paused_pending_stop if uncertain |
| Disabled install | exact task exists disabled, never ran; unrelated jobs preserved | not installed/blocked |
| Usage | each executed-session STATUS includes measured units+provenance or explicit unavailable | unavailable never zero |

## Reporting and open gates

Every executed relay gets one STATUS (two plain outcome/next-action sentences
first), then work/generation/base/result commit, evidence, waiting party and
per-session seat usage. For the first seven days AFTER enablement, this is
mandatory; do not start/restart that window during preparation. Token usage is
not a subscription bill. Missing usage is explicitly unavailable, not0 or free.
The current manual planning invocation has no attributable per-session accounting;
it has launched zero worker sessions. No numerical seat/cost estimate is asserted.
Actionable required-human failures get one BLOCKED here; no model retry, idle
heartbeat or extra relay/task created from that blocker.

Official OpenAI documentation describes codex exec as noninteractive and describes
JSON event usage, but does not verify this host's unattended support, an included-
only financial boundary or isolation. See https://learn.chatgpt.com/docs/non-interactive-mode
(accessed12Nov2026). Do not copy auth.json into work or public CI, expose API-key
fallback, or infer that documented CLI flags alone establish enforcement.

Open gates before real unattended operation: exact local launcher/WSL capability,
protected controller-to-sandbox boundary, reliable included-only allowance/route
verification, concrete process cutoff and pause proof, Claude exact-commit review,
then Rad's enablement decision. Build acceptance may prove safe refusal while
these are unavailable; it must not be reported as a working autonomous loop.

Approval requested now: disabled BUILD and credential-free acceptance of this
reconciled plan only. No registration is performed until the ordering above;
activation, paid runs, merge/deploy and production workload contact stay excluded.
