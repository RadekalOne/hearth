# First supervised real named-session receipt

9 November2026. The existing real Codex chat **Hearth 2 — laptop continuation**
(id01a194ad-865c-7100-a33a-e220e62cff8d) on verified RSLABINSKI-PC invoked the
named-session client against a dedicated, persistent, loopback-only Hearth v2
service using real TCP/HTTPS. This was not a unit fixture, ASGI/mock transport or
patched clock. It was a one-time supervised local run, not shared production or
a permanent background connection. The service and generated credentials have
now been retired.

The app's chat record and native CODEX_THREAD_ID agreed before enrollment. The
invocation wrapper checked that native thread ID and COMPUTERNAME, then passed
only this session's credential to the existing client. This is explicit operator
session binding and actual invocation from the named chat, not cryptographic OS
process identity or proof of model context ingestion/understanding.

## Observed result

| Evidence | Observed value |
|---|---|
| Named session | codex-laptop-01a194ad |
| Authenticated receipt principal | codex-session-01a194ad |
| Runtime source | signed0e0323bea757dc89cb3020e8a323115a0f3097cc, immutable Git export |
| Runtime origin during test | https://127.0.0.1:55139, now stopped |
| Notice | notice_242b203698074e9abccbd43a0a5539e3 |
| Exact body digest | b95f14a53069287fd74da48cc5726e895f66063c6af80004b19354b2e8161838 |
| Receipt server journal | sequence11,2026-11-09T06:09:26.023606Z (01:09:26 EST) |
| Before acknowledgement | Client durable store confirmed; server previously unconfirmed |
| After acknowledgement | Received / receipt recorded; understanding unknown |
| Repeat invocation | Zero new stored notices and zero new receipts |
| Task state | Running (claim recorded), unchanged |
| State preservation | tasks/runs/claims/notices/incidents/incident_attempts table-value snapshots unchanged |
| Native task execution | No native worker/model/provider execution was requested or started |

The dedicated operator/controller created one real receipt-only carrier plan/task/
claim/notice. Its approval record truthfully cites Rad's explicit supervised-test
request and was performed on his behalf; there was no separate human dashboard
click, independent reviewer approval or task-result acceptance. The carrier is
not model work, and its unchanged running record does not imply a worker is alive.
Its task ID is task_891b829c426f458ea97df13aa27bd58a. Receipt never completed it.

## Boundaries and cleanup

Fresh operator/controller/session credentials were generated only for this new
private service; no shared tokens, Mavis login, existing accounts, Matrix/Commons
posts, notifier jobs, schedules or normal services were changed. The client phase
read only its session credential, public certificate and enrollment metadata.
Its mutation attempt was refused403; legacy export was unavailable404.

The listener wrapped the unchanged app in an H2-only route gate. This is important:
the application's generic bearer mechanism also authenticates legacy APIs; H2
role checks alone must not be assumed to narrow that generic credential across a
shared service. The local gate blocks legacy REST/MCP. Shared-service credential
narrowing remains a required deployment gate, not a verified shared-production fix.

TLS used a newly generated local certificate trusted only by explicit client CA
context, with normal hostname/certificate validation. No global trust store was
changed and no verify=False was used. Certificate SHA256:
41011633cc87a0282407d4bebff057ebf85b4fcfd69aaa97e47c5b6382eea3a3.

An independent watchdog supervised startup/runtime. At06:09:53Z the supervised
stop request exercised its owned-process SIGTERM/closure path; no forced kill was
needed. Listener closure and both server/watchdog process absence were separately
verified. Only generated credentials and the private TLS key were removed; the
server token file is empty. The carrier database and named-session client inbox
remain private persistent evidence, without reusable session credentials.
The ten-minute expiry and forced-kill branches were not time-delayed/exercised.

## Evidence and verification scope

Private operation scripts/receipts are preserved in
.superpowers/sdd/2026-11-09-supervised-real-session/. Persistent state is below
/home/rslabinski/.local/share/hearth2-supervised/real-session-20261109 on WSL.
No secrets are included in the public-evidence.json summary. Post-stop readback
verified the single server receipt against the durable client digest and receipt.
Public evidence SHA256:
58e683969b5c690e39d37ae9309ffa86a2976f1d9a98e36be77e2a613a79a591.
Immutable source archive SHA256:
471c6e1df2d9beba6ad39eac03b2884e61256e4e3797dda6877618a1f69392c9.

One pre-activation static review found twoP2 harness issues: staged-source pinning
and startup-dependent graceful deadline. One author fix pass switched runtime to
an immutable Git export and added an independent owned-process watchdog. The
first preflight then stopped before creating state because WSL saw37 CRLF-only
checkout differences; independent normalization found zero content differences,
and the redundant worktree check was removed in favor of the exact Git export.
No additional review loop was used. Actual source/runtime, TLS, receipt, replay,
state-preservation and cleanup were verified by the operator.

Product code did not change. The prior1,131-test offline result belongs to0e0323b;
it was not rerun or relabelled as this real-session result. No new browser visual,
public-PKI, shared-production, automatic native session hook, model understanding,
worker health or task-completion acceptance is claimed. A future ongoing/shared
connection needs deliberate enrollment/lifecycle and the legacy-API restriction.
The existing900s/full-run inactive policy and other jobs remain unchanged.
