# Original-host creation binding and guarded consumption

Status: inactive controller libraries. No container is created, timer installed,
native worker started or service activated by this component.

`CreationRegistry.bind` seals the root-observed immutable container ID and stable
host fingerprint to the exact reserved live dispatch registration. It retains
the original claim/run, generation, creation epoch, fixed deadline and policy
digest. Guard and retained-parent names are deterministic from run plus original
creation epoch. They do not change with a controller restart or database restore.
The journal uses the existing audit/export layout and contains no credentials.
An exact live reserved replay is status only; different host/container identities,
consumed claims, expiry, foreign owners and restored claims cannot create or
replace a binding. `read` can recover the original identity after expiry/restore.

The future root launcher must create and independently verify a **stopped**
container with the intended limits, labels, retained parent and policy before
binding it. A crash between actual creation and journal commit still requires
outside inventory/reconciliation; this library cannot make Docker and SQLite
one transaction. No claim that a recorded fingerprint authenticates a machine
or that a stored policy digest proves its enforcement follows.

`consume_armed` accepts a fresh (at most60s, not future or before binding) trusted
observation of that exact original host, stopped/created immutable ID, guard,
retained parent, fixed deadline and policy. It requires the guard armed before
committing its attestation and the one-use dispatch transition in the same
SQLite transaction. Ordinary `DispatchRegistry.consume` refuses a bound run,
so the public direct path cannot skip guard attestation. Existing unbound paths
retain their previous contract. Private transaction helpers remain trusted-root
interfaces, not a restriction on arbitrary root database access.

Only the caller receiving a successful consume commit may proceed to start the
sealed immutable ID. Consumption replay, crash or lost acknowledgment cannot
authorize another start. A failed journal append rolls back both DB transitions;
it does **not** disarm the actual guard. A later retry still needs fresh original
host inspection. Actual start, prompt delivery and the guard's deadline behavior
remain outside this library and require composed OS evidence before activation.

For bound runs, OS-only observation and `RecoveryCoordinator` require the sealed
container/workload and original `host_id`. Strict recovery requires that host on
**both** independent empty and immutable-ID-absence observations. Even matching
empty/removal proofs on the new restore host cannot release the original host's
slot. Fresh current restore epoch/generation and existing outcome/replay rules
still apply; the original guard identity and deadline remain unchanged. These
are authenticated-root collector contracts, not proof that a caller really
contacted the original machine. Generic legacy result/reconcile/release paths
remain trusted-root compatibility interfaces; the future native controller must
use the strict bound recovery route.

No disarm operation is added. The root guard must remain armed and retain the
frozen parent until independent empty **and** immutable-ID-removal proofs; after
a post-kill failure it must attempt kernel kill again while the parent is frozen.
The existing standalone deadline fixture is unchanged. Actual launcher/collector
wiring, partial-create/arm/start restart drills, host reboot, privileged egress,
account projection and whole-piece native acceptance remain open. Existing900s
lease defaults and conditional full-run lease policy remain unchanged/inactive.

Offline SQLite tests cover binding restart/replay/restore, original-host fencing,
matching-but-wrong containers, exact current ownership, stale/malformed identity,
audit rollback, strict recovery/replay, guarded consume bypass, one-use consume
after restart, wrong timer/parent/deadline/policy, proof freshness, changed role
and restore fencing. They do not run Docker, systemd or provider inference.

Verification on the laptop, 1 November2026:18 new cases observed RED before
implementation, then GREEN;90 focused implementer tests passed. One fresh
read-only reviewer independently passed112 focused tests and a separate real
two-process consume race (one success, one refusal, exactly one armed/launching
journal transition), with no Critical/Important/new Minor findings. Earlier
primitives received integration review, not another exhaustive audit.

Full Python3.12 suite:539PASS119.801s, actual exit0, against immutable
`creation-review-source.tar.gz` SHA256
`abd317dbce4ffee1c65ad63207b2a87db25261bbb01706f682925f62fcfb897b`.
Source and project-specific dependency environment are retained under WSL
`/home/rslabinski/.local/share/hearth2-laptop-verification/creation-20261101`;
archive, dependency list and `full-python-offline.log` are in the private ledger
directory. Changed executable/test bytes were compared with the passed archive;
only documentation followed. Verification used an isolated network namespace
with only loopback enabled, a project-specific HOME and the official preloaded
Chroma embedding artifact verified against its shipped SHA256. Initial local
environment failures (missing embedding cache, then disabled loopback) were
resolved in the harness; product source was unchanged. No live provider or OS
containment acceptance follows from this offline regression.
