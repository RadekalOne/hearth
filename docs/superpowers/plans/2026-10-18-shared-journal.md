# Shared Journal Implementation Plan

Execute inline with superpowers:executing-plans. Spec: ../../commons-contributions/JOURNAL-DESIGN.md.

- [x] Real-store tests first: immutable prediction, separate reviewer/outcome, unknown cause, failed predictions preserved, retries, invalid dates/parents/identity.
- [x] Implement typed journal module and authenticated HTTP/MCP routes; verify existing reviewer denial and package/image inclusion.
- [x] Build browser form/list/read flow preserving the local prototype; test reload, two-account outcome, original preservation, retries and accessibility.
- [x] Extend runtime bridge/structured Mavis transport for journal commands; test bounds, author receipts and ambient denial; stage current active runtime candidates.
- [ ] Independent review; resolve significant findings; full appropriate checks, draft PR and exact release/access/rollback review. No production change without the concrete gate.
