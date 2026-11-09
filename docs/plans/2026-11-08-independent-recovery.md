# Independent stale recovery authority

Spec: Rad explicitly requested that a controller cannot mark its own stale report recovered. Enforce against the target identity, whoever opened the incident. A different authenticated controller may recover it; supplied references remain unverified. Preserve old journal records, self-report labels, CAS/epoch protection, and unrelated failure kinds. No observer role, authentication change, deployment or activation.

## Task 1: journal authority and regression coverage
1. RED: reproduce direct self-recovery and legacy idempotent replay bypass; reproduce HTTP denial failure.
2. GREEN: reject runner_stale recovered when actor.id equals target before idempotent replay. Keep epoch validation and independent-controller recovery/replay.
3. Adapt legitimate recovery and explicit historical UI fixtures. Verify atomic rejection, authenticated HTTP identity/roles and replay, legacy display and existing delivery acceptance.
4. One fresh review of the increment, then immutable offline full-suite verification. Keep existing local branch, signed local commit, durable outcome/checkpoint; no push.

Expected: direct/HTTP regressions fail before the guard, then focused and full offline tests pass. Historical self-recovery remains readable but no longer replayable through the public mutation path.

Verification: journal10, HTTP API8, human status17 and delivery/health acceptance2
focused tests passed. One fresh read-only review found no actionable issues.
The immutable offline full suite passed 1,097 tests in 179.164s, actual exit0,
with external networking disabled and loopback only. All 102 checked code/test
files matched the snapshot. Snapshot SHA256:
1cc6d812e441fd88782753b02d6ad1cbab1af882de30ad3428d76a37c6cbc573.
These are local synthetic-store/application results; no live observer or deployment.
