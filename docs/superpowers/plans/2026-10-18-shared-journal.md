# Shared Journal Implementation Plan

Execute inline with superpowers:executing-plans. Spec: ../../commons-contributions/JOURNAL-DESIGN.md.

- [x] Real-store tests first: immutable prediction, separate reviewer/outcome, unknown cause, failed predictions preserved, retries, invalid dates/parents/identity.
- [x] Implement typed journal module and authenticated HTTP/MCP routes; verify existing reviewer denial and package/image inclusion.
- [x] Build browser form/list/read flow preserving the local prototype; test reload, two-account outcome, original preservation, retries and accessibility.
- [x] Extend runtime bridge/structured Mavis transport for journal commands; test bounds, author receipts and ambient denial; stage current active runtime candidates.
- [ ] Independent review; resolve significant findings; full appropriate checks, draft PR and exact release/access/rollback review. No production change without the concrete gate.

## October 18 correction: interactive adoption

The service/UI and optional runner bridge are implemented in PR31; review and ten CI jobs passed at code commit ef5cac7. The earlier runner-first release is superseded for adoption. Follow [the interactive plan](../../commons-contributions/JOURNAL-INTERACTIVE.md):

- [ ] Inventory Mavis's actual interactive client/workspace and authenticated Hearth path; separately map Codex, Kimi, GLM and Hy4 without assuming runner parity.
- [ ] Prepare the hub-only release gate and verify journal tool access in the interactive clients after activation. Keep the 14 Connected runtime candidates out of the default release.
- [ ] Install reviewed additive startup guidance and work-handoff continuity in each verified interactive client; shared Memory guidance must actually be retrieved.
- [ ] Demonstrate Mavis's prospective prediction in real interactive work, an independently authored sourced outcome, and fresh-session retrieval without a special Rad journal prompt.
- [ ] Obtain Mavis's assessment; report each participant's adoption separately. No background execution, automation or runner acknowledgement counts as this proof.
