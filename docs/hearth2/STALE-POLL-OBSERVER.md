# Independent stale-poll observer

This increment implements an authenticated, one-pass detector in the existing
service. A distinct observer principal initiates the check independently of the
controller poll loop. It does not install a timer, worker, daemon or credentials.
No actual cross-host/process independence, observer uptime, host outage detection,
worker health or notice delivery is established by the fixture tests.

## Operator contract (not installed configuration)

Optional HEARTH2_OBSERVER_IDS lists observer identities, disjoint from humans,
controllers and workers. Observer and controller transport credentials are bearer
only, not browser sessions. Observers can read GET /api/hearth2/control and invoke
POST /api/hearth2/control/observe; other existing mutation routes reject them.
No principal is provisioned by adding an ID to configuration.

The check accepts only request_id, expected_seq and expected_epoch. An external
caller reads the current restore epoch and its latest current-epoch observation
sequence (zero if none), then sends a new bounded request ID with that sequence.
Targets and cadence/grace come from configured controllers and the existing
HEARTH2_POLL_EXPECTATIONS, never request payload. Up to128 controllers are assessed
per check. A stale sequence or restore epoch conflicts without writing. Retry an
identical lost-response request with its original ID/sequence: the original result
and time return. A new check requires a new ID and current sequence. Replaying an
old request does not prove a fresh observer invocation. If configured targets or
policy have changed, reusing the request ID conflicts rather than reinterpreting
the original observation.

## Observation and recovery

One transaction reads current-period server journal ticks and server time, then
appends a poll_observation audit event. The human page and observer share timing
rules: age greater than cadence+grace is stale; equality is recent. Missing tick or
policy, unusable time and future time are unknown. No tick is treated as unknown,
not an inferred startup outage. The observer currently detects stopped *known*
pollers, not never-started controllers.

Each observer owns separate per-controller incidents within its restore period:

| Evidence at a new observer check | Observer incident |
|---|---|
| Timely poll, no previous incident | None |
| Poll overdue | Open; retain latest stale poll sequence as recovery fence |
| Unknown assessment while open | Keep open |
| Same tick becomes recent after policy/clock change | Keep open |
| A newer timely tick than the last stale assessment | Record polling resumed |
| Poll becomes overdue again after recovery | Open a new outage state |

Controller failure/recovery reports live in a separate journal action. A controller
cannot invoke the observer or supply observation times/states/references. A tick,
including a new tick, cannot close an observer incident by itself. A separate
observer check must see the newer timely tick. Another observer's check does not
close the first observer's incident. Recovery here means server-recorded polling
resumed, not independent verification of work, model execution or service health.
A controller still supplies the completion assertion behind its journal tick.

The status page separately displays observer identity, last check/assessment time,
policy, assessed tick/time/age, stale and recovery sequences and restore period.
It does not run checks on read or label an old observer record as current process
liveness. Historical restore-period observations stay labelled historical; a new
period starts with unknown poll state until it has a new current-period tick.

## Small acceptance exercise

The authenticated temporary app uses a60s cadence and10s grace. A controller polls
at12:00; observer checks recent. At12:01:11, a new observer check records stale/open.
Controller 'I recovered' references and poll replays leave that observer incident
open; self-recovery is refused by the previous journal rule. A new controller tick
still leaves the observer record open. A later observer check records polling
resumed and links the newer tick. The human JSON/HTML show the observer and evidence;
the controller's separate manual failure remains open. Tasks, runs, claims and
attempt incidents do not change. Fixtures also cover threshold equality, missing/
future/malformed time, policy relaxation, replay, CAS, restore, rollback, restart,
second observers, role overlap, bearer-only transport and spoofed payload fields.

This is local synthetic application acceptance. There is no schedule installed or
live detector activated. Poll/check scheduling, credentials, trusted service clock,
independent host availability, outage notifications, large-history pagination and
physical acceptance remain separate work. Default900s/full-run policy is unchanged.
