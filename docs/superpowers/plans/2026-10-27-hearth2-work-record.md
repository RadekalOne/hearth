# Hearth 2 Work Record Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans task by task after
> the pre-build check. No application implementation has started in this checkout.

**Goal:** Build piece 1's isolated, versioned operational record and prove A5 and A11.

**Architecture:** Add a default-off Hearth 2 store beside the existing stores in
an isolated trial memory-service instance. Use a dedicated SQLite file, explicit
migrations, relational identity/constraint columns, JSON only for structured
payloads, and transactional audit. Keep Hearth 1's work module and export API intact.

**Tech stack:** Existing Python/FastAPI service; standard-library SQLite, JSON,
SHA-256, unittest and multiprocessing. No new provider or hosted dependencies.

**Spec:** `docs/hearth2/PIECE-1-SPEC.md` and its canonical source records.

## Current evidence and execution gate

Repository baseline: `d04ea3d74e2409cbe0ba30410c30b01ce3727d4f` (origin/main,
27 October). Existing `test/test_work.py`: **16 passed** locally. These tests
verify the existing Hearth 1 store, not the proposed Hearth 2 record.

Step 0 items 1–4 and 6 have source findings. Item 5, the live trial/Cloudroom
check, remains blocked: desktop SSH rejected; laptop connector offline; working
key location unconfirmed. Do not replace that check with this plan or begin
application code before its [VERIFY] disposition. The original six-item
preflight, not a new build approval, is what remains. No new seat run is needed
merely to inspect the existing host and run-record schema.

Live-check output must establish the actual host, installed/pinned Cloudroom
build, local-only endpoint, run fields, native sign-in/billing guard state,
process containment primitives and artifact/data permissions. Never print
credentials, token-bearing environment, private keys or complete auth responses.
Missing containment or broker support is new piece-2 work, not an invented PASS.
If access remains unavailable, leave this preparation resumable and report it.

## Global constraints

- Trial only; no production data, credentials, configuration or schedulers changed.
- Preserve existing `work.py`, drawer export, HM knowledge and Hearth 1 API semantics.
- Claude and Codex only; one agent workload at a time on the runner machine.
- Three attempts total; expired/unknown work held until independently reconciled.
- Broker read-only task/attempt/lease grants belong to piece 2; never reuse a
  general credential as an apparent task grant.
- No actual usage figure inferred from missing telemetry. No new paid service.
- UTC aware timestamps; injectable test clock; reject naive timestamps.
- Each mutating store operation commits its audit in the same transaction.
- No independent-review PASS, implementation PASS or A11-host PASS by inference.

## Review focus

1. Export during concurrent writes: one consistent snapshot, no dangling links (task 5).
2. Restoring into a populated path: refuse replacement; retain original data (task 5).
3. Late writes from the same agent after a restart: generation/epoch rejected (task 3).
4. Interrupted migration or restore: no half-published usable database (tasks 1, 5).
5. Model/plan changes between validation and claim: check in transaction (tasks 2, 3).

## Files and responsibilities

Create `mcp/memory/hearth2/{__init__,schema,store,backup}.py` and
`mcp/memory/hearth2/migrations/{001_initial.up,001_initial.down}.sql`.
Create `test/test_hearth2_{schema,store,claims,backup,api}.py`.
Modify `mcp/memory/app.py` only for a default-off initialization and authenticated
Hearth 2 routes; modify `mcp/memory/Dockerfile` to copy the new package.
Create `docs/hearth2/OPERATIONS.md` with trial backup/restore/rollback commands.

Do not split or rewrite the existing large app or existing stores as part of this work.

## Shared record shape

All tables carry stable IDs. Projects/tasks/plans have integer revisions;
relationships use foreign keys and same-project validation.

| Table | Identity and minimum fields |
| --- | --- |
| schema_migrations | version, checksum, applied_at; unknown newer version refused |
| record_meta | instance_id, restore_epoch, schema_version |
| projects / plans | project title/state; plan revision/content reference/scope; approved source and actor |
| tasks / dependencies | project/plan revision; recipient, ask, done_means, inputs, return; state, revision, generation, attempts |
| claims | task, run, runner, attempt, generation, restore_epoch, lease_until, state; unique active claim per task |
| runs | task/claim, attempt, request_id, model/rules revision, started_at, ended_at, deadline_at; exit_status nullable; closeout payload/validation; containment status/evidence; usage state/units/estimate/actual charge/provenance |
| decisions | project/plan revision, intended_subject, expires_at, state, consumed_at, action/source; replay identity; no bearer secret |
| notices | project/task, sender, named recipient, kind, payload reference, acknowledgement |
| role_grants | agent, model family/version, role, granted_by, state/revision; changed model pauses grant |
| incidents / incident_attempts | one incident per task; attempt/run linkage; recovered/escalated state and evidence |
| scorecard_events | agent, kind, source run/review, recorded_at; unique source/kind for repeat-safe counts |
| audit_events | immutable sequence, actor, entity/action, UTC time, before/after references |

Ruling: use a new `hearth2.sqlite3` rather than extending `work.sqlite3`, because
that satisfies the approved isolation decision and preserves Hearth 1 behavior.
Cost if wrong: later integration needs an explicit adapter, not shared tables.

## Task 1: Versioned schema and safe lifecycle

**Files:** schema.py, migration pair, test_hearth2_schema.py.
**Interfaces:** `Schema.initialize(path: Path, *, enabled: bool) -> None`;
`Schema.migrate(path: Path, target: int, *, backup_path: Path) -> None`.

- [ ] Write failing tests: disabled initialization leaves the directory untouched;
  enabled initialization creates version 1; reopening does not change rows;
  unknown newer version/checksum mismatch is refused. Add foreign-key tests and
  fault-injection proving a failed migration leaves the old version and rows intact.
- [ ] Run `python3 -m unittest discover -s test -p test_hearth2_schema.py -v`;
  observe the intended missing implementation failures.
- [ ] Implement explicit startup migrations with `foreign_keys=ON`, bounded busy
  timeout and `BEGIN IMMEDIATE`; never run DDL on ordinary reads. Version 0 has
  no operational schema. A populated v1→0 downgrade refuses destructive deletion;
  tested way back is restore of a consistent pre-migration backup while stopped.
- [ ] Re-run tests; verify empty forward/back/re-forward plus populated backup
  restoration and exact relationship equality. Commit only these files.

## Task 2: Records, approval boundaries and audit

**Files:** store.py, test_hearth2_store.py.
**Consumes:** task 1 schema.
**Produces:** `Store(path, *, clock)`; `create_project(actor, payload) -> dict`;
`create_plan(actor, project_id, payload) -> dict`; `create_task(actor, payload) -> dict`;
`record_decision(principal, decision_id, expected_revision, action, source) -> dict`;
`set_role(human_principal, agent, payload) -> dict`; `snapshot(project_id=None) -> dict`.
Caller principals come from authenticated transport, never a payload actor field.

- [ ] Write failing tests: five required task fields, cross-project dependency
  rejected, cycles rejected, stale revision rejected, agent cannot approve a plan,
  only intended human subject consumes an unexpired decision for that exact plan
  revision; second press is audited rejection without reapplying the action.
- [ ] Test that model change pauses the role; producer closeout cannot accept a
  deliverable; rejected mutations leave domain state intact and record the
  rejection separately when security auditing is required. Thread/card cutover
  state is explicit; no chat parser grants authority here.
- [ ] Run `python3 -m unittest discover -s test -p test_hearth2_store.py -v`; RED.
- [ ] Implement minimal transactional methods and record shape above. Human
  authentication/cutover UI belongs to piece 5; store guards are tested now.
- [ ] Re-run GREEN; commit. Do not seed the real rollout project yet.

## Task 3: Atomic claims, fencing and safe recovery holds

**Files:** store.py, test_hearth2_claims.py.
**Consumes:** approved task and active role from task 2.
**Produces:** `claim(runner, task_id, *, expected_revision, request_id) -> Claim`;
`renew(runner, claim, *, lease_until) -> Claim`;
`record_run(runner, claim, receipt) -> dict`;
`reconcile(controller, run_id, *, termination_evidence, outcome) -> dict`.
Claim is `(task_id, run_id, attempt, generation, restore_epoch, lease_until)`;
identity is not a reusable exportable bearer credential.

- [ ] Write a real two-process barrier race test for A5; assert one success, one
  conflict, one claim/run/attempt increment and one successful-claim audit.
- [ ] Write stale same-agent, old epoch, old attempt, expired lease and idempotent
  request retry tests for every mutating runner method. A conflicting request ID
  must not alias another task. Role/plan revision checks happen inside the claim
  transaction, including the changed-model case.
- [ ] Write recovery tests: expiry makes writes invalid but does not make task
  claimable; unknown termination keeps it held; trusted verified-stop evidence
  permits reconciliation. Three failed attempts prohibit a fourth; one incident
  retains all three attempts and may later be marked recovered without erasure.
- [ ] Run `python3 -m unittest discover -s test -p test_hearth2_claims.py -v`; RED.
- [ ] Implement conditional transitions under write lock with a partial unique
  active-claim index. Define trusted controller transport separately from workers;
  no worker-supplied `terminated=true` is sufficient for controller authority.
- [ ] Re-run GREEN; commit. This proves record fencing, not that a process died.

## Task 4: Run, decision and notice contract completeness

**Files:** store.py, test_hearth2_store.py.
**Consumes:** task 3's fenced writes.
**Produces:** `append_notice(actor, payload) -> dict`;
`record_review(reviewer, task_id, expected_revision, verdict, evidence) -> dict`;
`accept_result(human_principal, task_id, expected_revision, evidence) -> dict`.

- [ ] Write failing fixtures for missing end/exit/closeout/termination/usage;
  unknown usage stays null plus status unknown; zero is accepted only with a
  measured receipt. Enforce deadline greater than start and aware timestamps.
- [ ] Test done output still awaits independent review and any required human
  acceptance; same-family review does not satisfy family independence; stale
  generation cannot add output notices/counts. Deduplicate counts by source.
- [ ] Run task-2 and task-3 test commands; observe new RED cases.
- [ ] Implement shape validation without accepting Cloudroom completion as a
  complete Hearth receipt. Keep actual seat charge and estimate distinct.
- [ ] Re-run GREEN; commit.

## Task 5: Versioned export, clean restore and A11 reconciliation

**Files:** backup.py, test_hearth2_backup.py.
**Consumes:** task-1 schema and task-4 complete records.
**Produces:** `export_record(source: Path, destination: Path) -> Manifest`;
`restore_record(bundle: Path, target: Path, *, controller_stopped: bool) -> Report`.

- [ ] Write complete fixture graph with an active run, expired/pending decisions,
  notices, grants, incidents and counts. Assert round-trip IDs/links, FK integrity
  and no authentication/claim secrets in bundle. Add unknown format/schema,
  duplicate IDs, corrupted digest, truncated bundle and dangling-link failures.
- [ ] Add concurrent export/writer test; populated-target refusal; injected
  restore crash; same-source restore conflict; backup containing a secret-bearing
  field rejected with a field path only (do not print the secret).
- [ ] Run `python3 -m unittest discover -s test -p test_hearth2_backup.py -v`; RED.
- [ ] Export logical whitelisted rows from one SQLite snapshot into a local
  versioned bundle: manifest format/schema/source revision, export UTC, table
  counts, canonical JSON SHA-256 and source instance identity. No filesystem
  paths from the bundle are interpreted as output paths. Digest is corruption
  detection, not proof of authenticity. Treat imported strings as untrusted.
- [ ] Restore to a new staged DB; validate version, row limits, references and
  checksums; commit/fsync then publish exclusively to an absent destination.
  Require stopped-controller operation. Set a new restore epoch, fence all old
  claims, mark active runs/tasks reconciliation-required, preserve original
  receipts and audit why. Do not recreate cookies, credentials or broker grants.
  Pending approvals are held until the intended human and exact revision are
  rebound; consumed/expired decisions never become usable again.
- [ ] Run restore in a separate process and compare entire fixture graph plus
  explicit state changes; record these as local A11 evidence. Commit GREEN.

## Task 6: Default-off service wiring and trial acceptance package

**Files:** app.py, Dockerfile, test_hearth2_api.py, OPERATIONS.md.
**Consumes:** store and backup APIs above.
**Produces:** `HEARTH2_ENABLED=false` by default; enabled startup under the trial
instance's data directory; authenticated `/api/hearth2/*` routes with existing
CSRF policy plus explicit management/controller/worker capabilities.

- [ ] Write failing tests: disabled service touches no H2 path; existing H1
  routes/export are unchanged; anonymous/reviewer workers cannot mutate, export
  or restore; actor/identity payload spoofing refused. Restore is an offline
  operator command, not a worker-accessible HTTP action.
- [ ] Run `python3 -m unittest discover -s test -p test_hearth2_api.py -v`; RED.
- [ ] Wire only trial-gated lifecycle/routes; no default production activation,
  token provisioning, Google sign-in changes or UI redesign. Operations guide
  provides exact trial commands after live paths/version are verified.
- [ ] Run all `test_hearth2_*.py` plus existing `test_work.py` and applicable auth,
  API, Docker packaging checks. Report prerequisites that cannot run locally.
- [ ] On the trial host only, repeat A5 and A11 in a clean directory/process,
  verify migration way-back and compare Hearth 1 behavior/data evidence from
  read-only checks. Post [REVIEW] to the existing thread only through an
  authorized communication route. Claude provides independent PASS/changes.

## Resume and completion

The next executable action is step 0 item 5 using an already authorized SSH
route, not application Task 1 and not a repeat human build approval. The 3–4
engineering-day piece-1 estimate stays provisional until that live evidence is
known. If live Cloudroom fields differ, update the adapter mapping and ledger;
do not silently change the approved requirements. No seven-night test begins
until all pieces run together.


## Execution amendments, 28 October

Read `docs/hearth2/PREFLIGHT.md` and `PROGRESS.md` for observed results. Live
access and all six questions are now resolved as pre-build findings. The
implementation adds an immutable action manifest to bind authority and typed
output/reviewed/accepted dependency gates to preserve A10. Requested revisions
have one controlled resubmission path; a second changes verdict stays a human
disagreement. Verified termination of a held successful receipt permits review
without repeating work. Restore validates domain consistency as well as FKs and
a digest. These changes address whole-branch review findings; no runner, model
launch, production activation or seven-night PASS is implied.
