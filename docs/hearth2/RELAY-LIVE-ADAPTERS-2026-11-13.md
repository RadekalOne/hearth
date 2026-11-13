# Relay live adapters — 13 November 2026

Current state: **paused, task disabled, no active processes**. Rad authorized enabling the relay, but his original acceptance condition also requires Claude's review of the evidence before enabling. That exact review is pending. No further Rad approval is needed for verified intake-only enablement once this condition is met. Model dispatch is a separate, still-closed gate.

Runtime: `9166cf761d87b2091d7e311760524e87179ca536`, based on `b4f23af`, branch `codex/hearth-relay-live-adapters`. SSH commit signature verified with a private per-command allowed-signers file derived from the existing public signing key; global configuration was not changed. [Evidence](evidence/relay-live-adapters-2026-11-13.json).

## Delivered and verified

- Fixed-origin authenticated Matrix intake for the existing Agent Tasks thread. Original Rad approval envelopes and Claude review sources are checked; bounded pagination, durable staging/cursor, deduplication, no whole-room replay or read-marker writes. Existing room prose does not acquire work authority.
- Pinned existing Windows Codex0.164.0 read-only account/model/quota collection. Fresh private home, selected access token passed in memory, no refresh or ordinary login/config mutation; process ownership is durably recorded before use and independent Pause can stop its named Job Object. The reviewed Linux0.159.1 client is unchanged.
- Capacity is distinct from financial authority. The observed account had7% used and no credits; this does not establish an included-only monetary boundary. Inference refuses, and pending work stays unclaimed.
- Bounded fake native proposal protocol, scoped/base-hash checked file proposals and durable one-attempt no-send records. These are **not an operative unattended coding launcher**. Real launch composition, supported financial enforcement, isolated candidate test execution and real-model acceptance remain open.
- Activation requires a server-authenticated Claude PASS for the exact installed manifest and `intake_capacity_only` mode, plus paused/no-active-work state and live diagnostic checks. Independent desktop Pause, history,17 hourly07:00–23:00 ET triggers and existing inactive900s/full-run policy are retained.

## Evidence and review

83 focused Windows tests pass. The final immutable source tree `924bfc799acee3a435ede324342cc23cc4e8ff43` passed **1,323/1,323** tests in122.428s in the credential-free network-none trial container, actual exit0. Archive SHA256: `dd6c2f171f50bb8548963b6d3ccd7b93e9d38ea3ce20d42426ad91af64f6e473`. Installed program/recovery hashes equal runtime Git blobs. All309 trial baseline files are unchanged; no test container remains; WSL stayed stopped.

One fresh independent source review found two Important issues: an unrecorded native process could escape Pause's accounting, and malformed metadata fields could leak nested credential-like values into receipts. Both were reproduced, fixed and verified. A separate actual Windows harmless-process test independently paused the recorded native Job and confirmed it empty. Unknown stop remains held across invocations; a paused diagnostic is explicit and never adopts a new epoch after Pause.

Claude's earlier pause review (`drawer_64c3c377451577966191a306c33bc60f`) is addressed for failed-latch text (`NOT set`), enabled status (`not_paused`) and the legacy PowerShell hostname precheck. Topmost/real human shortcut foreground confirmation remains unverified; it is not represented as a failed or passed observation.

## Premature enablement, then correction

A single intake/capacity-only scheduled invocation actually ran at23:07:12Z and exited0. Its read-only poll completed23:07:15.716Z, with no pending work, model turns0 and confirmed native cleanup. This was enabled before rechecking Rad's original condition: “before the task is enabled, with Claude’s review of its evidence” (Rad's Matrix event `$Q-2_qM8I8kkWJ3xPuKb34udvdXOmpzM0hi0W-fzOKVk`). The condition was missed; it is not treated as waived by the later enable request.

Independent Pause at23:09:12Z restored disabled/paused state, epoch20 and no active processes. The activation command now refuses a missing or mismatched authenticated Claude review before any enablement. A real no-review activation attempt was refused and final paused status read back. The historical successful read-only scheduler run is not current enablement or approval, and no next run is inferred.

## Review handoff

Review the runtime plus this evidence, including the authority-gate correction. The installed manifest SHA256 is `b61732024785898e8c99f66c3e5399b5a93b5d61e9876f96da50cfa64310de0f`. If intake-only activation passes, Claude can post `[REVIEW]` with this exact JSON (optionally fenced), after doing the review:

```json
{"hearth_relay_activation_review":{"verdict":"pass","mode":"intake_capacity_only","manifest_sha256":"b61732024785898e8c99f66c3e5399b5a93b5d61e9876f96da50cfa64310de0f"}}
```

This is review evidence, not paid-run authority or a live coding PASS. The subsequent explicit activation step is `ops/hearth2/activate-offline-relay.ps1 -ClaudeReviewEvent <verified-event-id>` on the approved laptop. No actual turn may run under this adapter's current financial guard.

## Rulings and limits

1. Missing verifiable financial routing stays closed; quota and caller assertions cannot replace it. Cost: requested unattended coding remains incomplete, and intake-only activation cannot be described as autonomous implementation.
2. Original Claude-review condition remains in force despite later enable approval. The premature observational run is disclosed and reversed; no repeat Rad enablement approval is required after review. Cost: the requested ongoing relay is not currently running.
3. Keep private local evidence/continuity instead of deleting the task workspace; the source report and durable HM checkpoint link its outcome. Cost: retained local artifacts.

No model turn, paid run, credential/account setting change, merge, deployment or production change. Understanding stays unknown; task completion is not inferred. The first-week executed-model-session usage window has not started.
