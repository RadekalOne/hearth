# Hearth relay live adapters implementation plan

> Use superpowers:executing-plans for inline implementation and one final fresh review. No implementation delegation.

**Goal:** replace relay intake/allowance/launch stubs with concrete bounded adapters, retaining explicit financial and activation gates.
**Architecture:** stdlib Matrix transport + durable event staging; pinned native stdio collector/one-attempt proposal launcher; existing relay dispatch/pause state remains authority.
**Tech stack:** Python stdlib, Windows Job Objects, existing Matrix and Codex0.164.0, existing trial test container; no new app/SDK/API-key route.
**Spec:** docs/superpowers/specs/2026-11-13-hearth-relay-live-adapters.md

## Global constraints

Keep installed task disabled and paused; no model turn, paid call, reset/purchase, account/config mutation, merge/deploy or production change. Read-only live coordination/account metadata is allowed. Use existing dedicated native checkout RSLABINSKI-PC. No broad Hearth credential in a child. Explicit scoped paid approval and verified spend route required before inference; current scope has neither. Existing gpt-6.1-sol identity retained; Linux0.159.1 unchanged. Missing live proof is reported, never promoted from fixtures.

## Tasks

- [ ] 1. `relay_matrix.py` + `test_relay_matrix.py`: bounded fixed-origin HTTPS, existing env-file reader, server identity/event/thread checks, strict JSON approval envelope, durable cursor+pending staging; live GET-only receipt. RED -> GREEN; reject other room/sender/thread, edit/redaction, missing cursor, gap, transport failure, duplicate/conflicting task events.
- [ ] 2. `relay_native.py` + `test_relay_native.py`: pinned native artifact, fresh minimal home/env, bounded stdio/control methods, read-only account/rates/model observation, sanitized receipts, verified cleanup. RED -> GREEN; API-key/fallback/unknown/stale/exhausted limits refuse; no refresh or turn call during diagnostics. Separate capacity from billing authority.
- [ ] 3. `relay_launch.py` / process keeper and `test_relay_launch.py`: exact approved work/one-attempt send fence, closed financial gate, bounded tool-free proposal execution, isolated snapshot and scope/base-hash validation, fixed network-none test execution, stop proof, held unknown. Positive end-to-end uses fake native/provider only; no actual inference.
- [ ] 4. `relay_live.py`, HostPorts/installer/read-only diagnostic CLI wiring and tests. Hash-bind configuration/modules and keep paused installation. Actual manual live intake + native metadata receipts, no room post or worker turn. Full canonical-source offline suite; one fresh review/fix pass; source/evidence feature branch + Claude handoff; remote HM checkpoint/outcome/readback.

## Review focus

Cursor advance never loses eligible work; identity text is not authority. No downgrade from missing financial proof to a caller assertion. Malformed/slow native streams never bypass pause or leak credentials. Original epoch/deadline and one-attempt accounting survive failure. No host execution of modified repository tests, and no model-selected paths/commands/credentials.


## Activation amendment and delivered boundary
Rad subsequently authorized enabling the relay. Keep it paused during build/review, then enable ONLY verified intake/capacity mode after read-only live preflight. Preserve the existing hourly 07:00-23:00 ET schedule, interactive-user requirement, no wake/catch-up, independent Pause button, audit and inactive900s/full-run policy. Scheduler-enabled does not prove execution; record an actual scheduler run separately.

The pinned native schema cannot establish a server-enforced included-only monetary boundary. Therefore this increment does not deliver an operative unattended model launcher: real turns remain blocked, approved generations stay pending/unclaimed, and the positive proposal protocol is explicitly a credential-free fixture. No fake paid permit, caller boolean or human budget can turn quota into financial enforcement. Activation is intake/capacity only, not an autonomous coding loop. Completing actual model execution requires a separately reviewed financial authority/route design and scoped Rad APPROVED. This is an explicit outstanding requirement, not a passed gate.
