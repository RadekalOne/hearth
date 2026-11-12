# Native turn and private Broker prerequisites — 11 November 2026

This increment implements Claude review conditions 3–5 as inactive components:
canonical native turn dispatch, bounded streamed events, and a private scoped
Broker channel. It does not authorize a live launcher, activation or paid runs.
Claude's independent review of the final commit remains required.

## Changes

`NativeRpcClient.turn_start` accepts one exact text-only request for the client's
own canonical safe thread. Extra provider/model/config fields, foreign threads,
replays, approval-policy differences and private-method bypasses are refused.
The effective thread must name `gpt-6.1-sol`, never approval and read-only sandbox
with network disabled. Durable intent, native IDs, response hash and terminal
count/digest are recorded without prompt, error text or credentials. Audit/fence,
protocol or deadline errors request an external workload stop; unconfirmed stop
remains explicit. No automatic retries or model substitution.

Turn streaming has separate defaults: 10,000 events, 8 MB canonical event bytes,
45 seconds (including initial acknowledgement); existing 1 MB frame/16 MB session
and 64 pre-turn control-notification limits remain. Events received before the
turn acknowledgement are bounded and then bound to the owned turn. Final text
is capped at 16 KiB and input at 2 KiB. Existing CodexTurn reduction and usage
semantics are reused; reported usage is not a billing receipt.

The Broker bearer stays in trusted host-root memory. A per-run Unix socket
exposes only that grant's memory_search/get reads, with live checks before and
after requests. The root-owned parent is mode0700; only the socket inode is
mounted for UID1000. The fixed loopback MCP adapter accepts no Authorization or
Origin header and forwards no URL or worker credential. Native configuration
contains no bearer environment reference. Closing the channel revokes its grant
and removes only its own socket inode. Host root and upstream callbacks remain
trusted. This replaces worker token handoff, rather than teaching the client a
new secret-file mechanism. The legacy environment profile remains for historical
tests and is not the new launch path.

## Verification and limits

Focused tests run on trial Linux/Python3.12 with private pipes/real Broker:
74 pass. The full repository suite passes all 1,222 tests in 119.726 seconds
(exit0). Coverage includes >64 events, pre-ack events, count/bytes/deadline/final
text bounds, wrong identities, replay, audit/fence failures, expiry, read scope,
private channel cleanup and actual loopback transport without bearer forwarding.

One fresh-context source review found an authority race during durable intent
fsync. A regression reproduced a turn write after revocation; the one fix pass
rechecks the live fence after the audit and before transport write. All 74
focused tests pass afterward. No second reviewer pass or Claude PASS is claimed.

Final actual native-client pair:
`/root/hearth-runner-trial/walking-f30c044e028d49eb9c737710ffe11b27`.
The provider and HM upstream are explicitly synthetic. The positive run enters
review; the missing-closeout run returns to ready with an incident. Both native
processes exit0, their cgroups are independently confirmed empty, and containers
are removed. The positive run handles >64 native events. Both confirm bearer
absence in Docker metadata and native environment/argv/config. Understanding is
unknown and human acceptance false. Task transitions are synthetic fixtures only.

The source, run IDs, hashes, counts and broader-suite result are in
[evidence/native-turn-private-broker-2026-11-11.json](evidence/native-turn-private-broker-2026-11-11.json).
Prior failed environment setups are retained, not relabelled passing: initial
small pip tmpfs filled; noexec test tmpfs denied executable helpers; first full
snapshot lacked Git, ops/docs and the public Chroma model cache. Those are
isolated test-environment corrections; no product tests or frozen-track code
were changed to hide them. Final test execution has network disabled and uses
synthetic identities/temporary stores, no account credentials. Dependency/model
preparation fetched public artifacts only; the Chroma archive matches its
package-pinned SHA256.

## Still gated/open

The paid-turn packet remains prepare-only until independent exact-commit review
and all financial gates, including fresh seat screenshots and explicit approval.
No real account entitlement, allowance read, provider egress/request cap, financial
ceiling or live A4–A9/N2/N3 acceptance is established. Real HM upstream wiring,
plan-document storage, long-term Cloudroom choice and Claude runner remain open.

RootLifecycleDriver v1 is unchanged and still disallows these fixture bind/stdio
adapters. Trusted callbacks must be bounded and composed with an independent
root cutoff; protocol completion cannot replace observed OS exit/empty proof.
This increment does not claim all six launcher conditions closed: general
post-thread-start failure reconciliation/ID persistence and the unattended
journal capacity/lifecycle still require shipped-launcher review. Shell remains
disabled; bubblewrap must be resolved before any shell enablement. Production,
service activation, global client, accounts, credentials and billing are unchanged.
