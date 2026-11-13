# Independent relay pause acceptance - 13 November 2026

This closes the staged-integrity dependency reported in Claude's review `drawer_ea7c05d164dc5f1cc7cc586db4fba09e`, under `relay_342a3aab520e435d`. The revised runtime is `bcdffb32570ea36c8324a66fc116262233a5a25d`, based on `cb77197`, on `codex/hearth-offline-relay-pause-recovery`. The relay remains disabled and unavailable for unattended work.

The desktop **Pause Hearth relay** action now invokes a separate trusted recovery program. It obtains installed state through Windows Known Folders, opens only that existing database, persists paused/new epoch, stops recorded workload identities, and disables the exact owned root-level task/action. It does not import staged launch code or read the staged manifest. Launch verification still refuses damaged staged files and also verifies the recovery artifact's hash. The fixed interpreter, OS, recovery artifact and private state remain trusted; a compromised recovery executable or inaccessible/corrupt state is outside this guarantee and cannot report successful cleanup.

For recorded trial work, the action makes a bounded root SSH stop call to the fixed trial VPS. The operating instructions now disclose that behavior and its 25-second command / 8-second connection limits. Scheduler verification has a separate 30-second deadline. Unknown stop or scheduler state remains `paused_pending_stop`.

| Integrity failure while harmless work was active | Windows Job Object | Trial container | Launch verifier |
| --- | --- | --- | --- |
| Staged launch file changed | stopped, empty confirmed | stopped, absent confirmed | refused |
| Manifest unreadable (directory at file path) | stopped, empty confirmed | stopped, absent confirmed | refused |
| LOCALAPPDATA redirected to a decoy | stopped, decoy epoch untouched | stopped, decoy epoch untouched | refused |

These are explicit manual integration checks, separate from unit discovery. They started harmless external fixtures, verified their identities and recorded those synthetic identities in the already-paused installed database. They never enabled the installed control row or task, invoked its launcher or ran a model. The six paused fixture audit rows remain; no active rows remain. Fixtures were stopped before their independent 15-second watchdogs: Windows elapsed 3.7-7.9s; trial 7.8-8.1s.

The exact canonical-source full Linux suite passed **1,277/1,277**, zero skips, exit 0 in 139.695s, with external networking disabled. The final root observer found all 309 baseline files unchanged and no fixture/suite containers or watchdogs remaining. WSL remains stopped.

Ten new regressions cover the recovery path and launch's recovery-hash pin. The focused Windows suite passed 37/37; all scheduler operations in unit tests are now mocked. The one fresh-context whole-increment review found no Critical, Important or Minor findings and independently ran those 37 tests. Installed state, physical stop and trial operations were not observed by that reviewer. Claude's exact revised-commit review remains pending.

The trial's Docker cache was empty on the first new attempt; that start refused and cleanup confirmed no workload remained. The failed receipt was retained. The original exact public Python image digest was restored using an isolated empty-auth Docker configuration, and the retained test Dockerfile rebuilt a task-local test image. Registry/dependency preparation was separate from the credential-free, network-none tests; no host application, account, provider or production change occurred. Earlier trial results were not reused as proof of this revision.

The [machine-readable evidence](evidence/offline-relay-pause-2026-11-13.json) records final full-suite, source/archive/install hashes, physical receipts and cleanup. The disabled-only installer refresh preserved prior program/manifest/shortcut history. All 241 scheduler definition hashes and enabled flags match the pre-change snapshot; the exact relay remains disabled and never scheduler-run. The independent recovery program and staged launch program both match canonical source bytes after all corruption probes were restored.

Live authenticated coordination, checkout verification, included-only allowance/financial enforcement and unattended launcher adapters remain unavailable and fail closed. Per-session usage for this interactive coding work is unavailable; worker model calls are zero and the first-week post-enable reporting window has not started. No activation, paid run, merge, deploy or production contact occurred. Understanding remains unknown; this receipt establishes neither human acceptance nor task completion beyond the stated disabled build/tests.
