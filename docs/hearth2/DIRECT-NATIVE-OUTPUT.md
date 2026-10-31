# Direct native output and authoritative settlement

Status: inactive controller libraries and credential-free trial fixtures. This
connects decoded native stdout to the work record; it does not launch production
agents, configure credentials/MCP/egress or establish full piece-2 acceptance.

## Input boundary

`native_output.NativeStream` is the controller entry point for stdout bytes.
It limits records to 1MB, a stream to16MB/10,000 records and nesting to32 levels.
It accepts split UTF-8 and a final JSON record without a newline, rejects duplicate
keys, nonfinite numbers, invalid Unicode and non-object records, and poisons the
result after malformed/truncated output. A prior completed message cannot survive
that failure. Errors use fixed diagnostics rather than copying native secrets.

Codex reduction targets the installed0.154.0 generated app-server schema, retained
privately at `/root/hearth-runner-trial/native-schema-wbkpgxym/v2`. Thread and turn
IDs must come from validated controller start responses. Only matching root
notifications can supply text, usage or typed `usageLimitExceeded` stops. Interim
commentary is excluded; duplicate cumulative usage is not added twice. Contradictory
or conflicting terminal data cannot become a successful result.

Claude reduction targets one root prompt in a fresh, non-resumed session. Foreign
sessions and child results cannot complete the task. A typed rejected primary
`rate_limit_event` requests a pause; `overageStatus=rejected` alone does not.
Typed401/403 native retry notifications request authentication stop; typed429
requests rate-limit stop. This does not assert that every429 means included-seat
exhaustion. Budget stops also prohibit automatic retry. Missing/native-invalid
output is unknown. None of these data states proves a process exit or empty OS
workload. Stop flags require a trusted launcher to kill/reconcile and persist them.

Token totals remain native reports. Claude `modelUsage` totals are preferred to
main-loop counts; fallback main-loop counts are explicitly labelled partial when
cache counters are absent. Missing counters stay absent. CLI `total_cost_usd` is
an estimate, never an actual premium-seat charge. Missing usage stays unknown.

Primary references (installed-version schema/observations take precedence over
newer documentation):

- https://learn.chatgpt.com/docs/app-server
- https://code.claude.com/docs/en/headless
- https://code.claude.com/docs/en/agent-sdk/typescript

## Settlement

`DispatchRegistry.record_native_result` requires the consumed registered claim,
provider matching the recorded role family, sanitized native result, observed
end/exit and independent termination evidence. It parses a completed textual
closeout through the same 1MB/depth32/duplicate-key/finite/Unicode bounds as the
outer protocol (a JSON string can otherwise hide deeply nested JSON); invalid/prose/credential-like closeouts are not persisted
as valid results. Native estimates cannot be labelled actual charges. It uses the
existing atomic receipt/release path, including exact sanitized-receipt replay.

Native state, optional stop reason and usage scope are stored in `runs.data`.
No SQL DDL or bundle format change. Legacy receipts retain their prior semantics.
An unknown native result holds the task/claim while preserving the actual known
exit and containment observations; it does not falsify exit as unknown just to
obtain a hold. A stopped role is paused, with a revision and immutable reason/run
audit, in the same receipt transaction. If actual exit and empty containment are
known, the stopped attempt closes and releases the instance slot; that paused
role cannot consume another attempt. Another eligible role can run. Unknown exit
or containment keeps the slot held. Unknown output after a stop keeps both task
and role held. Human confirmation through the existing role operation is required
to reactivate a paused role; this code never does that automatically.

Reconciliation and bundle validation both respect native-state metadata. A
success-looking body cannot promote unknown native output to completed, including
when a bundle digest is recomputed. Failed reconciliation with fresh termination
proof remains the conservative recovery path. This changes controller semantics:
an older binary does not enforce the new metadata. Before activation, pin the
matching controller/restore code; a rollback must stop the controller and use a
verified pre-change backup, rather than assuming a binary-only downgrade is safe.

## Installed-client fake API observation

`test/fixtures/hearth2_claude_error_probe.py` requires root, exact trial host
srv2065995 and explicit opt-in. A disposable network-none/UID1000/cap-drop/read-only
container holds only the public Claude2.1.280 executable, managed policy, this
source and private bounded scratch. It has no real provider or memory login.
It sends a synthetic CLI prompt to a fake loopback-only HTTP server, using an
obviously fake API key. This is not a subscription route or real model request.

Initial controls without adapter intervention produced5/6 local requests and
native `system/api_retry` messages with max_retries10 before a20s fixture timeout,
for429 and401 respectively. No final result or typed subscription rate event was
observed. Private diagnostics: claude-error-l84nstew and claude-error-b_xf2d4p.
The401 control intentionally failed its expected-terminal assertion; it exposed
the native retry behavior and is not claimed as passing evidence.

With `NativeStream`, each first typed retry causes a fixture stop. Both401 and429
checks observe exactlyONE local HTTP request, known client exit-9, no timeout and
verified own-container removal. Private receipts: claude-error-eqf1oiej and
claude-error-1oqsm94r. Real-provider connection, inference and credentials are
absent. Typed subscription `rate_limit_event(status=rejected)` is SDK-contract
tested only; actual native subscription-exhaustion mapping remains unverified.
Do not infer real-seat quota, allowed-destination egress or full containment PASS.

## Remaining activation gates

Still required: exact-model/account validation and per-run clean credential and
settings projection; direct Hearth MCP configuration and scoped broker route;
fixed provider/broker egress and actual forbidden-tool tests; one host workload,
absolute claim deadline/lease/revocation handling and outside empty proof; root
controller scheduling, restart reconciliation and alarms; composed native tests.
Each actual launch, including an auth/quota stop, consumes one of the approved
THREE attempts. There is no refund: doing so could authorize more native launches
than Rad approved. The incident and native stop reason preserve the distinction
between an infrastructure stop and failed project work. Three such stops can
exhaust the launch cap; further action then requires a human decision.

A first native429 deliberately pauses even if it was transient. `rate_limit_stop`
means observed HTTP429, not proven included-allowance exhaustion. The launcher
must catch RecordError from BOTH feed and finish, stop the workload and verify
containment, then obtain outcome() and settle it. Poison still preserves a typed
stop and requires the atomic role pause; exceptions must not bypass teardown.

A native completed message alone is never a Hearth success receipt. Current
libraries are not an installed runner or a substitute for those gates.

## Review corrections

Independent component review reproduced two important defects before activation:
coalesced malformed/oversized tails could discard an earlier stop, and a nested
closeout string could crash settlement outside the outer JSON depth guard. Both
were reproduced RED and fixed in one pass. NativeStream now dispatches valid
prefix records incrementally, retaining stop reason while poisoning success;
partition tests cover both providers at every byte boundary. Closeout text uses
the shared bounded object decoder. A malformed status array exposed an older
closeout-validator type error; it now returns invalid rather than crashing.
Known exit/empty evidence is persisted even when closeout parsing fails.
