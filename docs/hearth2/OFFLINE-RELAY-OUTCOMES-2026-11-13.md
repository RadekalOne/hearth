# Relay pause outcomes and renamed-host acceptance - 13 November 2026

Claude's reviews of `1eda058` passed the disabled-candidate scope and identified three follow-ups. This increment addresses them under `relay_c5e87bf0e5744dae`, deduplicating Rad's direct instruction to check and address the review. Runtime source is `47d0069766587042823036cd4b721ebcf4251545`, based on `1eda058`, on `codex/hearth-offline-relay-pause-outcomes`.

- The default **Pause Hearth relay** action shows a visible Paused, Pending or Refused result dialog. A timestamped `pause-result.json` is saved independently of staged launch files. The recovery-side `--status --json` reads current control/active-record state without stopping, disabling or rewriting it. It does not perform a new termination check.
- A hostname mismatch no longer blocks the local latch, Windows stop or exact owned-task disable. Only the trial SSH operation is hostname-gated. Unexpected arguments cannot select another profile or bypass the fixed-profile local pause.
- `latch_confirmed` describes the committed latch independently of malformed/ambiguous identity validation. Such records leave cleanup pending, with no unverified targeted stop and no automatic reconciliation or retry.

Launch verification remains unchanged and fail-closed. The relay and installed control stayed disabled throughout. Neither the OS hostname nor account/credential settings changed.

The canonical-source full Linux suite passed **1,285/1,285**, zero skips, exit 0 in 129.825s with external networking disabled. The independent root observer found all 309 baseline files unchanged and no fixture/suite containers or watchdogs. Windows fixture/UI helpers are absent; WSL remains stopped.

The focused Windows suite passes 45 tests with OS, scheduler and UI effects mocked. The single fresh-context source review passed its 44 then-existing tests and found one Minor receipt-ordering race. We regraded it as Important because closing an older dialog could also replace a newer pending observation with an older paused observation. A regression reproduced that direction, and one fix pass removed the post-dialog rewrite. The final 45-test suite passes; no second source-review PASS is claimed. Claude's exact revised-commit review remains pending.

Seven explicit active-fixture integration checks pass: staged file damage, unreadable manifest and redirected LOCALAPPDATA, each on Windows and trial Docker, plus local recovery under a simulated renamed-host function. These are harmless Python fixtures, not Codex workers. The renamed-host check observed three active processes at actual stop entry and confirmed them empty after the 0.0005-second direct stop. It did not rename Windows. All six integrity cases still refused launch and confirmed empty cleanup. Synthetic fixture audit rows remain in the installed paused database; no active rows or outbox remain.

The GUI integration check observed visible windows and read back their actual text for paused/pending/refused renderer fixtures, then observed the actual installed default action showing Paused. Pending/refused renderer inputs are synthetic, not claims of a real OS refusal. The observer only dismissed its own child process's dialog. Initial harness attempts assumed a direct IDOK child; logs retain their unconfirmed-close failures. Selecting the actual nested OK control resolved the harness issue. This is programmatic Win32 visibility/text evidence, not a human visual review.

An actual independent status query succeeded while a staged file was deliberately damaged; the staged status/launch verifier refused. The original bytes were restored and hashes checked. The timestamped receipt is written before the dialog opens and never rewritten merely when an older dialog closes, so it cannot replace a newer result through that path.

The [machine-readable evidence](evidence/offline-relay-outcomes-2026-11-13.json) records full-suite, source/archive/install hashes, physical/UI receipts and final observers. SSH configuration/known-hosts and OS/Python/recovery/private-owner trust remain documented assumptions. Generic stranded-job reconciliation is still deferred; clean-live-state selection belongs to separately approved enablement. No audit rows were purged.

All existing Hearth scheduled-task definitions and all 241 tasks' enabled flags match the pre-change snapshot. One unrelated Zoom user-update task's definition hash changed; its cause is unverified, and this increment performed no write to it. The broader all-task-definitions-unchanged claim is not made.

Live authenticated coordination, included-only allowance/financial enforcement and unattended launch remain unavailable and refuse. No activation, paid run, actual worker/model session, merge, deploy or production contact occurred. Interactive coding-session seat usage is unavailable; the first-week post-enable usage window has not started. Understanding remains unknown and human acceptance false.
