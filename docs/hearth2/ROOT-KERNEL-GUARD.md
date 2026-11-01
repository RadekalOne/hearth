# Root kernel termination and independent disarm boundary

Status: inactive code, no installed timer, daemon adapter, worker, command entry
point or service activation. Tests touch only private temporary regular files
and synthetic inventory. They do not operate the laptop's real cgroups.

`RootKernelGuard.enforce(binding)` validates the original sealed host, immutable
container, run/creation epoch, policy and deterministic guard/retained-parent
names. Host identity is supplied by a trusted root authentication port; matching
a string here does not establish remote-host authentication. Names are derived
from the original epoch and never changed to the current restore epoch.

The guard requests parent freeze and kernel kill **before any daemon access**.
It then checks the inspected immutable ID, root run/epoch/policy/workload labels
and exact parent, removes only that ID, requires a successful exact absence query
and reads empty/frozen parent state. A return records termination observations,
never task success or a database slot release. Running Docker's zero ExitCode or
an exited-but-never-started state cannot invent an actual process exit; an exit is
known only with exited/stopped/PID0 state and real start/end within the bound
creation time and current observation. Unknown exits remain unknown. The guard
now requires a durable original-binding/exit receipt BEFORE immutable-ID removal
and a second removal/empty receipt before returning (`GUARD-EVIDENCE.md`). Without
a store or acknowledgment it repeats kernel stop and refuses removal/success;
the parent and guard remain retained.

Any failure or catchable interruption after kernel quiescence causes another
freeze request and another kernel-kill attempt. Kill is attempted even if the
renewed freeze request fails. The error stays unconfirmed, no success receipt is
returned, no parent is thawed/removed and no timer is disarmed. This covers a late
child arriving before a daemon inspection/removal failure. SIGKILL, host/kernel
failure and reboot still require independent outside inventory/acceptance;
Python exception handling cannot establish that containment.

`CgroupFiles` supplies real descriptor-relative freeze/kill/events operations.
It opens the root and exact deterministic child directory without following a
final symlink, opens only existing fixed control names without following symlinks,
rejects special files, bounds event reads and requires unambiguous populated and
frozen values. It never creates/thaws/deletes a parent. The default root is
`/sys/fs/cgroup`; tests explicitly inject a private directory. Root path/layout,
root-only permissions and actual cgroup-v2 semantics are deployment/OS gates.
The concrete future daemon driver must use exactly the configured retained
parent layout; there is no implicit conversion to a different systemd slice.

`IndependentGuardRelease.release(binding)` accepts no cached guard receipt or
caller boolean. It queries exact immutable-ID absence FIRST, then independently
re-reads empty **and frozen** parent state, verifies original host again, then invokes
the trusted daemon port's disarm operation. Missing, populated, thawed, unknown
or failed queries refuse. The observer does not remove/thaw the parent or release
a DB slot. Production must run it independently/outside the workload; two Python
class names do not prove that privilege/process separation. The daemon port must
raise on every failed/uncertain inspect/remove/absence/disarm operation and enforce
bounded execution. No concrete subprocess/systemd/Docker port is installed here.

No timer arming or start method is added. Actual original-deadline timer matching,
OS start after a delayed DB fence, authenticated collector/host identity, daemon
timeouts/output bounds, independent observer placement, orphan intents, reboot,
old backups and strict RecoveryCoordinator/native wiring remain activation gates.
Existing900s defaults and conditional full-run lease policy stay inactive.

Offline tests cover freeze/kill-before-daemon order, repeated kernel kill after
inspection/removal/absence failure or interruption, frozen-parent retention,
wrong immutable ID/parent and host refusal, unknown exit semantics, independent
disarm refusal/success, concrete private-file writes, traversal/symlink attacks
and missing/ambiguous events. No OS containment acceptance follows.

Verification, laptop1November2026:16missing-feature tests observed RED then GREEN;
two additional regressions observed RED before fixes (never-started exit and
post-kill interruption), giving18new cases.126focused implementer tests passed
18.992s. One fresh read-only reviewer found no Critical/Important/Minor issues,
independently passed75focused cases35.815s and four additional ephemeral edge
checks1.897s: kill despite renewed-freeze failure, repeat kill after final-state
failure, policy mismatch prevents removal, and host change during absence query
prevents disarm. Only private regular files and synthetic inventory were used.

Full Python3.12 suite:575PASS205.151s, actual exit0, immutable
`guard-review-source.tar.gz` SHA256
`b8b3feaeafd1045c6be52c65692a6d69a3347b595956eb2daf055cb7d5515726`.
Both changed code/test files were compared byte-exact to that passed source;
documentation alone followed. Durable WSL source is
`/home/rslabinski/.local/share/hearth2-laptop-verification/guard-20261101/source`.
It reused the existing project-specific isolated dependency environment/HOME and
preloaded official Chroma cache; the test network namespace enabled only loopback.
Archive, review, focused log and `guard-full-python-offline.log` remain in the
private plan ledger. Earlier primitives received integration review, not another
exhaustive audit. Actual OS/native/whole-piece acceptance remains open.
