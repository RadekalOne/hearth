# Bounded local root daemon commands

Status: inactive library, no installed entry point, service, timer or worker. All
tests execute private Python fake helpers; no real Docker/systemctl daemon call.

`BoundedCommand` uses a fixed absolute executable, bounded argument list, no shell,
DEVNULL stdin, closed inherited descriptors, fixed working directory and an
explicit minimal environment. It forwards no Hearth/provider/SSH credentials,
Docker context/host overrides or D-Bus routing. Executable binaries, parent paths
and permissions remain trusted root configuration and deployment gates.

Stdout and stderr share a bounded byte budget (default64KiB); stderr is counted
but never returned. A monotonic command/pipe deadline defaults to5s, with up to1s
additional helper-reap confirmation under a responsive kernel. Pipe reads are
nonblocking and bounded before accumulating stdout. Nonzero exit, malformed
arguments, timeout and excess output refuse with generic errors, never raw
stdout/stderr. There is no retry. The transport terminates its own helper process
group with SIGKILL and waits, on success or any catchable failure. It uses Linux
waitid/WNOWAIT before cleanup so the helper PID is not deliberately reaped before
targeting that group. Root deployment must preserve normal child ownership and
SIGCHLD behavior. This is a bounded helper protocol under a responsive kernel;
it does not solve uninterruptible kernel I/O or filesystem/exec stalls.

Process-group cleanup is **not** host-wide descendant containment: an intentionally
escaped session is outside that guarantee. Executables here are trusted root
helpers. The separate frozen workload cgroup remains the native-worker boundary;
terminating a CLI helper does not terminate daemon-owned Docker workloads.

`DockerSystemdCommands` supplies the guard's inspect/remove/absence/disarm port.
Docker always receives the fixed local Unix socket. IDs must be exactly64lowercase
hex characters, before any subprocess. Inspection asks the daemon to project only
ID, four root labels, cgroup parent and six selected process-state fields. It never
requests credential Env, Args, Mounts, arbitrary labels, State.Error or health logs.
The returned JSON must have that exact shape and types, with no duplicate or
nonfinite fields. An unexpected projection is refused rather than forwarded.

Removal uses only the immutable ID. Inventory uses a full-ID filter and untruncated
ID output: a successful empty result means absent, the exact ID means present,
and failed or unexpected output stays unknown. This provides no original-host
authentication by itself; the guard/independent observer still need trusted host
identity and a verified local daemon/root layout.

Disarm accepts only the deterministic guard prefix plus64hex characters. It stops
exactly that timer and service, then requires a successful empty active-unit
inventory. It never stops a parent slice or arbitrary unit. Missing/failed daemon
operations raise rather than imply absence/stop. This low-level command port does
not itself collect empty/absence evidence; `IndependentGuardRelease` must own the
fresh original-host checks before invoking it. There is no DB slot-release route.

Actual CLI template/version support, local socket/root binary permissions,
systemd timer identity and fixed-deadline matching, authenticated original host,
durable root receipts across immutable-ID removal, root parent-layout verification,
arming/start/independent observer placement and composed OS/reboot/backup/native
acceptance remain open. Existing900s/default full-run policy remains inactive.

Offline tests run real private helpers to prove environment stripping, bounded
time/output, opaque errors and same-group child cleanup after success/timeout.
Private fake daemon executables verify fixed arguments, selected projection,
identity refusal before execution, failed inventory, exact removal and guarded
unit-stop confirmation. These tests establish no actual Docker/systemd acceptance.

Verification, laptop1November2026:17missing-feature tests observed RED then
GREEN0.659s;143focused implementer tests initially passed18.150s. One fresh
read-only review found no production Critical/Important defect, and reproduced
one harness race: a correctly killed child could disappear with ESRCH during
`/proc` reading. The implementer treated this as a blocking false CI failure and
fixed both checks to accept ESRCH as disappearance. The observed review failure
is RED evidence;143focused tests then passed28.443s. No repeat review is claimed.
The reviewer separately verified55cases plus that one harness failure,36launch/
creation cases and four ephemeral projection/inventory/stop/error checks.

Final full Python3.12 suite:592PASS127.422s, actual exit0, immutable
`commands-fixed-review-source.tar.gz` SHA256
`b3f54dd7cd360eb6f05e4d4f01b615a22baa50ec551d28f9012f1c462aea66cd`.
Both changed code/test files were compared byte-exact; documentation alone
followed. Durable WSL source is
`/home/rslabinski/.local/share/hearth2-laptop-verification/commands-fixed-20261101/source`,
using the existing project-specific isolated dependency environment/HOME and
official preloaded Chroma cache, in a network namespace with only loopback up.
Private archive, review, focused and `commands-fixed-full-python-offline.log`
remain in the plan ledger. Earlier pre-fix full592PASS225.383s is historical;
the final source above includes the harness fix. OS/native gates remain open.
