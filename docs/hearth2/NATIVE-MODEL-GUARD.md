# Exact-model pre-thread guard

Required-change follow-up: Claude's source PASS in
`drawer_a3e6dca5280e24cfd909e21543ad685a` identified arbitrary request fields being
forwarded. The current revision requires exactly five keys with fixed non-model
values: `model=gpt-6.1-sol`, `cwd=/scratch`, `approvalPolicy=never`,
`sandbox=read-only`, `ephemeral=true` (a bool, not integer1). Missing/extra fields
or changed fixed values record `request_fields_not_allowed` before transport;
the model retains its separate exact-model check. This is a fixed candidate
contract, not a configurable provider/workspace gate. Any future request-shape
or workspace expansion requires a reviewed change.

See `NATIVE-MODEL-GUARD-REVIEW-RESPONSE.md` for the16-test regression and native
override controls. The original13-test/native evidence below remains historical.

Status: inactive library plus a credential-free network-none trial fixture.
Claude's boundary requirements: `drawer_ef54ea734ca91b838715dc47a54e8180`.
This addresses the native client's accepted-unknown-model observation in
`CODEX-01591-PREACTIVATION-2026-11-09.md`. It does not change the Codex binary,
activate a service, perform inference or claim complete runtime compatibility.

## Boundary and authority

`native_model_guard.start_codex_thread` is the sole guarded thread-creation entry
point in this candidate fixture. The one allowed model is hardcoded:
`gpt-6.1-sol`. Neither an advertised model nor caller-supplied configuration can
expand that allowlist. The caller must be the trusted root launcher, supplying
the exact mounted binary path/pins, fresh complete client model/list response,
durable-audit callback and thread transport. No worker HTTP route is added.

For that model, the guard reads the regular mounted file without following a
final symlink, bounds its size, checks binary and embedded catalog hashes, and
decodes a bounded catalog. The allowed identity must be present in both that
catalog and the complete client list. Invalid/duplicate identities, ambiguous
IDs, pagination or missing identity refuse. Any other requested model refuses
immediately; it need not reach the client to establish invalidity.

The guard records an allow/refuse decision with a fixed reason and failure class
before transport. A durable audit acknowledgement of exactly True is required;
missing acknowledgement or audit exception causes no thread. Audit callbacks
receive a copy and cannot alter selection. Allowed requests retain their model
and reach transport once. There is no substitution, fallback or automatic retry.
Downstream transport/runtime exceptions propagate unchanged; they are not turned
into a `model_selection` refusal. This guard does not submit turn/start.

The concrete service launcher remains unimplemented. It must enforce immutable
mounts, fresh native metadata and claim/lease/epoch authority separately; passing
a cached response to this library is not fresh launch authorization. The guard
does not replace broker, native output, termination or account policy checks.

## Verification — 9 November, Eastern

13 focused tests first failed with the guard absent, then passed on the trial's
Python3.12 in0.014s. They cover exact-model admission, unsupported/other-advertised
model refusal before transport, absence from either catalog, changed binary and
catalog pins, invalid/duplicate/partial client data, symlink/missing binary,
audit failure, callback mutation and downstream-error propagation without retry.
No broad suite or independent Claude source PASS is claimed.

Native fixture `codex-01591-4370fb9332724dbeb946fe9143cb4117` ran
21:42:31–21:42:51 Eastern (02:42:31–02:42:51UTC10November) on `srv2065995`.
The root host controller loaded the exact library outside the UID1000 candidate
namespace. Its audit file was root-private and absent from candidate mounts;
each decision was flushed/fsynced before any admitted thread request.

- Actual client0.159.1; mounted binary/catalog hashes and exact eleven unique
  model identities verified. Read-only/never-approval managed policy retained.
- The first request used the made-up model. Hearth recorded `model_not_allowed`
  with `failure_class=model_selection`; **zero thread/start calls, zero native
  threads at that point**. It never sent the unknown string to native transport.
- The positive request used `gpt-6.1-sol`. Root independently decoded the binary
  through the live container mount and checked both catalogs. A persisted allow
  preceded exactly one thread/start; the native result retained the exact model
  and effective readOnly/networkAccess=false.
- Native method trace: initialize, model/list, thread/start. **No turn/start**,
  real credentials, real provider call, substitution or retry.
- Root observer confirmed stopped/Pid0, removed cgroup and exact container, then
  quarantined the new home root-only. Subsequent candidate-container inventory
  was empty. All309 recorded baseline paths/resolutions/hashes were unchanged,
  within the coverage listed in the receipt; unknown consumers are not proven.

Remote evidence:
`/root/hearth-runner-trial/codex-01591-model-guard-jh22otnc` contains source/test,
red/green logs, root controller, candidate probe, JSONL decisions and raw receipt.
Local evidence: `evidence/codex-model-guard-2026-11-09.json`.
Guard SHA256: `2634e7fc04660af081bd40c1f90905fd9e53bbf61e307cb007bd0fa903800757`.
Native receipt SHA256:
`444081066e1dae2db2688bfc445e007497a829d040c0e31e3a02de36784b5d28`.

## Still open

Real scoped broker instead of discovery stub; forbidden-tool/expiry/output
settlement checks; concrete live launcher integration; and provider entitlement/
runtime/live A-tests. Startup still reports missing bubblewrap on PATH and a
bundled fallback. Keep shell_tool=false; resolve the host helper or pin/hash its
bundled copy before any future shell enablement. No shell enablement is proposed.

Catalog present: yes. Targeted Hearth model gate: passed. Complete runtime
compatibility and real-account execution: unknown. This is not Piece2 live
acceptance or a human approval decision. Service activation and paid runs remain
gated on Rad's [APPROVED]; production unchanged, frozen inventory track untouched.
