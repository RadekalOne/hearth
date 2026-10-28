# Piece 1 verification receipt — 28 October 2026

Status: **implemented, ready for independent Claude review; not project PASS**.
Draft PR: https://github.com/RadekalOne/hearth/pull/33
Tested application commit: `004b4c2200cd2a12a022331d264d7d5bd9e4597d`.
The earlier unsigned local commit IDs were replaced by verified signatures;
source-tree equality was checked before pushing. Repository rules stayed enabled.

## Observed checks

| Check | Result |
| --- | --- |
| Python 3.12 full suite on trial, actual service dependencies and Git installed | 336 PASS, 86.172 seconds |
| Node 24 syntax checks | PASS |
| Node suite | 35 PASS, 1 existing skip, 0 failures |
| npm dry-run packaging | package, API and both migration SQL files present |
| Actual memory-service Dockerfile build | PASS; image `hearth2-record:004b4c2` |
| A5 competing real processes | Exactly one claim and run committed |
| Migration rehearsal | Forward/back/re-forward, checksum/version refusal, atomic failure and nonempty downgrade refusal PASS |
| A11 fresh-container restore | All exported tables/relationships compared; FK and integrity checks PASS |
| Stale writer after restore | Original claim refused; active work held |
| Approval restore | Pending decision held, consumed decision preserved |
| Restored service boot and authenticated API | PASS, exact tested build commit returned |
| Restored service unauthorized read | 401 |
| Re-export from restored service | Fresh instance credentials absent |

Python command:
`python -m unittest discover -s test -p 'test_*.py'`.
Node commands: `npm run check`, `npm test`, and
`npm pack --dry-run --ignore-scripts` with explicit package/migration checks.

The A11 source fixture included two projects, two plans, three tasks, one
dependency, two role grants, three claims/runs, two decisions, one notice, one
incident and attempt link, one scorecard event, and twenty audit events. Every
operational table was nonempty. A separate clean container restored only the
logical bundle; a further container booted the actual service against that data
with fresh trial credentials. This was a synthetic record fixture: no model,
provider prompt or real project approval was executed. The temporary service
was bound to loopback and removed after checks; evidence/data remain private
on the trial host. No production data or credentials were mounted.

## Review and limits

The read-only whole-branch Codex reviewer found unbound approval scope, a missing
revision transition, and a held-success recovery dead end. Each reproduction
failed before its fix and passed afterward. Restore-domain validation and
stale-plan human acceptance also have reproducing regression tests. Typed
dependency gates preserve output→feasibility review without premature human
acceptance. Details and engineering rulings are in PROGRESS.md.

These results do not replace Claude's independent review. They do not prove
worker process containment, task-scoped broker grants, subscription-only launch,
actual unattended model acceptance, phone delivery or seven clean nights.
The clean restore used separate fresh containers on the trial VPS, not a newly
purchased VM. No runner has been installed or activated by this piece. The
trial verification images and private evidence persist; the synthetic service
is stopped. Production services/schema/schedules remain unchanged.
