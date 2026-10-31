# Direct native profiles and MCP interoperability

Status: inactive configuration builders and isolated synthetic fixtures. Real
provider logins, upstream Hearth Memory credentials and external networking are
not projected. This is not an installed native launcher or piece-2 acceptance.

## Configuration boundary

`native_profiles.codex_config` preserves an explicit model, pins the OpenAI/native
ChatGPT route, never approval, read-only sandbox, disabled web search and no saved
history. Only `hearth` HTTP MCP is configured, with `memory_search`/`memory_get`
allow-listed and required. It references `HEARTH_BROKER_CAPABILITY`; no raw bearer,
provider key, arbitrary URL/helper/provider or fallback is accepted. Install the
separate root-managed requirements too; this config alone is not enforcement.

`native_profiles.claude_arguments` starts the direct stream-JSON protocol with a
canonical session UUID, explicit model, dontAsk, no built-in tools, no slash
commands, strict MCP, no user/project setting sources and fast mode/workflows
off. It explicitly configures the Hearth HTTP server with the dedicated bearer
environment reference, replacing the old, denied Cloudroom SDK contract. Its
system context accepts root-approved rules only. Retrieved memory and worker
text must remain explicitly untrusted task input. No resume/fork, model fallback
or CLI option override is exposed by the builder.

The launcher must verify effective native policy, a fresh clean credential
route, exact model, private broker/allowed destinations and immutable projected
configuration before a prompt. Neither builder reads a secret or creates a
process/service. Native account and provider permissions remain separate gates.

## Actual broker compatibility

Installed Codex0.154.0 sends `tools/list` with `_meta.progressToken=0`. The earlier
broker rejected any nonempty list parameters, so a stub MCP server passed while
the real broker failed native initialization. The opt-in fixture reproduced this
before the fix; private diagnostics direct-mcp-wo0ij0a4 and76k6f1az retain it.

`broker_http` now validates and removes optional transport-only `_meta` before
method handling. Progress token must be a string/integer, never a boolean or
object. Metadata is never passed as read arguments, accepted as memory scope,
written to the record or logged by the application. Unknown actual tool fields,
write methods and forged argument scope remain refused. HTTP capability checks
before/after reads, byte bounds and argument/scope checks are unchanged. New
regressions exercise native-shaped metadata, scope injection attempts and invalid
metadata; the original SDK transport interoperability test still passes.

## Installed-client fixture

`test/fixtures/hearth2_direct_mcp_probe.py` requires root, exact isolated trial
host srv2065995 and explicit opt-in. Disposable read-only/cap-drop/UID1000
containers have network none; `hearth-broker` resolves only to container loopback.
The actual Broker/broker_http run against a synthetic SQLite work record and a
synthetic upstream callback, using a real scoped fixture grant. This proves
native protocol interoperability with our code, not live HM data or separation
between a real privileged broker and an untrusted worker. That boundary must be
proved in the final deployment layout.

- Codex discovers exactly the two read tools and forwards `memory_get` through
  the actual broker. Its returned effective sandbox is readOnly/network=false.
  No native turn/prompt or provider login is used.
- Claude connects with dontAsk and exactly the two read tools. With
  `--exercise-claude-tools`, a local fake Anthropic SSE server supplies TWO
  synthetic responses. The first deliberately requests an allowed memory read,
  forbidden `memory_add` and forbidden Bash touching a scratch marker. The read
  reaches the scoped synthetic upstream once; write/shell results are errors and
  the marker is absent. This is an actual installed-client tool loop with a
  synthetic prompt, not real provider inference. An obvious fake API key and
  loopback-only API URL are fixture-only, not an approved real credential route.
- `--expire-before-read` advances the trusted fixture clock after discovery.
  Both installed clients return a typed denial, make one MCP tool-call request
  without silent retry and never reach the upstream. It proves expired-grant/
  lease transport behavior. Authoritative late-exit recording and restart/
  containment recovery remain separate acceptance work.
- Each invocation kills its own native fixture client and removes only its
  label-verified container; successful exact-name absence queries verify cleanup.
  No host service, provider/core pin, live account or production setting changes.

Private actual-broker receipts: direct-mcp-m5ecqn8l (Codex read), e7oydam7
(Claude discovery), ww4cadoe (Claude synthetic tool-policy loop), fxgw3ued
(Codex expiry), duhd4zf8 (Claude expiry). Later final-source receipts supersede
these for commit verification. The original stub-only receipts are not claimed
as actual-broker proof. Bubblewrap PATH warnings in the diagnostic are retained;
these startup/RPC fixtures make no claim that a real Codex shell was exercised.

## Parser exception caller contract

The error fixture also accepts `--poison-tail`. After a real native401/429 retry
notification, the fixture injects malformed stdout data. It catches RecordError
from feed AND finish, reads outcome(), stops the still-running native client and
verifies cleanup. The result stays unknown with its typed stop reason. The
separate real-record regression verifies that this exception outcome atomically
holds the task and pauses its role. Private receipts claude-error-0sy8edbs and
mc5823wb demonstrate the installed-client teardown path. They do not replace
outside cgroup-empty evidence for a production workload.

## Lease decision and remaining work

Do not refund an actual auth/quota-stopped launch: it still consumes one of the
approved three attempts. Quota/rate/auth reason is retained so reports distinguish
an infrastructure stop from project-work failure. A transient429 deliberately
pauses the role; it is not labelled included-allowance exhaustion.

The proposed bounded-slice policy uses an initial lease and fixed grant ending
AT the sealed run deadline, without a margin beyond it or mid-run extension.
This avoids native bearer rotation for this slice. It is CONDITIONAL on verified
absolute deadline enforcement including delayed start/controller restart.
Existing900s defaults and live settings are unchanged. Every broker call must
still fence current ownership, epoch, deadline and revocation. A later renewable
mode would require its own verified header/proxy lifecycle; it is not silently
implemented by extending current grants.

Remaining: real credential/settings projection and collectors, exact-model
validation, fixed provider/broker egress, immutable runtime configuration,
independent absolute workload deadline/lease/revocation handling, authoritative
late termination observations, restart reconciliation, supervisor/alarms and
composed real-native acceptance. Current profile/loopback tests do not pass those
gates by association.

Primary configuration references:

- https://learn.chatgpt.com/docs/config-file/config-reference
- https://learn.chatgpt.com/docs/app-server
- https://code.claude.com/docs/en/mcp

## Final component verification, 31 October

Full offline Python3.12 suite: 484 tests PASS in91.675s, source archive SHA256
42b941a8dc4c1547b4521e55d1394133e9f6401cebcf7d967c9cb156d01a825d, private
source/log directory hearth2-native-mcp-final-20261031-42b941a8. Native fixtures
on that source: direct-mcp-5_jz_j_v (Codex read), d1o7t8cf (Claude read/policy),
duo8xr5x (Codex expiry), 61ndrga6 (Claude expiry); poison-tail401/429 receipts
claude-error-4ef2k02m/pqjuipaf. Every fixture verified its own cleanup. A later
fixture module-docstring clarification changes no executable payload.

Independent new-component review found no Important findings; 33 focused tests
passed there. That reviewer could not import broker HTTP tests locally without
httpx and did not run privileged fixtures. The full trial suite above covers the
HTTP tests; native fixture evidence is the implementer's recorded execution.

Prior native-output commit4ca51f3 separately received Claude component PASS
(source inspection only) and CI102/run41207042538 SUCCESS. Neither is a PASS
on this subsequent component or the complete piece2.

## Installed Codex shell/capability follow-up

Claude's component PASS on2d5afc9 was source-only (no tests/CI/probe/docs read).
CI103/run41211179958 independently completed SUCCESS. His prelaunch note asked
for proof that a shell cannot disclose the environment capability. Root-managed
requirements already pin shell_tool=false, and Claude managed permissions already
allow exactly the two read tools. The profile now repeats shell_tool=false and
shell_snapshot=false, uses inherit=none plus explicit HEARTH_* exclusion, and
Claude argv explicitly lists the two allowedTools. Empty child environments alone
do not prevent a same-UID shell from reading its parent's /proc environment; the
primary memory-only boundary is refusing the shell tool entirely.

The new --exercise-codex-tools fixture uses the actual installed0.154.0 and the
same read-only root requirements. It uses a FIXTURE-ONLY custom Responses provider
and fake API-key auth pointing to container loopback, preserving all tool policy.
Built-in openai provider overrides are refused by this installed client; the
normal ChatGPT profile remains unchanged. This fixture proves tool enforcement
with synthetic input, not real ChatGPT account/model routing. The fallback model
METADATA warning is retained; no real model or alternative model was called.

Two fake Responses results deliberately inject shell_command, exec_command and
shell calls attempting both direct environment and parent /proc environment reads,
plus an allowed namespaced memory_get and forbidden memory_add. The fixture checks
the shell names are not advertised, all three explicitly return unsupported call,
write is refused, permitted model-issued read reaches our actual scoped broker,
no scratch marker exists, and the synthetic grant value appears in neither native
stdout nor captured fake-model requests. It does NOT claim /proc is unreadable to
an arbitrary same-UID executable; the attempted reading tool is refused. Only
the root-side protocol can issue native control RPCs, never the worker/model.

This stronger tool-loop check initially found that allowed model reads failed:
our earlier control-RPC read bypassed model approval. The actual native error was
'MCP tool call requires approval, but approval policy is never'. Both broker tools
now advertise readOnlyHint=true, destructiveHint=false, idempotentHint=true; the
existing broker still enforces read-only tool/scope/lease checks. No general auto
approval or request-policy bypass was introduced. The actual model read now works.
HTTP regression checks the annotations. Intermediate passing actual native receipt
direct-mcp-qmvw19pz includes two fake responses, shell/write refusal, no capability
output and verified cleanup. Final-source receipts follow in the progress record.

Primary references: [Codex config](https://learn.chatgpt.com/docs/config-file/config-reference),
[MCP ToolAnnotations](https://modelcontextprotocol.io/specification/2025-06-18/schema#toolannotations).

Final follow-up verification: offline Python484PASS88.893s at private
hearth2-native-tools-final-20261031-bc74f692/verification.log. After that source
archive was created, only the opt-in fixture assertions were strengthened (exact
namespace tools, permitted read reaching model input, stderr capability absence);
no product/tested-library behavior changed. The strengthened fixture SHA256 is
c031fb3895330920f5cabc5c2b75e4beef2e42a044becf24a27a47704713fa12.
Its final actual-client receipts are direct-mcp-6gux0nbx (Codex synthetic tool
loop), 37uy7nfa (normal ChatGPT-profile discovery/read, no provider prompt),
_jd2jijc (normal Codex expiry), er7zuic_ (Claude tool loop), velcnmzx (Claude
expiry). All PASS/cleanup verified. Do not use the original bc74 archive hash
as the later fixture-file hash; the private extracted fixture was updated.
Independent review found no remaining Important findings and inspected earlier
qmvw19pz raw synthetic tool outputs itself. That reviewer did not run final
privileged fixtures or broad tests.
