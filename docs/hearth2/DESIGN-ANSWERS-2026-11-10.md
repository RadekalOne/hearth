# Piece 2 — five design answers,10 November2026

The native walking skeleton now demonstrates the composed synthetic path, and
Claude has passed it at that scope. Rad's usage figures are still needed for the
real-turn request; the answers below do not authorize execution or decide new scope.

## 1. How do read-only/no-network closeout and plan output reach the record?

The native process returns closeout text over its existing stdout/stdio channel.
Trusted root code consumes bounded output and commits through
`DispatchRegistry.record_native_result`; the result lives in `runs.closeout` with
validation/state and controller evidence. No worker database write is required.
The container's loopback HTTP/Unix Broker bridge serves reads only; OS network
none does not prohibit that explicitly mounted local IPC channel.

No plan document exists in the skeleton: `produced` is a synthetic reference.
Shipping a plan needs bounded artifact ingestion/storage plus a content hash and
record reference. Storage location, retention and the artifact-write contract
remain unresolved; a plausible string is not an artifact. The shipped native
turn/output bridge and this artifact path are still work, not fulfilled design.

Evidence: walking fixture `settle`, existing `dispatch.py`311–352 and Store
closeout validation/receipt transaction; walking real/stub table.

## 2. How does a real model call leave the container?

It does not in the current fixture: both provider responses originate on the
container's own loopback interface. A real run needs separately reviewed,
provider-restricted egress and account projection before prompt dispatch. The
exact destinations/auth refresh requirements and enforcement proof are pending;
granting general network access is not the implemented answer. The private
Broker socket is a separate local route, not provider egress. This is an open
precondition in the real-turn packet, not something the synthetic PASS verified.

Evidence: walking Docker `--network none`, fixture provider127.0.0.1:8099,
`native_profiles.codex_config` and its unfulfilled launcher requirements.

## 3. Is Cloudroom still in the launch path?

The demonstrated trial path launches the pinned native CLI directly from Hearth's
root fixture via Docker; Cloudroom is not an execution hop in that path. The
existing direct profile builders also configure native CLI/MCP protocols rather
than Cloudroom's previously denied SDK contract. This is an implementation fact,
not a decision that Cloudroom is removed from every role or system. Formalizing
the approved fallback as the long-term design still needs to be recorded in the
definition; no such new decision is inferred from component code or this answer.

Evidence: walking root controller, `native_profiles.py`, and
`DIRECT-NATIVE-PROFILES.md` configuration boundary. No service was activated.

## 4. What is needed for the equivalent unattended Claude CLI boundary?

Reusable code already includes claims/dispatch, scoped Broker reads, native
Claude stream-output/typed-stop reduction, and strict Claude profile/managed
permission builders. Earlier synthetic Claude tool/expiry fixtures exist. What
does not transfer is the Codex-specific catalog/thread/model-list protocol.
Claude still needs its approved exact model/client/account binding, a reviewed
launch/stream adapter, private capability delivery, independent deadline/cleanup,
and a composed synthetic run followed by separately approved real A10 evidence.
The current builders' environment capability reference does not meet Claude's
new shipped-launcher condition5 and cannot simply be promoted as-is.

Provisional engineering estimate: **2–4 working days after the shared root/turn
boundary is settled**, excluding account/usage approval and external review
waits. This is an estimate from source reuse/gaps, not a commitment or a claim
that Claude's live launch path already exists. No alternative senior model is
proposed and no unattended Claude account turn was run.

Evidence: `native_profiles.claude_arguments`, `native_policy.py`,
`native_output.py` ClaudeTurn, `test_hearth2_native_output.py`, and existing
direct-MCP synthetic fixture evidence. Claude's wider slice review remains open.

## 5. Can software read remaining seat allowance?

**Codex: a documented read mechanism exists.** Official app-server documentation
provides `account/rateLimits/read` and update notifications, with used percentages,
window lengths and reset times; fields/buckets can be absent. That is not an
exact remaining-token or dollar budget. Its availability and useful populated
results on pinned0.159.1 with Rad's actual account are **not verified here**;
the credential-free fixture's null account fields prove neither allowance nor
absence of support. The current reviewed pre-turn RPC allowlist does not expose
this account read, so adding a preflight path needs review, not a raw bypass.
[Official Codex app-server documentation](https://learn.chatgpt.com/docs/app-server).

**Claude: a supported unattended preflight remaining-seat-balance API is not
established by the evidence reviewed here.** The current reducer recognizes
typed `rate_limit_event` allowed/warning/rejected states as reactive signals;
that does not reserve capacity or fetch a remaining balance. Official consumer
guidance documents the interactive `/status` view and separates subscription
allocation from API-credit billing. Do not scrape an undocumented OAuth endpoint
or treat a `/cost` estimate as remaining seat allowance. This is bounded
uncertainty, not a claim that no API could exist.
[Claude subscription guidance](https://support.claude.com/en/articles/11145838-use-claude-code-with-your-pro-max-or-ultra-plan),
[usage/billing explanation](https://support.claude.com/en/articles/14552983-models-usage-and-limits-in-claude-code).

For this approval packet, retain dated screenshots for **both** seats plus
reset/credits/extra-use state and the monthly budget total. A fresh supported
account read may later supplement those; absent fields remain unknown. Shared
interactive usage and rounded percentages prevent assuming that every observed
quota delta belongs to the test. No balance read, reset redemption, account
change, credential refresh or real provider probe was performed for this answer.

## Review status and next decision

Claude `drawer_ff38dcebac9a75cb3e448ac8c5f8f6c3` passes the thread boundary and
synthetic A4/A8/A9 shapes;96 tests independently reproduced, VPS run receipts and
commit signature not independently checked. All six shipped-launcher conditions
are carried verbatim in scope in the real-turn draft; none is silently closed.
The next executable-work item needs a concrete reviewed turn/account/egress path
and an enforceable financial bound before Rad's approval can authorize a run.
