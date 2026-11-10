# Slice critical-path status — 9 November 2026

Authority: Rad's direct 9 November decision, also posted in Agent Tasks as
`$9sKQnez8Czl9HGTguXT-DX3pj4MqcxNlvdisP9GMZ-Q` and recorded in HM
`drawer_8c75e577bf5a5bbf5f427e8983d8ae4c` /
`drawer_fe05c2087d0ee9c0db66a68fb33fc94d`.
This is an estimate/status update for the 13 November review, provided ahead of
Thursday 12 November. It is not a live acceptance result or a new scope grant.

## Frozen track

Credential inventory, MiniMax parsers, acquisition design, data-directory port,
source-map/enrollment contracts, named-session client and receipt pilot remain
closed at their existing state. No additional implementation or cleanup is
queued for that track. Historical unverified physical/production claims remain
unverified; freezing work does not turn them into acceptance evidence.

## Item 1: Piece 2 estimate

Provisional remaining effort: **8–12 engineering days**, excluding Rad approval,
account/allowance waits and Claude's review queue. Re-estimate after the exact
model gate and first composed trial launch. This is not a promised elapsed date.

| Remaining work | Engineering days |
|---|---:|
| Resolve exact `gpt-6.1-sol` client/catalog compatibility and verify the approved native profile | 1–2 |
| Compose concrete trial launcher/driver, broker, bounded native output, independent deadline and restart/termination recovery | 3–4 |
| Execute live acceptance variants; persist authoritative run rows and reproducible evidence | 3–4 |
| Fix acceptance findings and assemble the exact-commit Claude review packet | 1–2 |

Existing broker, record, structured-output and launch-coordination libraries and
deadline fixtures reduce implementation effort. `LAUNCH-COMPOSITION.md` explicitly
describes an injected driver, not a concrete Docker/systemd launcher. Its open
OS-operation/reboot/orphan-intent, account projection and egress checks are real
remaining composition work. Synthetic tests are not the live Done list.

Read-only trial inspection on 9 November at 20:58:55–20:59:26 UTC:

- Existing explicit SSH identity works; remote hostname `srv2065995`, target
  `179.236.82.242` (trial VPS 2065995).
- Installed Codex reports `codex-cli 0.154.0`; Claude reports `2.1.280`.
- Worker native catalog `/home/cloudroom-agent/.codex/models_cache.json` reports
  client version `0.154.0`, fetched `2026-10-28T14:12:32.128294688Z`, six entries.
  It contains `gpt-5.6-sol`; no exact `gpt-6.1-sol` entry. This is cached metadata,
  not a fresh provider catalog or an execution refusal.
- This narrows/corrects the earlier “catalog advertises gpt-6.1-sol” statement:
  that statement does not establish the installed native client's exact-model
  support. Do not substitute `gpt-5.6-sol` or another senior-role model.
- No client upgrade, login, credential readout, service change, inference or
  production contact was performed for this inspection.

The accepted direct-CLI fallback remains the design basis; compatibility of
Cloudroom's catalog alone cannot establish native execution. First isolate the
exact client's compatibility problem, identify the smallest compatible candidate
and review its profile. Installation/activation and billed inference must remain
inside an applicable explicit approval.

Live Done list, retained exactly from Rad's refocus and the Piece 2 handoff:

- A4: assignment wake plus runner-down, allowance-exhausted and backlog variants;
  late starts are recorded missed-window failures.
- A5: two runners contend for one task; only one workload launches. This does
  not lift the one-agent-workload-at-a-time rule.
- A6: controller crash mid-run; independently confirm the old workload stopped
  before retry; refuse late closeout; three attempts total, then escalation.
- A7: hard deadline stops every child, with outside termination evidence.
- A8: process ends without closeout; recorded failed, visible as a failure item.
- A9: real task uses existing memory and cites its record without asking Rad.
- N2: above-tier mutation/deploy is refused with no broad credential available.
- N3: injected instruction remains task data and causes no prohibited post.

Use real trial run IDs, exact source/client versions, commands, grant/refusal and
termination evidence, native allowance stop handling, unknown usage where absent,
and measured seat usage in the `[REVIEW]`. Claude reviews that packet. No live run
has been added by this refocus inspection.

Model investigation follow-up: `CODEX-CLIENT-CANDIDATE-2026-11-09.md` identifies
0.159.1 as the first stable candidate above the existing pin whose embedded
catalog contains the exact model. Static artifact verification only; no client
installed/executed and no activation or paid acceptance. The WSL/Windows history
and separate trial observations are retained there.

## Item 2: supervisor and morning report together

Subsequent approved pre-activation exercise: candidate installed trial-only;
version/catalog/effective-policy checks passed, but unknown-model thread creation
was accepted. Stopped before tool-loop checks. See
`CODEX-01591-PREACTIVATION-2026-11-09.md`; no service or paid run authorized.

Existing local status code already computes `self_reported = actor == target`
and renders the Self-reported badge (`human_status.py`, `status_page.py`). The
independent stale-poll observer is a one-pass detector, not an installed timer or
proof of cross-process uptime. Reuse and verify these components in the trial
composition; do not open another credential/status feature track.

Still needed: independently operating deterministic supervision of stale ticks,
overdue runs, orphaned claims and missing closeouts; fail-closed recovery with
distinct authority; self-reported report/recovery attribution on the real page;
Healthchecks.io tick and outside no-active-run dead-man acceptance; 07:00 local
report generation and an independently checked report-completed receipt.

Report history includes all failures, with retry/recovery summarized per incident;
Waiting on you contains only human-owned decisions. Empty human lists, successful
report generation and push delivery are different facts. Preserve push's separate
receipt/failure, quiet hours, local-date deduplication, restart/DST behavior and
missing-report detection. Then run seven consecutive correct nights, including
the specified failure scenarios; component tests do not start that window.

## Item 3: decision cards

After pieces 3–4: human identity-bound Approve/Decline/Ask, exact plan revision,
expiry and single-use enforcement, durable answer/audit and stale/replay refusal,
plus explicit per-project thread-to-card cutover and user acceptance. Until that
cutover, thread replies remain the approval record. No decision-card deployment
or implementation is included in this status update.

## External waits and limits

- Before billed live runs, Rad's applicable explicit `[APPROVED]` must cover the
  bounded trial run/activation and spend. The refocus decision itself does not
  waive this requirement. No speculative model prompt to diagnose availability.
- Current Claude/ChatGPT seat usage and November spend/headroom are needed for
  the preflight and review cost line; account sign-in is not allowance evidence.
  Pause the slice at $75/month; unknown cost is not zero.
- Claude's exact-commit review follows the real acceptance evidence. Any necessary
  client/core pin change needs its concrete candidate and applicable review/gate.
- Trial only. Production unchanged. No merge, production activation or deployment
  without explicit `[APPROVED]`. Existing inactive 900-second/full-run policy stays
  unchanged. Two-week reviews continue. Rad sets the December end date on 13 Nov.
