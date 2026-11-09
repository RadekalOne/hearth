# Human delivery and poll status view

Rad requested this next increment after the isolated delivery/health acceptance
exercise. Preserve the existing checkout, inline execution and inactive runtime.

Build a read-only authenticated human page and JSON read model over existing
Hearth 2 records. The person can inspect assigned work, recorded notices and
controller polling, then expand the evidence behind each state. This is a local
offline build; no production activation, provider, room posts or automation edits.

Approach chosen by Codex within the requested scope: server-rendered HTML with
native details/summary controls, alongside JSON. Existing authenticated API
middleware and roles protect both. No JavaScript, new dependencies, new database
schema, observer process, delivery writer or acknowledgement endpoint. Extending
the old H1 dashboard would mix unrelated stores; a separate read-only H2 view
keeps the existing default-off boundary and makes review small.

## State contract

- Task cards show the persisted human-readable task state and assignee. Results
  awaiting review, reviewed and accepted remain distinct.
- Every existing notice is Recorded / delivery unconfirmed. No delivered, read,
  understood or acted-on claim follows from viewing it, a task result, a tick or
  arbitrary notice metadata. Show notice ID, task, recipient and original evidence
  reference as escaped text. No timestamp is invented for old untimestamped notices.
- Poll states are Recent, Overdue and Unknown. Only a completed current-restore-
  epoch controller tick qualifies. Use its original server journal time, compared
  with this response's server observation time. A replay never refreshes it.
- Timing expectations are explicitly configured per controller: cadence 1..86400
  seconds and grace 0..3600 seconds. Overdue means age strictly greater than
  cadence+grace. At the boundary it remains recent. No configuration, no tick or
  future/malformed timestamp means Unknown, with its reason. Recent means a poll
  was recorded recently, not that a workload succeeded or a notification arrived.
- Optional HEARTH2_POLL_EXPECTATIONS is a strict JSON object keyed only by
  configured controller IDs, each value exactly cadence_seconds/grace_seconds.
  Missing means empty policy, not a default cadence. Invalid enabled configuration
  fails before opening/creating a database; disabled mode does not parse it.
- Show expected timing, last completed poll, assessment time, tick request/sequence/
  epoch and evidence. Preserve open/recovered failures separately. A new tick never
  erases an open failure; failures from a prior restore epoch are labeled historical.
- One database transaction reads task/notice/control records. JSON output includes
  only view fields, no claim secrets, auth tokens, arbitrary notice metadata or
  private run data. Evidence is plain text, never an executable URL. Unknown project
  refuses; filtered views contain no other project's tasks/notices. Controller
  health remains explicitly instance-wide.
- Both routes require human authentication, default-off checks and no-store.
  Role-denied, malformed query and database failures use existing error boundaries.
  HTML escapes every stored value, uses restrictive CSP and no mutating controls.
  The snapshot states when it was assessed and does not auto-refresh or imply an
  independently operating outage detector.

## Acceptance

Synthetic authenticated real HTTP tests: assign handoff -> inspect running -> see
recorded progress -> result awaiting review; no inferred delivery. Advance a
controlled server clock across the explicit cadence/grace boundary -> overdue;
inspect the old tick evidence; replay unchanged -> still overdue; new completed
poll -> recent while an open failure remains visible. Missing configuration/tick,
restore epoch, malicious notice HTML/metadata, auth and project isolation tested.
Render the actual response with synthetic data and inspect desktop/mobile layout
and evidence expansion in a browser. One fresh code review and immutable full
offline regression suite precede local signed commit/HM closeout. Retain the
private workspace and branch; no push/merge/deployment.
