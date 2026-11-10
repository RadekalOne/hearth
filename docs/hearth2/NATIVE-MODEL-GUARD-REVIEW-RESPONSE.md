# Guard request contract — review response, 9 November 2026

Claude source review `drawer_a3e6dca5280e24cfd909e21543ad685a` passed the model
boundary with one required Medium fix: arbitrary request fields were forwarded.
Verified that finding against the actual prior source. No provider/config or
instruction overrides should travel alongside an exact-model audit decision.

## Required change addressed

The current guard requires exactly this candidate request:

```json
{"model":"gpt-6.1-sol","cwd":"/scratch","approvalPolicy":"never","sandbox":"read-only","ephemeral":true}
```

The model is checked separately against the one-model allowlist and both
catalogs. All keys must be plain strings; missing or extra keys and any changed
non-model value are refused as `request_fields_not_allowed`, recorded before
transport. Types are exact: integer1 cannot stand in for true. No nested config,
provider selector, base/developer instructions, service tier or unknown future
field is allowed, even an empty config or explicit modelProvider=openai.
There are no implicit native defaults, filtering, fallback or retry. The
checked request contains only immutable scalar values and is copied before use.

This fixed `/scratch` request is scoped to the candidate profile. Future concrete
launcher/workspace requirements need a reviewed contract change; this fix does
not introduce a user-configurable workspace or provider selection route.

## Regression and native evidence

Trial Python3.12 RED:16 tests,14 failing new subcases reproduce the old request
forwarding; the prior13 tests remained green. GREEN:16 tests passed in0.017s.
The regressions include provider/config/base/developer instruction overrides,
empty config, extra future fields, fixed-value changes, bool aliases and missing
fields. Each checks a recorded refusal and zero transport calls.

Native network-none fixture `codex-01591-215e7dc314aa45a4aaa9fd86739847eb`
ran23:30:46–23:30:54 Eastern9November (04:30UTC10November). Same pinned0.159.1
binary, separate fresh home, no real credentials, root guard/audit outside the
UID1000 candidate namespace:

- Unknown model refused before any native thread, as before.
- modelProvider, config, baseInstructions and unsafe sandbox overrides each
  recorded request_fields_not_allowed, with zero thread/start calls.
- Only the canonical request was admitted: exactly one gpt-6.1-sol idle thread,
  readOnly/networkAccess=false. Native trace initialize, model/list, thread/start;
  no turn/start, provider inference, substitution, retry or paid call.
- Independent root observer verified stopped/Pid0, cgroup removal and exact
  container removal. Fresh home quarantined root-only. Subsequent candidate
  container inventory empty. All309 scoped baseline hashes unchanged.

Remote evidence directory:
`/root/hearth-runner-trial/codex-model-guard-request-oxworo88` includes exact
source/test, red/green logs, controller/probe, JSONL audit and raw receipt.
Local receipt summary: `evidence/codex-model-guard-request-2026-11-09.json`.
Source SHA256: `a05bb498976d28894d238b669cc3f1e7a5ccf44cbffc70da6e4623128852fa1b`.
Test SHA256: `af05f446ac780390c760238e5e1913e50a9574860c212fa49095c9a926b6d2de`.
Raw receipt SHA256: `70c29a6a172866061ae0c29b31c888a48abb580f2d235bcc2810f44b2b478115`.
Summary SHA256: `647e430758c057fc75dc8c73527c4c97b3121654832802125674c3d5c98ccb76`.

## Four smaller notes: explicit dispositions

- **Auditable model/list freshness:** remains a follow-up for concrete launcher
  integration. The fixture retains the actual model/list response/RPC trace and
  root audit times; each library decision still lacks its own client-list hash
  and JSON-RPC ID. No new freshness guarantee is claimed.
- **Unexpected _check errors:** still abort before transport, but can skip the
  decision row. A bounded guard_error audit path remains open; the required
  request-field fix does not silently change exception/failure classification.
- **Invalid requested-model diagnostics:** still represented as None, avoiding
  arbitrary raw input in the audit. A bounded hash/representation remains a
  diagnostic follow-up; no request text is promoted into trusted instructions.
- **Per-admission hashing:** retained deliberately for this one-thread-per-workload
  trial profile. No cache or new stale-proof shortcut is introduced.

Real scoped broker, forbidden-tool/expiry/output settlement, concrete live
launcher, bubblewrap PATH or pinned bundled helper before any shell enablement,
and entitlement/live acceptance remain open. shell_tool=false stays enforced.
No service activation, paid run, production action, merge or frozen-track work.
The code is uncommitted/inactive, not a new independently reviewed source PASS.
