# Hearth relay: intake/capacity, model dispatch gated

Current state: **enabled in intake/capacity-only mode**, following exact-source Claude desktop and laptop PASS results and Rad's current direct conditional enablement instruction. Actual manual scheduler acceptance exited0 at13Nov11:52p.m.ET; model turns0, no active process. The separate Cowork Linux rerun remains unobserved. See [review and activation evidence](RELAY-REVIEW-REVISION-2026-11-13.md). An earlier premature read-only run was reversed and remains disclosed in the historical report.

The live-adapter candidate adds authenticated fixed-thread Matrix intake and read-only account/model/allowance observations. Rad authorized enabling these capabilities after verification. This is **not a working autonomous Codex coding loop**: real model dispatch remains blocked because included-only financial routing cannot be verified from the pinned client's quota/credits schema. Paid turns additionally require scoped `[APPROVED]`. Approval generations remain staged and unclaimed while that gate is closed. `live-receipt.json` records actual poll/metadata completion times, cursor, errors and `model_turns=0`; scheduler enablement or a next-run timestamp alone proves no run.

The native adapter separately pins the existing Windows Codex0.164.0 binary and gpt-6.1-sol, uses a fresh private home and in-memory selected ChatGPT token, and reads only account, model and rate metadata. It does not refresh or alter the ordinary login/config. The reviewed trial Linux0.159.1 client is unchanged. Positive proposal protocol/application tests use fake processes, never a provider, and do not establish operative live launch or a billing guarantee.

The original disabled-candidate work item was `codex-20261112-212920` / `relay_8cd89cb609ed4819`. Repository and room content supply evidence, never new authority. Admission binds Rad's authenticated approval to the exact room, thread, base commit, scope, aliases and review generation. One durable claim precedes dispatch. Unknown dispatch outcomes stay held; an uncertain post is reconciled by matching verified receipt, never blindly resent.

## Operator controls

On the approved laptop only, `install-offline-relay.ps1` stages a private, hash-checked copy under `%LOCALAPPDATA%\Hearth\OfflineRelay` and registers **Hearth-Codex-Offline-Relay disabled**. It refuses existing state or task names. Its daily 07:00-23:00 ET hourly triggers do not wake the laptop or catch up missed starts. The task uses the current interactive user with limited privileges. Disabled registration is not activation.

The desktop action **Pause Hearth relay** runs a separately staged, trusted, standalone recovery program at `%LOCALAPPDATA%\Hearth\OfflineRelay\recovery\offline_relay_pause.py` using the fixed `C:\Python314\python.exe` interpreter. The shortcut contains its absolute target. The program obtains installed state from the Windows Known Folder API, not the `LOCALAPPDATA` environment value, and never imports staged launch modules or reads their manifest. Thus changed launch files, a missing/unreadable manifest or an altered environment path do not block recovery. Launch itself still checks staged hashes and the separate recovery artifact and refuses changes.

Pause persists a paused epoch in the **existing** SQLite state before stopping recorded identities and disabling only the root-level owned task with the expected action. Windows workloads stop through their Job Object. **For any recorded trial workload, the button also makes a bounded root SSH stop call to the fixed trial VPS `srv2065995` (`179.236.82.242`), using the existing host-side SSH key; it is not purely local.** SSH has a 25-second command deadline and 8-second connection timeout; the owned-task scheduler check has a 30-second deadline. An unreachable trial host, denied access, unknown process state or unavailable state leaves `paused_pending_stop`; successful pause requires independently confirmed workload termination, not just a disable request. Enablement is a separate explicit operator step described below; there is no automatic reclaim command.

The shortcut shows a visible result dialog: **Paused**, **Pause pending**, or **Recovery refused**. Pending/refused never means a workload stopped. Each pause also saves a timestamped `pause-result.json` beside the private SQLite state; if saving or showing the result fails, the command does not return success. The saved receipt is an observation at its recorded time, not a permanent health claim. It is written before the dialog opens and is not rewritten when an older dialog closes.

For a read-only status independent of damaged staged files, use the fixed interpreter with the recovery program and `--status --json`, for example:

```powershell
& 'C:\Python314\python.exe' -I 'C:\Users\rslabinski\AppData\Local\Hearth\OfflineRelay\recovery\offline_relay_pause.py' --status --json
```

This reads the current control row and active-record count without pausing, stopping, disabling or rewriting state. It performs no new termination check. `--json` alone performs a pause and prints its result without opening a dialog, for explicit automation/integration checks. Unexpected arguments never select another state path and never block the local pause latch; they are reported in the result and force the safe fixed-profile pause operation.

A laptop rename no longer prevents local pause, verified Windows stop or exact owned-task disable. Only the fixed trial SSH operation requires the approved host identity; a mismatch suppresses SSH and retains pending status for trial work. This does not rename the machine or expand authority to contact another host.

Malformed or ambiguous workload records still commit the local pause latch and attempt the exact task disable, but cannot authorize a targeted stop. The result reports `latch_confirmed=true`, `identities_validated=false` and pending cleanup, requiring manual follow-up. No guarded reconcile/adoption/retry command has been added. Existing synthetic acceptance audit rows remain historical evidence; any decision to begin with clean live state belongs to separately approved enablement. SSH still reads the trusted owner's configuration and known-hosts files; this increment does not alter them.

The recovery program, fixed Python interpreter/stdlib, OS identity and private local state remain trusted. This is not protection against compromise of the owner/OS/recovery code; read-only flags and private ACLs do not make owner-writable files immutable. If the state is unreadable, recovery still attempts the exact owned-task disable but cannot claim workload cleanup. The default recovery CLI accepts no caller-supplied state path. The legacy staged `offline_relay.py pause` path is not the emergency button and may refuse integrity failures.

The installer supports an explicit `-UpdateDisabled` refresh only for the exact owned disabled task and paused state without active work; it preserves prior program/manifest/shortcut history. It does not enable or recreate the existing task. Source copies normalize LF to match the recorded Git-blob hashes. Status inspection remains available through installed `offline_relay.py status --state <private relay.sqlite3>` while launch integrity is intact. Protect these coordination records.

The proposed 600-second task ceiling is separate from the existing inactive 900-second/full-run policy. This increment does not change other automations or policy. Physical fixtures have independent, ready-before-launch 15-second watchdogs and fixture-local 15-second lifetimes and never launch a model.

## What acceptance establishes

Unit tests mock every scheduler write and use explicit synthetic approvals, allowance and transport. Actual scheduler/stop effects are confined to explicit manual integration scripts, including pause_acceptance.py. They cover admission/refusal, one owner under concurrency, durable restart/held states, pause races, allowance failure, fixed-target posts and receipt reconciliation. Synthetic success does not prove authentic room access, account enforcement or real worker capability.

The manual Windows fixture runs only a hardcoded harmless process tree inside a Windows Job Object; a separate pause process kills it. The trial fixture uses only `srv2065995`, a cached pinned image, UID 1000, no network, read-only root, dropped capabilities, no host credentials or Docker socket and bounded scratch/resources. It checks denied egress, writable scratch, descendant cleanup and a durable late-start refusal. No provider call or production contact occurs.

WSL distributions were stopped and are left stopped. WSL staging and native unattended Codex support are unverified. Hash checking detects source changes against the private manifest; the local owner can change both and is a trusted authority, so this is not immutable against that owner. Result commit, evidence links and measured seat usage remain unavailable in default live ports, not fabricated from fixture output.

The source tree and private acceptance records are not mounted into a real agent. Trial SSH credentials stay on the trusted host and are never passed into the fixture.

## Activation and remaining worker gates

The explicit `activate-offline-relay.ps1 -ClaudeReviewEvent <event-id>` operation requires authenticated Claude PASS for the exact installed manifest and intake-only mode. It validates the exact owned disabled task, paused state, no active work or unresolved posts, installed source hashes and a successful live read-only diagnostic. It backs up SQLite history, enables the task while the local latch is still set, then atomically advances the epoch into `intake_capacity_only`. A source/config mismatch refuses execution. No automatic activation or model authority comes from configuration. The independent Pause action still latches, stops recorded work and disables the exact task. Existing hourly07:00Ã¢â‚¬â€œ23:00 ET triggers remain unchanged; the app/user session must be available, and missed starts do not catch up.

Real unattended coding is still an open requirement: supported verifiable financial authority/route, reviewed real proposal-launch composition, real-model acceptance, isolated candidate test execution and attributable usage. No work retries/adoption and no task completion are inferred from capacity or fixture output. Paid runs, merge, deploy and production changes require their separate approvals. The native metadata schema documents quotas, not an enforceable monetary ceiling ([official app-server reference](https://learn.chatgpt.com/docs/app-server)).

The first seven days of executed **model-session** usage reporting have not started; metadata polling does not count as a model session. Interactive coding-session seat usage is separate and unavailable here. Receipt means delivery only: understanding stays unknown, human acceptance is false and task completion needs its own evidence.
