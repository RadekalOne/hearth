# Hearth offline relay: disabled candidate

This increment is a fail-closed controller and credential-free acceptance fixture. It is **not a working autonomous Codex loop**. Live coordination, authenticated approval lookup, checkout verification, included-only allowance enforcement and unattended launch adapters remain unavailable. The default ports refuse them. No enable command is provided.

The sole work item is `codex-20261112-212920` / `relay_8cd89cb609ed4819`. Repository and room content supply evidence, never new authority. Admission binds Rad's authenticated approval to the exact room, thread, base commit, scope, aliases and review generation. One durable claim precedes dispatch. Unknown dispatch outcomes stay held; an uncertain post is reconciled by matching verified receipt, never blindly resent.

## Operator controls

On the approved laptop only, `install-offline-relay.ps1` stages a private, hash-checked copy under `%LOCALAPPDATA%\Hearth\OfflineRelay` and registers **Hearth-Codex-Offline-Relay disabled**. It refuses existing state or task names. Its daily 07:00-23:00 ET hourly triggers do not wake the laptop or catch up missed starts. The task uses the current interactive user with limited privileges. Disabled registration is not activation.

The desktop action **Pause Hearth relay** runs a separately staged, trusted, standalone recovery program at `%LOCALAPPDATA%\Hearth\OfflineRelay\recovery\offline_relay_pause.py` using the fixed `C:\Python314\python.exe` interpreter. The shortcut contains its absolute target. The program obtains installed state from the Windows Known Folder API, not the `LOCALAPPDATA` environment value, and never imports staged launch modules or reads their manifest. Thus changed launch files, a missing/unreadable manifest or an altered environment path do not block recovery. Launch itself still checks staged hashes and the separate recovery artifact and refuses changes.

Pause persists a paused epoch in the **existing** SQLite state before stopping recorded identities and disabling only the root-level owned task with the expected action. Windows workloads stop through their Job Object. **For any recorded trial workload, the button also makes a bounded root SSH stop call to the fixed trial VPS `srv2065995` (`179.236.82.242`), using the existing host-side SSH key; it is not purely local.** SSH has a 25-second command deadline and 8-second connection timeout; the owned-task scheduler check has a 30-second deadline. An unreachable trial host, denied access, unknown process state or unavailable state leaves `paused_pending_stop`; successful pause requires independently confirmed workload termination, not just a disable request. There is no enable or automatic reclaim command.

The recovery program, fixed Python interpreter/stdlib, OS identity and private local state remain trusted. This is not protection against compromise of the owner/OS/recovery code; read-only flags and private ACLs do not make owner-writable files immutable. If the state is unreadable, recovery still attempts the exact owned-task disable but cannot claim workload cleanup. The default recovery CLI accepts no caller-supplied state path. The legacy staged `offline_relay.py pause` path is not the emergency button and may refuse integrity failures.

The installer supports an explicit `-UpdateDisabled` refresh only for the exact owned disabled task and paused state without active work; it preserves prior program/manifest/shortcut history. It does not enable or recreate the existing task. Source copies normalize LF to match the recorded Git-blob hashes. Status inspection remains available through installed `offline_relay.py status --state <private relay.sqlite3>` while launch integrity is intact. Protect these coordination records.

The proposed 600-second task ceiling is separate from the existing inactive 900-second/full-run policy. This increment does not change other automations or policy. Physical fixtures have independent, ready-before-launch 15-second watchdogs and fixture-local 15-second lifetimes and never launch a model.

## What acceptance establishes

Unit tests mock every scheduler write and use explicit synthetic approvals, allowance and transport. Actual scheduler/stop effects are confined to explicit manual integration scripts, including pause_acceptance.py. They cover admission/refusal, one owner under concurrency, durable restart/held states, pause races, allowance failure, fixed-target posts and receipt reconciliation. Synthetic success does not prove authentic room access, account enforcement or real worker capability.

The manual Windows fixture runs only a hardcoded harmless process tree inside a Windows Job Object; a separate pause process kills it. The trial fixture uses only `srv2065995`, a cached pinned image, UID 1000, no network, read-only root, dropped capabilities, no host credentials or Docker socket and bounded scratch/resources. It checks denied egress, writable scratch, descendant cleanup and a durable late-start refusal. No provider call or production contact occurs.

WSL distributions were stopped and are left stopped. WSL staging and native unattended Codex support are unverified. Hash checking detects source changes against the private manifest; the local owner can change both and is a trusted authority, so this is not immutable against that owner. Result commit, evidence links and measured seat usage remain unavailable in default live ports, not fabricated from fixture output.

The source tree and private acceptance records are not mounted into a real agent. Trial SSH credentials stay on the trusted host and are never passed into the fixture.

## Remaining enablement gates

Claude must review the exact candidate commit and evidence. Real adapters must then establish authenticated thread intake, protected checkout/launch boundaries, authoritative fresh included-only routing with no financial fallback, attributable usage and real process cutoffs. They need separate scope and verification; unavailable evidence always refuses. Rad must explicitly approve enablement afterwards. Paid runs, merge, deploy and production remain excluded.

The first seven days of mandatory executed-session usage reports start only after actual enablement; that window has not started. Current interactive coding-session seat usage is unavailable. Worker model calls in these acceptance fixtures are zero. Receipt means delivery only: understanding stays unknown, human acceptance is false and task completion requires its own evidence.
