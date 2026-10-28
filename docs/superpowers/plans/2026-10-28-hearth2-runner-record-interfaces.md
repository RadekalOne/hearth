# Hearth 2 runner record interfaces implementation plan

> **For agentic workers:** Use superpowers:executing-plans to implement this plan task by task.

**Goal:** Supply the record interfaces required by the approved piece-2 handoff before building its runner.

**Architecture:** Extend the existing authenticated record, keeping operational data separate from knowledge. Human answers live in task data plus immutable audit events. Runner ticks and standalone control failures use typed events in the existing transactional journal, with server time, epoch, compare-and-swap and idempotent request IDs. No SQL layout changes are needed; schema and backup remain version 1.

**Tech stack:** Python, SQLite, FastAPI, unittest.

**Spec:** Approved Hearth 2 slice and piece-2 handoff, continuing `docs/hearth2/PIECE-1-SPEC.md` and the HC review thread. This is an implementation detail under that authority, not an additional gate approval.

## Constraints and design calls

- Trial instance only; production, native models, credentials and deployment unchanged.
- Preserve task manifest, attempt count, immutable prior runs, independent review and human merge gate.
- Only the approving human can answer a current verified `needs-decision` run. A second review disagreement cannot use this route.
- Defaults remain 900-second lease and 7200-second deadline. Positive integer settings may shorten either for tests, but cannot increase the approved two-hour run ceiling. A lease never extends past its run deadline.
- Append-only operational journal avoids a redundant mutable heartbeat table and a schema migration. Projection readers return epoch and server timestamp; old-epoch ticks are not current liveness after restore. Previous failures remain historical evidence.
- Standalone failures cover missed start, runner stale, and dispatch blocked. They never invent a run, use an attempt, reset an incident, requeue work or prove recovery by a heartbeat. Explicit evidence is required to resolve them.

## Review focus

Stale/double human answers; held or unknown-exit runs; altered approval and review disagreement; tick replay after restore or out of order; failure recording without a real launch. Tests below exercise each.

## Task 1: Human answer and timing

- [x] Write and observe failing tests for exact human/run/revision binding, unchanged inputs and counters, duplicate/stale rejection, review bypass rejection, and short timings.
- [x] Implement `answer_task` and configuration bounds; add authenticated route and default-off configuration parsing.
- [x] Verify valid answered work survives export/restore; damaged ready-with-unanswered-request bundles are rejected.

## Task 2: Operational journal

- [x] Write and observe failing tests for restart persistence, idempotence without timestamp refresh, CAS conflicts, authorization, epoch separation and no fictitious runs.
- [x] Implement typed tick/failure append and projection with controller-only writes and management-only reads.
- [x] Verify audit transaction rollback and export/restore preserve historical evidence while invalidating liveness.

## Task 3: Reviewable delivery

- [x] Exercise real application auth/routes plus complete Python suite in isolated trial containers.
- [ ] Document contracts and verification limitations; review exact signed commit, open draft PR and post exact-commit review request directly to Claude in the authorized thread.
- [ ] Save and read back a Hearth Memory outcome and own checkpoint. Wait for independent review and Rad's merge gate before runner consumers depend on this PR.
