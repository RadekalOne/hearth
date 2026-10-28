# Hearth 2 piece 1: work record contract

Status: preparation only, 27 October 2026. This document carries the approved
requirements into the implementation checkout; it is not a new approval or a
claim that the service exists.

## Authority and sources

- Gate 1: Rad's 23 October slice-build approval, recorded in
  `drawer_a29bc2b9cebf8bb5097caff839ff398a`.
- Canonical thin-slice section: `drawer_9c12d389f93ee60581bf4f6ab98d9553`,
  `drawer_de4500fa8ebbe1234f15c1425e7835a8`,
  `drawer_00a536731abb7ce648b05762c94193a5` (rev 67).
- Rev 68 erratum and isolation decision:
  `drawer_79d7cb7f1b17fe92818c28e0edde47fd`. An empty human inbox means no
  person has to act. It does not prove that nothing failed.
- Piece-1 handoff: `drawer_b9c510d262e45d2c35837e07c5997bdb`.
- Agent rules v1.0: `drawer_ca4ecafb568fbd47b592b4f0c0fc6ee3`, approved by
  Rad in `drawer_88da752326dd0500ded07b9ba42efd74`.
- Piece 7 is guide-text PASS only; no runtime or seven-night proof follows.
- Rad's 27 October instruction to continue as far as possible permits further
  work inside this scope. It does not waive the live pre-build check.

## Boundary

The work record runs in a separate trial instance of the memory service, with
its own data directory and credentials on the trial VPS. No production service,
knowledge records, credentials, schedules, or Hearth 1 board data change.
Any later production integration needs its own approval. The record does not
live inside Chroma's internal database. Existing Hearth 1 APIs retain behavior.

Piece 1 owns projects, tasks, dependencies, claims, runs, decisions, notices,
role grants, simple scorecard counts, operational audit and versioned backup.
It does not implement model execution, the broker, process containment,
supervision, reports, pushes, decision-card UI, or the Climate Central rollout.
Their record interfaces are defined here without claiming those systems work.

## Required behavior

1. A5: two independent runners race for one ready task; exactly one claim
   commits. Dependencies, assignment, role, plan approval and expected revision
   must hold at the same transaction as the claim.
2. Persist lease and fencing generation. Every runner mutation is bound to
   the exact live task/attempt/claim/generation. Expiry invalidates writes;
   expiry alone never requeues potentially live work.
3. A crashed or restored active run is held for reconciliation. Only trusted
   controller evidence that the old workload is stopped can release it.
   Unknown outcomes remain held. Piece 2 supplies actual termination evidence.
4. At most three attempts total. One task incident keeps every failed attempt;
   recovery does not erase it. Counts must not imply human action is required.
5. Every run has start, end, deadline, attempt and request identifiers, process
   exit status, independent containment/termination status and evidence,
   closeout plus validation result, rules/model revision and usage state.
   Unreported usage is unknown, not zero. List-price estimates and actual seat
   charges are separate nullable facts with provenance.
6. A decision records the exact plan revision, stable intended human identity,
   expiry, state, single-use consumption and audit. Do not accept typed chat
   as a card action after that project's cutover. Gate 1 releases only actions
   the approved plan explicitly covers; gate 2 accepts the result.
7. An agent-produced 'done' closeout does not itself make a task accepted or
   unblock reviewed-result dependencies. Dependency edges distinguish output
   available, independently reviewed, and human-accepted results; the feasibility
   review consumes output without an intermediate human prompt. Preserve producer,
   independent reviewer and human acceptance as distinct facts.
8. A11: export and restore projects, tasks, dependencies, claims, runs,
   decisions, notices, role grants, counts and audit with relationships intact.
   Active work is reconciled, never resumed. Backups contain no authentication,
   broker grants, provider keys, cookies or reusable claim secrets.
9. Migration versions have explicit forward and backward paths. Rollback is
   tested against nonempty fixtures without losing data; a destructive downgrade
   fails closed. A pre-migration operational backup is part of the way back.
10. Disabled startup creates or opens no Hearth 2 database. Enabling the trial
    path cannot mutate existing Hearth 1 stores. Exporting the work record does
    not silently change the existing drawer-only export contract.

## Acceptance evidence

- A5 race: separate processes, separate SQLite connections, synchronized start.
- Run/decision row contract checks, including missing/unknown outcomes.
- A11 clean-process restore, relationship comparisons and blocked active work.
- Migration forward/back/re-forward and injected failure rollback.
- Default-off tests and existing Hearth 1 work-store regression suite.
- Fresh-host trial execution and independent Claude review remain mandatory;
  local tests alone cannot mark piece 1 verified.
