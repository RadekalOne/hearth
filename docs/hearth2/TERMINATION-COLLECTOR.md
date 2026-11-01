# Outside termination collector and strict recovery bridge

Status: inactive read-only Python collector. Tests use private evidence files,
synthetic OS ports and real SQLite; no actual daemon/cgroup/worker is operated.

`RootTerminationCollector.inspect_termination(binding)` implements the recovery
port consumed by `LaunchCoordinator.recover`. The launcher captures the exact
current registration, restore epoch and claim generation **before** calling this
port, then sends its packet only to `RecoveryCoordinator`. The collector never
mutates the work DB, classifies a task, kills/removes a workload or disarms a guard.

First it verifies the original host and reads the private original-binding guard
evidence. It checks exact record shape, canonical content hash, reference/binding,
times and known-exit consistency. Later unknown observations do not erase a known
exit/end; conflicting known facts refuse. Missing known exit stays explicitly
unknown, even when the old guard recorded empty/removal. Only bounded provenance
for the known historical exit is carried forward; no credential/native closeout,
usage, worker command or role state is accepted or created.

Historical receipts supply **only historical exit/end facts**. The collector
always successfully queries exact immutable-ID absence FIRST, then reads the
original retained parent as empty AND frozen. A late child added during the
absence query therefore cannot reuse an earlier empty-parent observation. The
independent guard-release observer now uses this same ordering. A historical `removed` receipt
cannot substitute for either query. Query timestamps are taken before invoking
each port so a delayed result cannot be relabeled as freshly acquired. Wall-clock
ordering and a monotonic whole-collection bound of60s both apply; rollback, stale
or failed observations refuse. Original host is checked again after the queries.
Actual port authentication and process/privilege independence are deployment
requirements, not properties established by a class name or matching string.

Each collection has a fresh root observation/recovery identity and bounded query
and receipt provenance. Classification references are explicit bounded trusted
root context supplied to the constructor and copied; they are not a worker task
closeout or automatic success/failure decision. The caller still chooses an
explicit root recovery outcome and all existing strict rules apply. Missing exit,
unknown protocol/zero-exit failure, invalid success, changed owner/epoch/generation,
stale proof and wrong original host remain held/refused. Failed ports raise opaque
typed errors and perform no cleanup fallback.

The current restore epoch/generation belong to the DB snapshot; the original
host, container, guard, parent and creation epoch belong to the immutable binding.
Restore does not rewrite those identities. A new-host absence proof refuses;
fresh original-host queries can recover under a newly captured current context.
After release, the launcher refuses before another driver inspection. Exact
recorded-packet acknowledgment remains the strict coordinator's separate route.

Root evidence/storage authenticity, authenticated local daemon and cgroup ports,
original timer/deadline matching, retained-parent layout, outside observer
deployment, concrete create/arm/start, power-loss/reboot/orphan/old-backup and
native/full-piece acceptance remain open. The frozen parent and armed guard are
retained: this collector never invokes `IndependentGuardRelease`. Existing900s
defaults and conditional full-run lease policy remain inactive.

Tests cover fresh queries versus historical exit facts, strict recovery, current
container/parent presence and thaw, missing/corrupt/mixed/conflicting receipts,
unknown/known history, original-host changes, slow/rolled-back collection,
epoch/generation changes during inspection, restore and copied bounded root
classification context. They do not establish actual OS containment or authority.

Verification, laptop1November2026:19missing-feature cases observed RED;
180focused cases passed27.030s after normalizing failed-port errors. One fresh
read-only reviewer independently passed109focused cases39.587s and four
ephemeral edge checks1.099s. During that same review, the implementer found the
empty-before-absence ordering race and wrote two regressions; both observed RED
and the reviewer independently reproduced them. One Important finding covers the
collector and independent disarm observer. The single fix pass uses successful
absence FIRST then a fresh empty/frozen read in both paths. Final182focused cases
passed37.021s; no re-review is claimed. Earlier629PASS198.315s is historical.

Final full Python3.12 suite:631PASS138.343s, actual exit0, immutable
`collector-fixed-review-source.tar.gz` SHA256
`bb585f18071e652ee403f5dd987562343dcf175fe74f480ce3d2c5ec36ce39ef`.
All four changed code/test files were compared byte-exact; documentation alone
followed. Durable WSL source is
`/home/rslabinski/.local/share/hearth2-laptop-verification/collector-fixed-20261101/source`.
The suite reused the existing project-specific isolated dependency environment/
HOME and official Chroma cache, with only loopback enabled in a network namespace.
Private archive, review, focused and `collector-fixed-full-python-offline.log`
remain in the plan ledger. Actual host/observer/OS/native/full-piece acceptance
remains open; no live worker or daemon was invoked.
