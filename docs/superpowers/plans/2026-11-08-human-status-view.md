# Human Status View Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: use superpowers:executing-plans,
> inline implementation with TDD and one fresh final read-only review.

**Goal:** Show honest notice delivery and controller poll states with evidence.
**Architecture:** One transactional allowlisted read model, protected JSON and
server-rendered HTML routes, optional explicit timing configuration.
**Tech Stack:** Existing Python 3.12/FastAPI/SQLite, stdlib HTML; no dependency.
**Spec:** docs/superpowers/specs/2026-11-08-human-status-view-design.md.

## Global Constraints

- Verify RSLABINSKI-PC; use C:\Users\rslabinski\Projects\hearth2-transfer and
  existing codex/hearth2-minimax-consumer-parser branch, BASE a2d4fea.
- Synthetic temporary stores only. No production/native/provider/credential/
  room/service/automation changes. 900-second/full-run runtime remains inactive.
- Preserve private history/workspace; signed local commits, no push or merge.

## Review Focus

1. Forged delivery metadata or a fresh tick must not imply receipt/comprehension.
2. Missing/future/old-epoch ticks or absent timing policy must not show recent.
3. Read-only view must not leak claim/run/auth data or cross-project notices.
4. HTML/evidence content cannot execute scripts or external URLs.
5. Disabled or invalid config must not create/open the operational database.

## Task 1: Read model, configuration and protected JSON

Files: new mcp/memory/hearth2/human_status.py; modify control.py, api.py and
app.py; new test/test_hearth2_human_status.py.
Consumes: existing tasks/notices/control journal and server clock. Produces:
human_status(store, controllers, expectations, project_id=None) -> allowlisted
dictionary, and validated per-controller poll timing config. Factor journal
snapshot-in-transaction without changing existing control endpoint semantics.

- [x] Write missing-module/route RED tests for exact boundary, replay, unknowns,
  failure persistence, restore, notice metadata, roles and project filtering.
- [x] Run tests, verify expected failures before code.
- [x] Implement read model and strict config; add GET /api/hearth2/status.
- [x] Run GREEN focused status + existing control/config/API acceptance tests.

## Task 2: Human page and evidence acceptance

Files: new mcp/memory/hearth2/status_page.py; modify api.py; extend status tests;
new docs/hearth2/HUMAN-STATUS-VIEW.md.
Consumes: Task1 read model. Produces: escaped responsive HTML at
GET /api/hearth2/status/view with native evidence details and refresh link.

- [x] Write RED route/escape/no-store/CSP and real HTTP workflow assertions.
- [x] Implement semantic HTML, status labels, timestamps, explicit unknowns and
  separate unresolved/historical failures; no action forms or scripts.
- [x] GREEN focused tests; render real synthetic response for browser inspection.
- [x] One fresh final review; no findings or fix pass required.
- [x] Immutable full suite with external networking disabled, byte equality,
  signed local commit and remote HM outcome/checkpoint search/write/readback.

Pre-flight: Task1 JSON is the sole Task2 rendering input. Shared record reads
must use one transaction and one server observation time, no client clock.
