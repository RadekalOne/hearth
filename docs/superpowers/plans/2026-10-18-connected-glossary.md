# Connected Glossary Implementation Plan

> Use superpowers:executing-plans inline, preserving the current isolated worktree and dirty runtime checkouts.

**Goal:** Prepare one live glossary shared by the browser and authenticated agent tools.

**Architecture:** Extend the existing Commons adapter with a verified per-turn bridge; stage hash-bound runtime candidates. Reuse the existing hub, credentials, model loops and MiniMax CLI.

**Spec:** ../../commons-contributions/CONNECTED-DESIGN.md

**Constraints:** No new services, credentials, provider changes, model probes, room posts or Cloudroom changes. No live activation before the concrete release gate. Never impersonate requester-authored content.

## Tasks

- [ ] Add failing bridge tests for verified human/direct mention/room/command gates, ambient denial, stable host IDs and independently reported receipts. Implement the smallest bridge and rerun.
- [ ] Add failing structured Mavis-loop tests for malformed JSON, unknown operation, six-operation limit, one write, error receipts and no unsolicited post. Implement CLI driver using existing MiniMax interface; test with injected completions and real store fixtures.
- [ ] Generate exact-hash candidates for Kimi/GLM, Hy4 and Mavis. Route glossary tools before existing history handlers; preserve ambient behavior and provider policy. Exercise candidate tool loops without model requests.
- [ ] Update source help, dashboard link and live release/access/rollback review. Verify browser, server, packaging and CI; request independent code review and resolve significant findings.
- [ ] Prepare exact release with current production image and backup/rollback procedure. Present final concrete production/access approval after the build is reviewable.

## Review focus

Forged environment body differs from verified event; quoted commands; ambient direct mentions; repeated lost responses; partial runtime drift; MiniMax output that claims a save without a validated receipt; duplicate tool names; human session enrollment differing from agent tokens.
