# Independent stale-poll observer implementation plan

> Execute inline with superpowers:executing-plans and TDD; one fresh final review.

**Goal:** Detect a stopped controller independently of controller failure/recovery claims.
**Architecture:** A disjoint observer principal invokes an authenticated one-pass endpoint. One atomic journal event records server-clock assessments of configured controllers using existing cadence+grace rules, plus observer-owned incident states. Controller reports remain separate. No installed timer, daemon, provider or deployment.
**Tech:** Existing Python/SQLite/FastAPI and controlled-clock synthetic acceptance.

## Binding design and constraints
- POST /api/hearth2/control/observe permits observer bearer only; payload request_id, expected_seq, expected_epoch. Observer cannot tick, write manual failures or manage tasks. HEARTH2_OBSERVER_IDS is optional, disjoint from all existing roles; disabled instances stay inert. At most128 controllers per observation.
- Compute from server journal/current restore epoch and server observation time, never caller time, target state, references or claimed health. Share the human view timing assessment: age > cadence+grace is stale; equality recent. Missing config/tick, malformed/future timestamps are unknown and cannot close an open incident.
- Separate poll_observation audit action, entity per observer+restore epoch. Persist bounded controller assessments and incident_state none/open/recovered. Stale opens; only a newer timely tick than the last stale assessment's tick can recover. New/replayed ticks alone do not modify observer records. Manual controller reports/recovery cannot change observer incidents. Recovery means polling resumed, not worker health or delivery.
- Checks have CAS/epoch and stable request-id replay: repeated old request returns original row/time, not a fresh observer heartbeat. New epoch starts unknown/no inherited health; preserve history. One transaction reads and records; no task/run/claim mutations.
- Human view shows last observer check, assessed poll sequence/time, policy and observer incident separately, with no independent health inference or observer process-liveness claim.

## Task 1: implement and prove the increment
- [x] Write RED unit/HTTP acceptance for stopped poller -> observer open -> controller claims/tick leave open -> new observer check recovers, with independent auth.
- [x] Implement shared timing helper, bounded atomic observer, runtime role/route, and human status section. Keep existing manual failure contract.
- [x] Verify boundary, unknown, replay, rollback, restore, roles/spoofing/cookie/config tests and small user-facing acceptance.
- [x] One fresh read-only review, one fix pass if needed, immutable offline full suite, signed local commit and remote HM outcome/checkpoint. Preserve private evidence; no push/deploy/activation.


Verification: focused8 observer journal tests PASS1.363s,3 authenticated observer
acceptance/config tests PASS6.679s, and17 existing human-status tests PASS11.226s.
One fresh read-only final review found no actionable findings (static review only).
Full immutable Ubuntu24.04/Python3.12 offline suite:1,108 tests PASS155.935s,
actual exit0; external networking disabled, loopback only. All106 checked code/test
files match the snapshot. Source SHA256:
b80ab14554e02fee6b0ab21ec625182a55af19d3ad46b73380527772c1b611b5.
This is local synthetic application acceptance, not activated/off-host acceptance.
