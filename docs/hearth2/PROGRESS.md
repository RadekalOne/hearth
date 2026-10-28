# Hearth 2 piece 1 preparation ledger

Plan: `docs/superpowers/plans/2026-10-27-hearth2-work-record.md`.

## Piece 2 prerequisite record interfaces (28 October)

PR35 follow-up review: Claude independently reproduced acceptance of an old
in-flight failure recovery after restore. The follow-up requires the caller's
`expected_epoch` in failure writes and checks it before replay/CAS, matching the
tick fence. A real export/restore regression now checks rejected stale recovery,
unchanged history, then a valid fresh-epoch recovery. HTTP tests check missing
and wrong epochs. The two small findings use the reviewer-offered documentation
resolution: the configured-controller allowlist is an HTTP API policy, and only
latest-event/current-epoch failure replay is idempotent; older-event replay fails
closed and is now tested. Independent exact-commit re-review remains required.

PR34 merged into main at `5e892f905ebb0101dca6f9532663ffcc273545ad`, containing
Claude's exact passed commit `2ec3c49290174a3f5d1e6a8d5492a45b175ed3c7`;
piece 1 is verified. Piece 2 is started under the existing slice approval.
The six-point pre-build verification was posted and read back in the existing
HC review thread. Rad explicitly authorized direct project coordination there.
Claude responded with no interface objection, requesting a stale-card check and
an explicit outside wait for usage-page evidence; both are included.

The prerequisite implementation adds a human-answer transition, typed controller
ticks/standalone failures in the existing journal, and bounded timing settings.
See `RUNNER-RECORD-INTERFACES.md` and the 28 October implementation plan.
No schema DDL changed; v1 export includes the complete journal and answer history.
Internal read-only review found two regressions (old tick replay after restore,
and overstrict export validation of an unknown-exit reconciled failure); both
were independently reproduced and corrected. This is not Claude's PASS.

Current usage/seat charges remain unknown. Current usage-page evidence is an
outside wait before live acceptance and is excluded from the provisional 6–9
engineering days. Runner, broker, containment and real-model acceptance are not
delivered by this prerequisite. No native prompts, production deployment or
account/configuration changes were made. Independent exact-commit review and
Rad's merge gate remain open.

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
- Tasks2–6 implemented in the isolated branch: immutable plan action manifests,
  explicit dependency gates, records/roles/expiring decisions, atomic claims and
  generation/epoch fences, three-attempt incident history, run evidence,
  independent review and human acceptance, versioned logical backup/restore,
  offline CLI and default-off authenticated REST integration. No UI or runner.
- Initial service verification had environment failures (WSL missing httpx/MCP;
  first isolated Python image omitted Git required by existing Commons tests).
  Installed dependencies/Git only inside a disposable trial verification image.
  Final Python3.12 run on the trial host: 336 tests PASS in86.172s.
- Node24 check/test on the trial host:35 PASS,1 pre-existing skip,0 FAIL.
  Packaging dry run includes Hearth2 schema, API and both migration files. An
  initial packaging assertion had a shell quoting error; corrected standalone
  package verification succeeds. No production install or dependencies changed.
- Whole-branch read-only code review (Codex; NOT Claude's independent project
  PASS) found three Important issues: unbound task scope, no revision path,
  and no successful-held reconciliation. All reproduced RED and corrected GREEN.
  Added regression for stale-plan result acceptance as well.
- Review's restore-domain gap was treated as Important: reject inconsistent
  accepted tasks/claim/run histories even when a bundle's digest is recomputed.
  The impossible-accepted-task reproduction is now GREEN.
- Ruling: bind approval to an immutable action manifest; materialize each action
  once with its exact handoff/dependency gates. Required by bounded authority.
  Cost if wrong: planners must revise their plan to change/add action slots.
- Ruling: dependency gates distinguish output, independent review, human
  acceptance. Feasibility review consumes output directly, preserving A10's
  unattended path. This corrects the earlier blanket accepted-dependency rule.
  Cost if wrong: an incorrectly selected gate can block a downstream task; the
  gate is therefore visible in and bound by the approved action manifest.
- Reviewer set aside runtime subscription/process enforcement, canonical Claude
  independence and deployment: those are not inferred from record tests.
  General secrets in prose cannot be excluded by a heuristic; export validates
  known credential fields/patterns but is not a general DLP guarantee.
- Ruling: no extra secret-detection subsystem in this slice. Keep private backup
  handling and explicit bundle provenance; do not call heuristics exhaustive.
  Cost if wrong: an operator must detect/remove an unrecognized prose secret.
- Independent Claude review and fresh-container live service restore evidence
  remain required before piece1 is called verified. Pieces2–5 remain unassigned.
- Final A11 drill now complete on the trial host: separate clean restore
  container compared every table/link, refused the old claim, held active work
  and pending approval. A further container booted the actual restored service
  with fresh credentials; auth, build identity and credential-free re-export
  passed. Temporary fixture service removed afterward; no model launched.
  This is fresh-container evidence, not a new-VM or independent-Claude PASS.
- Actual Dockerfile build passed, tested application commit004b4c2200cd2a12a022331d264d7d5bd9e4597d.
  Initial unsigned pushes were rejected by GitHub's signature rule; used the
  existing Windows signing key and identity to sign only our unpublished
  commits, verified identical source tree, then pushed successfully. No rule,
  global Git config or GitHub credential/key registration changed.
- Draft PR33 created and attached: https://github.com/RadekalOne/hearth/pull/33.
  Piece1 IMPLEMENTED/READY FOR REVIEW, not VERIFIED. Claude review has not been
  requested through HC by this session; no agent messages or runtime launches.
  Pieces2–5 remain unassigned. Production services/schema/schedules unchanged.

28 October — independent Claude review follow-up:
- PR33 was merged by Rad, but Claude returned4changes, not PASS, in the review
  thread. Read and verified both full posts and their HM review record.
- Implemented all4 in one scoped follow-up: draft revisions no longer revoke
  task-bound approval; replacement approval explicitly supersedes; human waits
  and unknown exits never auto-retry; reconciliation preserves receipt end;
  strict integer revision, sanitized source metadata and live-only claim replay.
- Fourteen focused regressions pass. Findings1–3 observed RED→GREEN; minor fixes
  and delayed-containment variants also reproduced before their fixes. Initial
  regression expectations that treated drafts as supersession were corrected to
  require a human-approved replacement. One stale closed-claim fixture corrected.
- Full trial Python suite350PASS in85.190s; Node35PASS/1existing skip, syntax,
  compilation and whitespace checks pass. No schema DDL or runtime deployment.
- Follow-up remains unmerged for Claude's exact-commit review. No piece2 start,
  production change or new build approval needed. See PR33-REVIEW-FIXES.md.
