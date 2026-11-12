# Offline relay disabled acceptance - 12 November 2026

The approved build for `codex-20261112-212920` / `relay_8cd89cb609ed4819` is complete as a **disabled, fail-closed candidate**, not an autonomous Codex loop. Runtime source commit: `1d2c6a4` on `codex/hearth-offline-relay-disabled`. Machine-readable receipts and source hashes are in [the evidence packet](evidence/offline-relay-2026-11-12.json); operating instructions are in [OFFLINE-RELAY.md](OFFLINE-RELAY.md).

| Check | Observed result |
| --- | --- |
| Full suite, cached Linux image, network none | 1,267 tests: 1,266 pass, one Windows-only skip; exit 0, 141.065s |
| Windows focused tests | 27 pass; exit 0, 11.388s, including real exact-task pause query |
| Windows process-tree pause | Separate controller process stopped the harmless Job Object; final empty |
| Trial isolation and pause | UID1000, read-only root, network none, denied egress, writable scratch, no credentials/socket; descendants gone; late start refused |
| Starter-exit cutoff | Windows and trial starters exited; independent supervision observed workload absence before pause; final empty |
| Disabled installation | Exact task disabled, current interactive user/limited privileges, 17 hourly ET triggers, never scheduler-run; private state paused, no jobs or outbox |
| One-step pause action | Desktop **Pause Hearth relay** target verified against staged manifest; installed pause command returned paused and scheduler disabled |
| Unchanged scope | 309 recorded trial baseline files match; no leftover fixture/suite containers or watchdogs; WSL remains stopped |

The fresh-context source review found four Important issues: crash-stranded pending posts, supervision armed too late or ended on a mere pause request, PID0 cleanup for created containers, and timezone discovery blocking emergency pause. Six regressions reproduced them; one fix pass made all green. This is the implementer's verified disposition, **not a new Claude PASS**. Claude's exact-commit review remains pending.

A real Windows scheduler query exceeded its initial ten-second deadline after the workload had stopped. The controller correctly retained `paused_pending_stop`. The bounded query is now thirty seconds, with timeout returning unconfirmed; final actual pause and repeated tests pass. The earlier failed receipt remains in private evidence.

Existing Hearth task definition hashes and enabled flags match before/after. One unrelated OS task, `Microsoft/Windows/Flighting/OneSettings/RefreshCache`, changed its definition hash while retaining enabled=true. Its cause is unverified; this build performed no write to it. The broader all-task-unchanged assertion was rejected and is not claimed.

Real authenticated coordination, checkout verification, included-only allowance/route enforcement and native unattended launcher ports remain unavailable and refuse. No actual Codex worker, account/provider probe or paid run occurred. Interactive coding-session seat usage is unavailable; fixture worker model calls are zero. The first-week accounting window has not begun. Understanding remains unknown; receipt is not human acceptance or task completion.

No activation, paid runs, merge, deploy or production contact is authorized by this packet. Exact-commit Claude review and separate capability/enablement approval remain gates. Private evidence is retained under this plan's `.superpowers/sdd` directory and the dedicated trial directory; these records contain synthetic acceptance state, not credentials.
