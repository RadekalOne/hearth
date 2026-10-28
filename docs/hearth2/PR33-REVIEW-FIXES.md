# PR33 independent-review follow-up

Base: merged PR33, `64ff5bf0eb9a0500e7d54dc0e3b15e3aa5e7cfe7`.
Claude's 28 October verdict was **4 changes, not PASS**. Piece 2 remains on hold
until Claude re-reviews the follow-up's exact commit. No production activation,
runner installation, model/provider prompt, schema DDL or credential change is
part of these fixes.

## Changes and reproductions

1. **Plan eligibility:** a task remains bound to its own approved plan and its
   approved action manifest. Creating a draft does not revoke the existing
   approval, freeze renew/receipt/acceptance, or consume another launch. Only
   approving a replacement transitions the previous approved plan to
   `superseded`, with an audit event. Old cards still fail the latest-revision
   check. Backups retain and validate superseded approval history.
2. **Human waits and uncertain outcomes:** a valid `needs-decision` closeout with
   a known exit and verified containment enters `needs_decision`; its request is
   preserved and a clean human wait creates no failure incident or automatic
   retry. A nonzero exit still has an escalated incident, without retrying the
   human request. An unknown exit or unconfirmed containment enters `held` and
   must be reconciled. Existing run ordinals remain factual history: one process
   launch stays one recorded run, never renumbered or erased. No new retry is
   queued or failure attempt registered for the clean human wait. The existing
   three-launch safety limit remains unchanged.
3. **Receipt end time:** reconciliation keeps an existing `ended_at`. Its own
   observation time is stored as `termination_evidence.reconciled_at`; if no end
   was ever recorded, the controller's verified-stop time fills the missing end.
4. **Robustness:** revision arguments require actual integers; missing source
   identity/epoch metadata is refused inside the sanitized bundle reader; an
   idempotent claim replay must still pass the complete live-claim checks.
   Closed, held, expired and superseded work cannot be returned as launchable.

`test/test_hearth2_claude_review.py` directly reproduces these findings. Against
merged PR33, 12 tests yielded 9 failures, 2 errors (the frozen renew/acceptance),
and 1 passing existing stale-card guard. The new tests for changes 1–3 were
observed failing before code changes and passing afterward. The same file also
reproduces all three minor issues. The original negative tests now approve a
replacement before asserting supersession; a draft alone is deliberately safe.
An old receipt fixture was corrected to stop replaying an already closed claim
when its loop had no remaining run to execute.

No new withdrawal control is added: Ask on an unapproved draft changes that
proposal, and does not revoke an older approved plan. Approval supersession is
an explicit human decision; frontend withdrawal remains outside this slice.

Independent re-review remains mandatory. Passing tests do not constitute
Claude's PASS and do not authorize deployment or piece 2.

A scoped read-only code review also caught the delayed-containment variant of
change 2: a human request first held for uncertain containment must stay a human
wait when stop is later verified. Two more regressions were observed failing,
then passing: completed reconciliation now preserves the human wait, and failed
reconciliation cannot blindly retry the preserved request. The final focused
regression file has 14 passing tests. This internal check is not Claude's PASS.

## Final verification

- Full Python 3.12 suite in the isolated trial verification container: **350
  passed**, 85.190 seconds.
- Focused Claude-review regressions: **14 passed**, following the recorded
  failing reproductions.
- Node syntax checks and suite: **35 passed, 1 existing skip, 0 failures**.
- Python compilation and staged whitespace checks passed.
- No runtime deployment, schema migration, live workload, production change or
  new purchase. Only source/tests ran in disposable trial verification containers.

Claude should review the exact follow-up commit before it is merged. Piece 1
remains not verified and piece 2 remains unassigned pending that PASS.
