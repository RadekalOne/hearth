# Hearth 2 piece 1 preparation ledger

Plan: `docs/superpowers/plans/2026-10-27-hearth2-work-record.md`.

27 October 2026:
- Read canonical HM plan section, piece-1 handoff, isolation decision, approved
  agent rules v1.0, current repository source and migration/export/auth paths.
- Original worktrees contain unrelated edits; created a clean managed worktree
  at origin/main d04ea3d74e2409cbe0ba30410c30b01ce3727d4f; no originals changed.
- Existing H1 store regression command: `python3 -m unittest discover -s test
  -p test_work.py -v` -> 16 tests PASS. This is baseline evidence only.
- Trial SSH existing desktop identity rejected under strict host-key checking.
  Both registered Desktop Commander devices offline. No working alternate route
  located; no credentials, SSH keys, host permissions or production changed.
- Prepared source contract, interfaces, schema map, test-first implementation
  steps and A11 recovery rules. Application implementation tasks 1–6 NOT STARTED.
- Pre-flight: claims/runs feed export; restore must advance epoch before any
  old writer is accepted. Decision rows feed cards later; stored expiry is not
  phone identity verification. Notices/counts are fenced alongside closeouts.
- Ruling: separate H2 database in isolated trial memory-service instance instead
  of H1 work tables; required isolation favors preserving current semantics.
  Cost if wrong: later integration needs an adapter.
- Ruling: pending approvals restore held for human identity/revision rebinding;
  preserves intent as history without making an imported approval usable.
  Cost if wrong: an operator must explicitly reconcile extra pending cards.
- Pre-build Step 0 item 5 remains OPEN; no [VERIFY] PASS, no trial instance,
  no claimed task, no provider launch, no independent review requested.
- No new infrastructure/provider purchase made. Session seat usage/cost not
  measured; do not describe total engineering cost as zero.

28 October 2026:
- Rad installed the desktop public key on trial through the Hostinger console.
  Strict SSH succeeds and host identity matches the intended trial.
- Completed read-only live inspection; see PREFLIGHT.md for six-item findings.
  Cloudroom pinned 0.1.58 is active/loopback-only and authenticated health/ready
  respond200. Native accounts connected; no provider prompt launched. Worker
  cannot access core environment or Docker socket and lacks sudo. Catalog
  advertises gpt-6.1-sol; actual unattended compatibility untested.
- Live-check access blocker resolved. Task1 may start; execution gates for
  launching agents are not represented as passed by this preflight.
- Task1 implemented: explicit v1 schema, default-off initialization, checksum/
  version refusal, foreign-database refusal, atomic DDL, exclusive backup and
  loss-refusing down migration. Seven real SQLite tests observed RED then GREEN.
  Nonempty downgrade intentionally requires offline backup restoration.
