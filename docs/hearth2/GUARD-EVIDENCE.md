# Durable root observations before immutable-ID removal

Status: inactive filesystem store and guard integration. Tests use private
regular files and synthetic daemon inventory. No OS workload, service, credential
or production database is opened or activated by these tests.

`GuardEvidenceStore` lives outside the restorable work-record database. A trusted
root service provisions a private0700directory; the library does not create one
or infer a new host from a restored DB. It checks service-EUID ownership, exact
private mode and non-symlink root/file access. Actual root identity, full trusted
parent path, permissions, filesystem and backup placement remain deployment gates.

Records contain only the exact original creation binding and a typed observation.
The pre-removal `observed` stage records observation time and known actual exit/end
or explicit unknown. The `removed` stage records observation time and successful
empty/immutable-absence observations. No command, Env, credential, native closeout,
usage, role or worker-supplied fields are permitted. The original host, creation
epoch, guard, parent, deadline and policy remain unchanged across DB restore.

Files are immutable0400 canonical JSON, named by binding/stage/content SHA256.
Append writes a unique private staging file, fsyncs its complete contents and
mode, publishes by a no-replace hard link, unlinks its own staging name, then
fsyncs the directory before acknowledgment. An exact retry reconfirms file and
directory durability rather than returning on existence alone. No final receipt
is overwritten/deleted. Complete unacknowledged receipts can survive an append
failure, but the failed call never authorizes removal. Storage errors propagate.

A nonblocking exclusive directory lock serializes writers and conflicting known
exit/end checks. Unknown and later known observations remain separate immutable
history. A known exit/end cannot be replaced. Readers take a nonblocking shared
lock, validate canonical bytes/checksum/shape/identity/permissions, and fsync each
record plus the directory before returning. Thus a reader does not acknowledge
the interval between another writer's publication and final directory sync.
Busy locks, corrupt/symlinked files and failed durability checks refuse.

Each record is bounded16KiB; a directory scan stops after4096entries and a single
binding after256receipts. These are fail-closed capacity bounds, not a retention
system. Prospective capacity is checked under the writer lock before creating
any staging file, while exact retries remain allowed at capacity. New
publication reserves both staging and final directory entries, so a retained
staging link after interruption cannot itself exceed the readable scan bound. A refused
post-removal append leaves the earlier exit receipt readable and produces no
positive guard result. Root storage capacity and safe archival need operations planning. Orphan
staging files may remain after abrupt process death; no automatic adoption or
deletion of unknown files is implemented. Checksums detect corruption, not a
malicious root or a storage device falsely acknowledging fsync.

An exclusive-create collision never grants ownership of the preexisting staging
name: failure cleanup unlinks only a staging file created by that invocation.

`RootKernelGuard` still freezes/kills before daemon access. After inspecting and
validating the original immutable container, it MUST receive a durable `observed`
acknowledgment before removing that ID. No evidence store, failed file/directory
sync or conflicting history leaves the ID and guard retained after a repeated
kernel-stop attempt. After removal, successful absence and empty/frozen state,
it must durably append `removed` before returning a successful guard observation.
A post-removal storage failure retains the earlier actual-exit receipt, repeats
kernel kill, retains the frozen parent/guard and returns no success receipt.

Historical receipts never become fresh independent OS proof, task success or a
DB slot release. `IndependentGuardRelease` still performs fresh original-host
empty/frozen and immutable-ID-absence queries. A future outside collector must
authenticate the receipt/host, preserve known exit history and query current
containment before strict RecoveryCoordinator wiring. Backups of the work DB
alone do not migrate these host-bound root artifacts or prove old-host removal.

The former guard constructor may omit a store for compatibility, but enforcement
then kills conservatively and refuses ID removal. Real activation must provision
and pin the matched code and root evidence store. Original timer/deadline matching,
host authentication, retained-parent layout, concrete create/arm/start driver,
real crash/reboot/storage/observer separation/orphan/old-backup and whole-piece
native acceptance remain open.900s/default full-run policy stays inactive.

Offline tests prove append/re-read/idempotency, pre-removal visibility, no-store
refusal, file/directory fsync faults, preserved pre-removal exit after later failure,
unknown/known history, conflicting two-process writers, strict credential-free
shape, root/file permissions/symlinks/corruption and read durability/writer fencing.

Verification, laptop1November2026:13missing-feature tests observed RED, then
31evidence/guard checks passed5.425s; two read-barrier regressions observed RED
before their fixes.158focused checks passed22.713s. One fresh read-only review
independently passed90existing focused cases and reproduced two Important bugs:
prospective capacity could acknowledge an unreadable history, and failed staging
creation could delete a preexisting orphan. Three regressions observed RED before
the single fix pass. The same capacity fix reserves staging/final peak headroom,
also observed RED before correction. Final161focused checks passed24.597s. No
repeat review is claimed; the original607PASS225.167s source is historical.

Final full Python3.12 suite:610PASS152.093s, actual exit0, immutable
`evidence-fixed-review-source.tar.gz` SHA256
`85d318c7874bbb96ac3472bd896c4e68d77ed942d2c051a4bf667c4ee2cc2e3c`.
All four changed code/test files were compared byte-exact; documentation alone
followed. Durable WSL source is
`/home/rslabinski/.local/share/hearth2-laptop-verification/evidence-fixed-20261101/source`.
The suite reused the existing project-specific isolated dependency environment/
HOME and official Chroma cache, with only loopback enabled in a network namespace.
Archive, review, focused and `evidence-fixed-full-python-offline.log` remain in the
private plan ledger. Tests establish private-filesystem behavior and fault handling,
not real power-loss/OS/root authentication or native/full-piece acceptance.
