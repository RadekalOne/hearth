# Native thread-launch adapter — 10 November 2026

Implemented and exercised as a root-side, credential-free, network-none thread
adapter. This closes the two audit conditions from Claude's guard PASS
`drawer_8d3ca359b7f0b2504d8bd5a05f294ea5` at this native thread boundary.
It is not a composed live runner or full OS lifecycle acceptance. No provider
turn, account entitlement check, service activation or production change.

## Concrete integration and authority

`NativeRpcClient` owns the real serial stdio exchange with an already isolated,
root-selected app-server: initialize, full model/list, and thread/start only.
There is no turn/start API or process factory. It generates session/request IDs,
bounds frames, total output, notifications, pipe I/O and lock acquisition, and
rejects duplicate fields, malformed/nonfinite/deep JSON, wrong IDs and ambiguous
replies. Canonical reply bytes are immutable; each result read returns a copy.
Actual model/list error replies retain their hash, RPC/session identity and root
receipt time without returning untrusted error text in the audit.

`CodexThreadLauncher` consumes one attempt before any RPC. It acquires model/list
through that live port rather than accepting a caller's cached dictionary. Every
decision records canonical response SHA256, RPC ID, RPC session, root receipt
timestamp, monotonic age and root decision time. A missing/error response is
explicitly unavailable/error, never a fabricated successful catalog.

The strict five-field model/request guard remains mandatory. Unexpected errors
inside its request/catalog check become recorded guard_error refusals, where the
audit is available. Audit/storage failures still abort before transport; a full
or corrupt journal cannot guarantee another row and never authorizes a thread.
Transport/setup errors remain distinct from model selection and from future
provider turn/entitlement failures. No substitution or automatic retry.

Immediately before thread dispatch, the adapter invokes a required trusted
authority fence and rechecks model-list age (at most60s, no future monotonic
stamp). These checks execute INSIDE the RPC serialization lock, before assigning
or writing the thread request. A queued concurrent request cannot bypass them.
Native profile mismatch refuses before any turn. The root driver must supply
the real claim/lease/epoch/deadline fence; the fixture used container-identity
fencing only. RPC I/O and mutex waits are bounded; trusted fence callbacks and
uninterruptible kernel/filesystem operations are not bounded by this adapter.

`RootModelDecisionJournal` is a concrete root-only append-only JSONL sink outside
candidate mounts. It requires an absolute non-symlink private0700 directory and
root-owned0600 regular single-link file; uses nonblocking locks, bounded reads/
rows/capacity, canonical sequential rows, file/directory fsync before ack.
Corrupt tails, unsafe ownership or capacity refuse; there is no auto-repair.
These are operational audit records, not human approval/decision-card rows.

## Existing OS lifecycle contract preserved

RootLifecycleDriver v1 forbids extra mounts and interactive attachment. The
candidate fixture deliberately uses an isolated bind-mounted client and stdio,
so it cannot be represented as v1 OS lifecycle acceptance. That policy was not
loosened. The remaining root driver/policy/assembly observer/bootstrap integration,
real claim fence, independent deadline, restart/orphan handling and live task
record composition remain open. This adapter selects no container, daemon route,
account, credential, service or executable and grants no launch authority alone.

## Verification

- Trial Python3.12: initial32 cases RED for missing components/guard-error audit;
  subsequent aware-clock/error-identity and peer-review findings reproduced RED.
  Final **38 tests PASS, actual exit0,0.651s** on exact staged source. Covers
  real-pipe RPC behavior/timeouts/IDs/bounds, immutable replies, metadata hashes/
  timestamps, stale/queued authority changes, single-use, audit safety/failure,
  guard_error rows and separate setup errors. No broad full-suite claim.
- One fresh-context read-only review found two P2 issues: checks before a mutex
  wait, and dropped error-response evidence. Both were fixed with four failing
  regressions turned green plus a real-pipe remote-error test. No second review
  or new independent Claude PASS is claimed.
- Actual0.159.1 fixture `codex-01591-ca4eff1b5ee14989856d65ef357c8f6e` on
  `srv2065995` completed09:40:42 Eastern10November. Real stdio port and all four
  package modules ran on the root host, outside the UID1000 candidate namespace.
- Unknown model, request override and injected checker exception each produced
  a root-private fsynced decision, with actual model/list RPC IDs3/4/5, hashes,
  session and receipt stamps; zero thread starts for those controls. Exception
  text did not enter the audit. Positive model/list RPC6 was recorded before
  exactly one same-model idle thread at RPC7. Replay of that attempt refused
  without another RPC. No turn was sent.
- Final fence observed persisted audit_seq4 while the last RPC was model/list6;
  it checked the fixture container ID/label/namespace state inside dispatch.
  This is not a real task claim/lease fence.
- Root observer independently verified stopped/Pid0, removed cgroup and exact
  container removal; home quarantined. Subsequent inventory found no candidate
  containers or unquarantined homes. All309 scoped baseline file paths,
  resolutions and hashes were unchanged within the recorded coverage.

The first native run hit a harness variable-name collision after the container
stop/removal checks, before quarantine/final receipt. It did not produce a final
receipt. Preserved its controller, root audit and RPC trace. A separate root
recovery check confirmed Docker die/destroy events, container and cgroup absence,
then quarantined its home. Fixed the harness name and reran for the complete
receipt above. Both histories remain; no failed run is relabelled PASS.

Remote evidence directory:
`/root/hearth-runner-trial/native-thread-launcher-raheblm6` contains exact source/
tests, RED/final logs with exit manifest, root controller/bootstrap, raw RPC
responses, journal, recovery evidence and final receipt.
Final raw receipt SHA256:
`228ace47ee03dd30faf0f679086140e3980b85710df1baf8fd00adc19b1243bc`.
Local summary: `evidence/native-thread-launcher-2026-11-10.json`.

## Still open and gated

Real scoped broker instead of discovery stub, forbidden-tool/expiry/output
settlement, full OS lifecycle/claim composition, bubblewrap PATH or pinned/hashed
bundled helper before any shell enablement (shell_tool remains false), provider
entitlement/runtime and live A-tests. Invalid-model diagnostic hashing and
per-admission binary hashing retain the earlier explicit dispositions.

Catalog/model/request gates and targeted native thread adapter passed; complete
runtime compatibility and real-account execution remain unknown. Service
activation and paid runs require Rad's explicit [APPROVED]. Production and the
frozen credential-inventory track are unchanged. Sources remain uncommitted.
