# Piece 2 prerequisite: record interfaces

These are backend contracts for the approved trial slice. They do not launch a
runner, deliver a phone card, check subscription allowance or activate a model.
Independent review of this PR and the human merge gate precede runner consumers.

## Answer a run question

`POST /api/hearth2/tasks/{task_id}/answers`, authenticated as the human who
approved that task's exact plan manifest:

```json
{"expected_revision":3,"run_id":"run_example","answer":"Use the approved source.","evidence":["human-answer-reference"]}
```

The task must be `needs_decision`, at that exact revision, with fewer than three
launches. Its latest run must match `run_id`, have a valid `needs-decision`
closeout, known exit, end time, verified containment and closed claim. Its bound
plan and role must still authorize the action. A second review disagreement
cannot take this route. The operation stores answer, human, time, run, revision
and references in `task.data.human_answers` and a matching immutable audit event;
then changes state to `ready`, increasing revision by one. Counters, manifest
inputs and prior run rows stay unchanged. New scope needs a new approved plan.
The answer is supplemental task context, not tool, budget or deployment authority.
Old answer cards, claims and expected revisions are refused after consumption.
There is no phone-card UI in this PR.

## Controller health and standalone failures

`POST /api/hearth2/control/ticks` is bearer-controller-only. Body fields are
`request_id` (stable per completed polling cycle), `expected_epoch` (from the
current control snapshot), `expected_seq` (zero initially,
then the returned latest sequence), and nonempty `evidence` reference list.
Runner identity and time come from the server. Replaying the same request returns
the original timestamp; it never refreshes liveness, even after a newer tick.
Changed replays and stale sequences fail. Restore epochs separate old ticks from
current liveness. A tick is poll evidence, not workload success or notification
delivery proof.

`POST /api/hearth2/control/failures` is also controller-only. Fields: `kind`,
`target`, stable incident `key`, `expected_seq`, `state`, `evidence`.
Kinds are `runner_stale` (configured controller target), `missed_start`
(ready task with no launches), and `dispatch_blocked` (ready task). Task targets
must retain approved-plan/role/dependency eligibility. The caller supplies the
observation references; this endpoint does not itself measure a start window.
Opening uses sequence zero. Further observations or explicit recovery use the
latest sequence. Recovery cannot create an incident; explicit evidence is
required, and a tick does not recover a failure automatically. Same-event replay
is idempotent. Failures never invent runs or consume attempts, requeue tasks,
overwrite run incidents, or act as containment proof.

`GET /api/hearth2/control` is human/controller-only. It returns current
`restore_epoch`, server `observed_at`, latest current-epoch `ticks` per controller, and latest
`failures` per kind/target/key, including recovered and previous-epoch evidence.
Future all-failures reports must include both these control failures and the
existing run incidents; the two are explicitly different record types.

These events append transactionally to the existing `audit_events` journal.
Schema and bundle remain version 1; export already includes all journal rows.
Restore keeps failure history but requires a genuinely new post-restore tick.
No new SQL migration exists to roll back. The previous binary can still read the
unchanged layout and retain journal evidence; it cannot perform the new answer
or health operations. The existing nonempty-downgrade refusal remains in force.

## Timing configuration

Only enabled Hearth 2 instances parse `HEARTH2_LEASE_SECONDS` (default 900) and
`HEARTH2_DEADLINE_SECONDS` (default 7200). Both accept integer seconds 1–7200;
invalid settings refuse startup before database creation. Disabled mode ignores
these values without opening the database. Initial lease is clamped to the run
deadline; renewals cannot extend a deadline. Restarts/config changes do not
rewrite already-created claims or deadlines. Short values permit repeatable
containment tests without relaxing the approved two-hour ceiling.

## Verification and remaining work

Focused tests cover answer identity/revision/run/evidence, stale cards and
claims, immutable scope/counters, exhausted attempts, superseded plans, held
unknown exits, second-review disagreements, backup/restore, short deadlines,
default-off config, authenticated API boundaries, tick persistence/CAS/replay,
failed transactions and standalone failure records without fictitious launches.

Runner, broker, independent process containment and actual model acceptance are
still to build. Current usage-page evidence is an outside wait before live
model tests, separate from the provisional 6–9 engineering days. Historical zero
charges are not current cost evidence. The accepted credits-on/$75 seat-cap
policy stays unchanged. Production and native accounts are not modified here.

Full Python regression: 369 tests PASS on the isolated trial host, Python 3.12
(94.704 seconds). The final additive server-observation timestamp was checked
in the focused suite after that full run. Of the total, 90 tests cover Hearth 2
and 19 are added here. Internal review has no remaining blocking findings;
Claude exact-commit review is pending. No native provider calls were made.
