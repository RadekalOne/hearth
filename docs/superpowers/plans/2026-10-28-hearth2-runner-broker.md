# Hearth 2 runner and broker implementation plan

> **For agentic workers:** Use superpowers:executing-plans, with test-first implementation and one final fresh-context review.

**Goal:** Execute the approved piece-2 handoff on the isolated trial instance.

**Architecture:** A trusted controller owns the work record, broker, native-runtime connection and containment evidence. Workers receive only one ephemeral read-only memory capability, scoped to their current claim and selected memory wing/room. Every broker request is checked against the authoritative claim before reading upstream and again before releasing a response. Runtime activation remains disabled until account, tool enforcement and independent containment checks pass.

**Tech stack:** Existing Python/SQLite/FastAPI service and direct native CLI adapters under the approved fallback. Pinned Cloudroom 0.1.58 remains installed and unchanged. No production change or model substitution.

**Spec:** Approved piece-2 HC handoff, six-item VERIFY, `docs/hearth2/PIECE-1-SPEC.md`, `PREFLIGHT.md` and `RUNNER-RECORD-INTERFACES.md`. PR35 is merged at `6b6987b42a8560c78f9c367560ea604d8e407ca3`; its tree matches the passed `21cf340`.

## Boundaries and rulings

- Preserve native account settings, pinned runtime, approved rules 1.0, one active workload, the three-launch cap and the two-hour ceiling.
- Do not treat connected accounts, model catalog entries or receipts as billing, execution or containment PASS.
- Ruling: use an in-memory capability registry, so broker restart revokes all grants automatically; store only hashes of bearer capabilities. No mint/admin HTTP route. Trusted controller supplies scope; worker input cannot broaden it. Cost if wrong: controller must mint a fresh grant after broker restart or lease renewal.
- Ruling: broker allows only `memory_search` and `memory_get`, within a required wing and room. Root-only upstream callback owns credentials; no general memory URL/token is sent to workers. Cost if wrong: planners must provide relevant scoped knowledge rather than relying on unrelated wings.
- Runtime spike: pinned Codex adapter requests danger-full-access; Claude skips permissions and exposes managed delegation. An outer request containing a tool list does not itself enforce that list. Resolve actual enforcement before native prompts, without silently replacing the pinned runtime.
- Billing settings review completed by Rad on 29 October: both premium seats; retain Claude $75/month extra-usage limit; ChatGPT zero workspace credits and auto-reload off. Technical native acceptance gates remain.
- 30 October continuation: durable dispatch registration implements the single instance slot, one-use launch transition and persisted workload identity over the existing audit journal (`DISPATCH-REGISTRY.md`). It does not execute processes or establish host-wide containment. Controller task remains partial. Native seat-credential residual risk is accepted; no repeated consent or gateway requirement is introduced.
- Later 30 October: native policy/argument boundary, account-guard validation, preflight coordinator and atomic claim/reserve + receipt/release are implemented as inactive components. Installed-client policy fixture passes without user turns or real credentials. See `NATIVE-PREFLIGHT.md`; actual collectors, root launch/projection, tool-call/egress/containment proofs and scheduling remain to build. Ruling: native observations expire after 60 seconds; current-month Claude admin review retains the accepted trade and is not reclassified as a per-run allowance. No new approval or activation implied.

- Fallback ruling (30 October): installed Claude rejects the pinned core's required bootstrap request with both hardened and original arguments. Short declared-version check found no established compatible version. Under Rad's 15 October explicit fallback, reviewed with Claude, Hearth will launch BOTH native CLIs directly. Preserve all account/model/receipt/containment controls; remove core Command Guard/transcript coupling from this path. No new purchase, account or pin change. Direct adapters and their acceptance remain unimplemented. Independent systemd/Docker deadline fixture now passes after the submitter exits; not yet absolute claim-deadline or native acceptance.

- 31 October continuation: bounded native stdout reducers and atomic native-result settlement are implemented as inactive components (`DIRECT-NATIVE-OUTPUT.md`). Unknown output preserves known exit but holds; native auth/quota stops atomically pause the role without automatic reactivation. Installed Claude fake401/429 controls exposed ten-retry behavior; adapter stops the first typed retry after one local fake request. No real credentials/inference/provider connection. Ruling: native state, actual exit and OS emptiness are separate authority dimensions; retain all activation gates. Older controller binaries do not enforce new native metadata: pin matched code and verify pre-change-backup rollback before activation.

- Further 31 October: direct native profile builders and actual broker compatibility fixtures implemented (`DIRECT-NATIVE-PROFILES.md`). Native MCP progress metadata is transport-only. Conditional ruling: an explicitly full-run initial lease/grant may avoid mid-run bearer renewal only after absolute deadline/delayed-start/restart proof; current defaults are unchanged. Native expiry checks do not substitute for authoritative late-exit settlement. Actual auth/quota stops consume launches; no attempt refunds.

- Absolute-deadline primitive (31 October): PID1 sealed UTC timer before start, kernel quiescence before Docker, immutable-ID removal, delayed/never-started/daemon-failure controls and error cleanup verified (`ABSOLUTE-DEADLINE-TRIAL.md`). This is not DB-bound launcher/restart acceptance. Keep full-run lease policy inactive until composition.

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

## Current continuation: trusted late OS observation

- Add a controller-only DispatchRegistry observation path, distinct from native
  worker closeout. Require the exact durable registration, fresh current restore
  epoch, current run/claim/generation/owner, and bounded fresh OS evidence.
- Preserve actual known exit and prior end/closeout/usage/role history. Missing
  protocol remains unknown; an OS observation cannot assert task success, accept
  a late closeout, resume a role, consume another attempt or release a slot.
- Hold active/held work after observation. Exact logical observation retries are
  idempotent, conflicting IDs/proofs refused. Restore requires a NEW current-epoch
  observation, never stale pre-restore proof. Current generic reconciliation and
  closed/quarantined slot recovery remain separate integration work.
- Tests first: expired ordinary receipt refusal, actual late exit retention,
  unknown exit, freshness/identity/epoch/generation/authority negatives, replay,
  export/restore preservation and no successful promotion. Single fresh review
  and full appropriate checks before commit. No HTTP worker authority is added.

Production root-guard follow-up must include Claude's c689 notes: derive durable
guard identity from run+epoch, never disarm before verified emptiness/removal,
and attempt kernel kill again on post-kill failure while retaining frozen parent
until immutable-ID removal is independently proved. Current standalone fixture
UUID collision is intentionally not a controller-restart proof.

## Current continuation: atomic recovery with removal proof

Ruling: implement a root-only in-process RecoveryCoordinator over existing
SQLite transactions. It accepts fresh exact-context OS proof PLUS separately
matching immutable-container absence proof and classification references. Empty
cgroup alone cannot release a launch slot. No HTTP route, OS collector or native
activation is added. Cost if wrong: conservative refusal/held slot, never infer
a successful task or retry authority from an uncertain process.

- Active/held recovery records trusted OS evidence, explicitly classifies failed
  or completed using existing rules, and releases atomically; unknown exit stays
  held. No late worker closeout/usage is accepted.
- Closed pre-restore unresolved slots get a fresh current-epoch OS/removal audit
  and release while preserving task/run history; classification must be preserve.
- Exact replay is read-only and current-epoch fenced. Wrong owner/context, stale
  proof, container mismatch, missing absence, missing classification, journal
  failure and restore-old proof refuse without partial state changes.
- Ordinary legacy reconciliation remains available to old unregistered paths;
  actual native launcher must use the strict composed coordinator. No claim that
  trusted root database access itself is constrained by these APIs.

## Current continuation: immutable original-host creation binding

Implement the next offline controller boundary (`CREATION-BINDING.md`): seal a
reserved live registration to original host, immutable container, deterministic
run/original-epoch guard and parent, policy and fixed deadline in the existing
journal. Refuse replacement on restart/restore. Require the original host and
container in bound OS observations and both strict recovery proofs. A fresh exact
armed-guard/stopped-container attestation and one-use dispatch consumption commit
atomically; ordinary public consume cannot bypass this for bound runs. All OS
operations and actual native activation remain separate gates. No disarm is
introduced;900s defaults/full-run policy remain unchanged/inactive. Tests first,
one fresh final review, then appropriate full regression; preserve private ledger.

## Current continuation: one-use root launch composition

Before any external create, commit a one-use original-host creation intent.
Compose the inactive injectable root driver through stopped create/independent
inspect/bind/arm/independent inspect/atomic guarded consume/final live fence/start
of only the sealed immutable ID (`LAUNCH-COMPOSITION.md`). Crash/lost-ack replay
never creates/adopts/rearms/starts again; no cleanup/disarm fallback. Capture
current recovery fencing before independent proof collection and call only the
strict bound RecoveryCoordinator. Test all partial boundaries and a real process
race offline. Concrete OS/driver/old-backup/orphan-intent inventory acceptance
remains an activation gate; no full-run lease/default change. One final fresh
review and full appropriate regression before local commit.

## Current continuation: kernel guard and independent disarm

Implement root-only termination with exact original binding, kernel freeze/kill
before daemon calls and repeated kernel kill on post-kill failures/interruption.
Retain frozen parent and never disarm in the guard. A separate outside observer
must freshly read empty/frozen parent AND successful exact immutable-ID absence
before disarm. Add directory-fenced real cgroup-file operations tested ONLY on
private regular files and synthetic daemon inventory (`ROOT-KERNEL-GUARD.md`).
Actual daemon/host-authentication/arming/start driver, OS and reboot/old-backup
acceptance remain open; no service activation or lease/default change. TDD,
one fresh final review and full offline verification before local commit.

## Current continuation: bounded fixed daemon command port

Implement POSIX bounded subprocess transport with stripped environment, no shell,
bounded combined output/time and own-helper process-group cleanup before reaping.
Add exact-ID Docker inspection/removal/inventory using a selected credential-free
projection and guard-only systemctl stop/confirmation (`ROOT-COMMAND-PORT.md`).
Tests execute ONLY private fake helpers/daemons; no service activation. Actual
CLI/version/timer/deadline/host/layout support and durable root guard receipts
remain subsequent acceptance layers. TDD, one final fresh review, full offline
verification and local commit;900s/full-run policy unchanged/inactive.

## Current continuation: durable root guard evidence

Before immutable-ID removal, durably publish a credential-free original-binding/
actual-exit observation outside the restorable DB. After independent local
removal/empty queries, durably publish the second observation before success.
Use immutable content-addressed private files, file/directory fsync, no-replace
publication, bounded history and nonblocking writer/read fencing; refuse corrupt
or conflicting facts (`GUARD-EVIDENCE.md`). Missing/failed evidence still permits
kernel stop but never removal/positive guard return. Historical receipts never
substitute for fresh independent original-host proof or strict DB recovery. TDD,
one final fresh review/full offline suite/local commit, no actual OS activation.

## Current continuation: outside termination collector

Combine original-binding durable known-exit facts with NEW original-host empty/
frozen and immutable-ID-absence queries, under the launcher's pre-inspection
current epoch/generation snapshot and strict RecoveryCoordinator. Historical
receipts never become fresh OS proof or automatic result classification. Bound
collection time with query-begin stamps, wall ordering and monotonic duration;
refuse unknown/conflicting/foreign/stale data (`TERMINATION-COLLECTOR.md`). TDD,
one final fresh review/full offline verification/local commit; actual host/OS/
observer/native acceptance gates remain open and900s/full-run policy inactive.

## Current continuation: original timer-only readback

Use upstream-verified typed systemd D-Bus contracts, not human timestamp parsing.
Bounded local GetUnit/property-only reads verify the exact original future UTC
calendar/deadline, transient waiting timer/inactive linked service, invocation
identity and twice-stable snapshots (`TIMER-READBACK.md`). Refuse extra triggers,
delay, alias, changed identity/time/host and malformed types. The timer-only result
must NOT substitute for full guarded container/policy attestation or authorize
start. Actual CLI/version/service/host/layout/OS acceptance stays open. TDD,
one final fresh review/full offline suite/local commit,900s/full-run inactive.

# Offline root layout continuation (1 November 2026)

Implement immutable original-host layout policy and mapped cgroup boundary as
specified in `docs/hearth2/ROOT-LAYOUT.md`. Keep the original logical parent and
creation epoch; select layout before creation, pin it with `policy_sha256`, and
refuse restore-host remapping. Tests use private files/injected ports only.
Actual root authentication, service executable/UID/policy and stopped-container
resource readback, then concrete create/arm/start composition remain required
before any activation. Full-run/default900s policy remains inactive.

## Offline service-only readback continuation

Read original guard/native artifacts pinned by layout and bounded typed service
configuration (`GUARD-SERVICE-READBACK.md`). Exact sealed binding argv, explicit
numeric root settings, unused transient inactive unit and no alternate lifecycle
commands; stable twice-read artifacts/properties/current original host/deadline.
Service-only evidence never authorizes consumption/start. Actual runtime UID,
namespace/dependency closure/native policy application/container/OS gates remain.
TDD, one fresh final review/single fix pass/full offline suite; no activation.

## Offline stopped-container configuration continuation

Validate original-layout-pinned memory-only native container policy and selected
stopped immutable-ID/resource/security configuration (`STOPPED-CONTAINER-READBACK.md`).
Narrow network-none/no-extra-mounts version1 only; explicit future assembly policy
needed for mounted profiles/broker egress. Read twice under originalhost/deadline
and immutable context. Partial config evidence cannot satisfy full created/armed
proof. Actual native application/OS/driver acceptance stays gated; TDD/fresh review/
full offline suite/local commit, default900s/full-run inactive/no activation.

## Offline sealed root guard ABI continuation

Implement root execution seals/callable guard entrypoint (`GUARD-ENTRYPOINT.md`):
canonical exact binding, embedded original layout/evidence path, durable immutable
private no-replace seal before arming, UID/originalhost enforcement, no early
execution, existing kernel-first termination at originaldeadline. DefaultCLI has
no runtime; no installedwrapper or activation. Policyrepo loss after sealing must
not prevent termination. Rootdriver/hostauth/OS/nativeassembly acceptance remains
open; no partialproof promotion. TDD/fresh review/full suite/local commit only.

## Offline concrete root lifecycle continuation

Implement fixed create/absolute-arm/immutable-ID-start ports plus RootLifecycleDriver
and durable one-use root attempts/created-ID receipts (`ROOT-LIFECYCLE.md`). Require
explicit independently verified assembly/bootstrap/root/namespace/credential/mount/
egress contract; missing observer refuses before mutation. Root execution seal
before arming; strict service literal-JSON flag, timer/config/assembly reinspection
before consumption/start. Never turn partial receipts into full authority alone.
Default driver unconfigured/no OS activation; actual installed collector/wrapper/
native/OS/orphan/restore acceptance remains open. TDD/freshreview/full offline gate.

## Offline independent assembly collector continuation

Implement RootAssemblyCollector/immutable independent root enrollment and bounded
Docker metadata comparison ports (`ASSEMBLY-COLLECTOR.md`). Require separate fresh
image/container file-stat-digest and root-runtime/installation facts; never turn
caller states or hashes alone into physical attestation. No default enrollment/
file/runtime backend or driver wiring. Two copied stable rounds under original
host/boot/namespaces/context/deadline. Actual file/runtime/backend provenance,
CLI/OS/native acceptance remains gated. TDD/freshreview/full isolated suite only.

## Offline selected-file archive measurement continuation

Implement bounded non-extracting selected-file USTAR measurement port
(`FILE-MEASUREMENTS.md`) with exact immutable source linkage, independently
acquired no-follow ancestor measurements and fresh time/provenance checks.
Refuse links/extensions/traversal/extra members/unsupported archive formats.
No default authenticated source, layer resolver or driver wiring. This component
does not establish physical source provenance or complete credential inventory.
Private archive fixtures, TDD, one final fresh review and full isolated suite.

## Offline enrolled rootfs file producer continuation

Implement `RootfsFileMeasurements` (`ROOTFS-SOURCE.md`) using independently enrolled
original image/CID/rootfs identity, a fixed isolated bounded stdlib helper and
real descriptor-relative no-follow measurement. Require actual original
root/boot/namespaces, read-only same-mount view, pinned root inode and stable
regular-file facts. Default enrollment empty; no mounts/enrollment/driver wiring.
Use direct digest output within existing transport budgets, not file contents.
Private filesystem fixtures with explicitly injected root/mount facts only.
Complete credential inventory/runtime provenance/OS/native gates remain open.

## Offline credential audit policy contract continuation

Implement immutable `CredentialAuditRequirements`
(`CREDENTIAL-AUDIT-REQUIREMENTS.md`): original image/assembly, independently audited
complete-rootfs/consumer manifests, parser closure, authority reference and strict
budgets. Fixed required coverage families before/after creation, no exclusions.
Requirements only, not a scanner or inventory receipt. Complete physical producer,
audited consumers/provenance and driver wiring remain absent. TDD/private artifacts,
one final fresh review/full offline suite; stop new work at the existing cutoff.
