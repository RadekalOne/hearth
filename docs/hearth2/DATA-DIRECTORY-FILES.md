# Conditional bounded file-read verification

`DirectoryFileCapture` extends the inactive metadata fixture port with two
independent candidate-body read passes. Default view is absent and refuses.
It is a lower layer of Task3, not the full planned DataDirectoryCapture or an
installed helper, parser, discovery mechanism or credential-inventory producer.
Only private synthetic trees are exercised. No live Mavis data is read.

Every mapped regular single-link candidate is reacquired O_PATH/O_NOFOLLOW;
its inode/device/ctime/mode/owner/group/link/size/mtime and mount must match the
listing. Read-open uses the pinned procfd, then independently checks descriptor
identity/mount before reading. No candidate symlink/FIFO/socket/device/hardlink
body is opened. The file must match the supplied owner/group and not be writable
by group/others. A file failing that policy is unreadable(type), not absent.
Unmapped trees are not descended. Each pass closes all descriptors.

Reads accumulate short reads up to 65537 bytes. Length or stat size >=65536 is
unreadable(oversize); no truncated success. Empty existing files remain present.
Read-open/read errors become unreadable(permission/io), preserving other stable
sources; listing/root failures and inconsistent passes return whole-root
unscanned. Candidate metadata and named link are checked after reading, then all
measured candidates are checked again at pass completion. Two passes compare
private successful-file SHA256 digests as well as metadata/status/reason. No
hash is claimed for an unreadable or oversized body. There is no retry-until-stable.

Metadata entries, candidate acquisition/rechecks and every read attempt consume
the same exclusive work budget (max256); bytes across BOTH passes must remain
strictly below an independently supplied limit (max1MiB). Hitting either budget
invalidates the whole root with no summary. Monotonic checks still cannot kill a
blocked OS call: separate externally enforced helper isolation/reap is unfinished.

Public `DirectoryFileResult` contains only counts, fixed status/reason enums,
ordinal file outcomes and the compact coverage summary. Ordinal statuses derive
from final accounting, so unsafe sibling evidence cannot leak an unapproved
absence through an intermediate result. Bytes and comparison hashes are private
temporaries and are not persisted or returned. This is not a memory-erasure
guarantee, an audited parser closure or physical credential custody proof.

The supplied RootDirectoryView is conditional evidence, not independently
authenticated original-host/image/rootfs enrollment. The prior documented `..`
root-spelling Minor remains deferred before production enrollment. Two sequential
live reads do not create an atomic frozen view, and external concurrent mutation
cannot be ruled out by this component. All physical coverage families remain
unresolved. Native parsing, independent policy/consumer map/discovery, exact
transient naming audit, frozen-view comparison and process composition remain
future gates. No RootCredentialAccounting/observer/start authority is wired.

Source protocol reference: Python3.12 [os descriptor APIs](https://docs.python.org/3.12/library/os.html).

Verification uses fake files only, including empty/65535/65536/65537/large bodies,
short reads, permission/IO injection, changed content/identity, unsafe types,
reopen-mount/fstat faults, descriptor closure, final-pass prior-source mutation,
byte/work boundaries and redacted results. Initial16 tests failed for missing
reader. The race test was made deterministic by explicitly advancing mtime
(sub-clock-resolution writes need not change every stat timestamp immediately).
One new regression failed for intermediate-vs-final status disagreement; fixed
by deriving ordinal output from final accounting. Full-suite evidence follows.

Final verification: full1018 Ubuntu-24.04/Python3.12 tests PASS175.451s, actual exit0, external network disabled/loopback only. Immutable archive e11e8592cc717ac2357dd0454a4138d51c23d45265971464164aa3cceb9d924f; all90trackedHearth2Python/test bytes match. One fresh final review found no new defects;45focused and80credential tests pass, plus six reviewer adversarial fixture checks. Historical '..' canonical-root Minor remains deferred; no new minors or declined findings. LowerTask3 synthetic conditional file-read component only; no native parser or physical enrollment/credential-custody/start acceptance. Full Tasks1-4 remain unfinished.
