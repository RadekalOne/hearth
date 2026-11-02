# Inactive whole-rootfs inventory acquisition

`RootfsInventorySource.scan(image_id, container_id, requirements)` enumerates and
hashes every supported entry of one independently enrolled frozen read-only view.
It is the filesystem acquisition part of credential inventory, not a credential
scanner or absence receipt. Environment, container configuration/mount sources,
native consumers, audited manifests/parsers and runtime provenance remain gates.
No credential-backend or driver wiring is installed. The class has no `observe`
method and its output cannot satisfy the collector's credential inventory schema.

`RootfsInventoryEnrollment` explicitly authorizes the whole view under the exact
independently enrolled `CredentialAuditRequirements` digest. A selected-file
`RootfsViewEnrollment` alone is refused. The nested immutable view still pins
original host/boot/initial namespaces, exact approved image/nullable container ID,
root path/device/inode/ctime/mount and outside provenance. There is no automatic
whole-view enrollment, image/rootfs association, mount or policy broadening.

The fixed isolated stdlib helper reuses the existing rootfs descriptor/identity
primitives, validates actual root UID/EUID, original boot/namespaces and read-only
root identity, then walks every directory using bounded `scandir` iteration.
There are no filename exclusions, including hidden files. Names are sorted for a
deterministic traversal. Unsupported names, unreadable paths and budget exhaustion
refuse the entire acquisition; no successful truncated or partial result is emitted.

Every child is first acquired using `O_PATH|O_NOFOLLOW`; type and same-mount facts
are checked before reopening the pinned kernel `/proc/self/fd` inode for reading.
Only directories and single-link regular files up to 8 MiB are supported; symlinks,
hardlinks, devices, FIFOs, sockets, nested mounts, non-ASCII/control/backslash names,
paths over 4096 characters and depth over 64 refuse. Empty files are included.
Inner ownership/mode facts are inventoried, not silently normalized or interpreted
as safe. The enrolled root retains the existing ownership/protection requirements.

Two full passes must agree on every path's device/inode/mode/ownership/link/size/
mtime/ctime snapshot, all content digests, counters and logical-tree digest. Named
links, per-directory name lists and metadata are checked during each pass, then
root-path identity, read-only mount and runtime identity are checked again. Actual
frozen-view custody is still an independent enrollment/OS acceptance requirement;
these observations cannot protect against a malicious privileged kernel/producer.

Source and byte budgets count work across BOTH passes. Reaching a budget refuses,
even if an entire small tree would end exactly at that number. Backend hard caps
are 8192 visited entries and 64 MiB read across both passes, in addition to lower
policy limits. A larger declared policy does not enlarge these implementation
limits. Bounded directory iteration, depth, file size, metadata maps and chunked
reads bound resources. The existing isolated command transport enforces the
policy's 1–10 second timeout, 64-KiB output budget and helper-group cleanup. Failure
to terminate/reap remains a refusal. No file contents or path lists leave the
helper, and no inherited credential environment is passed to it.

The logical `tree_sha256` hashes canonical compact sorted-key JSON records plus
newlines in sorted depth-first order. Each record includes path, mode, UID/GID,
link count and kind; files also include byte length and content SHA256. Directory
records precede children. `snapshot_sha256` hashes the canonical path-to-stat
signature map, including inode/times. These digests are NOT the policy's separately
audited manifest digest and are never equated with semantic review or credential
absence. The parent validates exact typed root facts, work equations, per-file
byte feasibility, requirements/enrollment/image/CID binding, authenticated host,
and wall/monotonic freshness. It emits only digest/count/provenance summary facts.

Ruling: acquire a complete bounded filesystem inventory before attempting native
consumer classification. An unlisted private credential-file fixture changes the
tree/counts, but does not produce `credentials:none`. The existing requirements
still demand image environment/native consumers and, for a container, all its
configuration/consumer/mount-source coverage. Those producers/parsers and actual
root/image/view/enrollment/interpreter/procfs provenance remain unconfigured.
Unknown semantics never become a clean scan. All service/native/OS/orphan/backup
gates and default inactive 900-second/full-run lease policy remain unchanged.

Tests use private files and injected root/read-only facts, not actual privileged
mounts or real Docker/PID1/provider/worker execution. Primary contracts:
[Python descriptor scandir](https://docs.python.org/3.12/library/os.html#os.scandir),
[Linux open/O_PATH](https://man7.org/linux/man-pages/man2/open.2.html).

Verification on the laptop, 2 November 2026: initial 11 missing-feature tests
failed (0.035s); an impossible-byte-total regression failed before its feasibility
check. Final 73 focused checks passed (4.429s), direct 14 tests passed (0.228s).
One fresh final review found no Critical/Important/Minor issues and passed 35
focused plus 10 additional private adversarial checks. No fix pass or rereview
was needed. Full Ubuntu-24.04/Python 3.12 suite passed 804 tests (395.627s), actual
exit 0, with only loopback enabled in its network namespace and existing isolated
dependencies/HOME/cache reused. Immutable `rootfs-inventory-review-source.tar.gz`
SHA256 `63ed27d7c67bb72284ef2e9c93b5ec25800ac085c38c3f966fa308430eeccbd1`
matches both new code/test files byte-exact; documentation alone follows.
Durable source is
`/home/rslabinski/.local/share/hearth2-laptop-verification/rootfs-inventory-20261101/source`.
The directory's date suffix is inherited from the verification helper; this was a
new immutable source/run on November 2, not reuse of an older result. Actual root,
mount, enrollment/image custody, interpreter/procfs and complete credential/native
OS acceptance remain open. The expired daytime automation remains paused.
