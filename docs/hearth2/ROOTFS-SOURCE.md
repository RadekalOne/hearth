# Inactive enrolled rootfs file source

`RootfsFileMeasurements` is a concrete bounded file-digest producer for the
`RootAssemblyCollector` file port. It reads a separately enrolled read-only
filesystem view; it does not create, extract, mount, inspect or adopt images or
containers. Default enrollment is empty and no driver wiring is installed.

`RootfsViewEnrollment` is immutable outside authority: original host/boot/initial
user, PID, mount and cgroup namespace inodes; exact image ID and optional stopped
container ID; canonical root path, device, inode, ctime and mount ID; approved file
paths and authority reference. Image and container views require distinct
enrollments. No constructor/helper can establish the image-to-rootfs association
from a directory name, caller declaration, DB record or current stat observation.
That association, a coherent frozen view and trusted provenance must be verified
independently before enrollment. There is no automatic enrollment API here.

The fixed helper runs through the existing bounded command port using isolated
stdlib Python (`-I -S -c` plus literal program/JSON/path). Its environment contains
only the existing minimal noncredential variables; stdin and inherited file
descriptors are closed. The existing five-second/64-KiB transport kills and reaps
its helper process group, including when filesystem I/O fails. Cleanup inability
fails closed. No shell, provider, worker prompt or file-content output is used.
The installed Python interpreter, stdlib, package, kernel/procfs and command-port
runtime still need independently pinned dependency/provenance acceptance. A hash
of the helper in a reference is not that acceptance.

The child checks actual UID/EUID zero, original boot and namespace inodes before
I/O. It opens every root-path component with descriptor-relative no-follow
directory opens, then checks enrolled root device/inode/ctime and `/proc/self/fdinfo`
mount ID. The filesystem must report `ST_RDONLY`. Selected ancestors must be
root owned directories without group/other writes on that same mount. Nested
mounts are unsupported. The final target is acquired with `O_PATH|O_NOFOLLOW`
before any read open, preventing activation of a device/FIFO during type checking.
Only a regular root-owned UID/GID-zero, single-link, 0444/0555 file of 1 byte through
8 MiB is reopened through the pinned kernel `/proc/self/fd` reference. Inode facts
and mount identity are compared again before reading. No source pathname link is
followed; the deliberate procfs reopen refers to an already validated inode.

Reads use bounded chunks and return only SHA256/stat facts. File metadata, named
path links, all held ancestor descriptors, root-path identity, read-only mount and
runtime identity are rechecked after the read. The parent requires exact typed
helper fields and enrolled root facts, then rechecks authenticated host and
five-second wall/monotonic bounds. It emits the existing collector file schema,
with enrollment/measurement references. The collector still requires expected
profile hashes, stricter profile size/mode, two fresh stable rounds and all other
independent runtime/metadata/credential evidence.

Ruling: use this direct digest producer rather than serializing an 8-MiB file into
the existing 64-KiB command transport. The previous selected-file archive decoder
remains a separate inactive option for a future independently authenticated
archive source. No transport limits are widened and no image-layer semantics
are invented. Hardlinked files, nested mounts and unverified rootfs enrollment
remain unsupported rather than being interpreted as complete proof.

Tests operate on private ordinary filesystem fixtures with explicit injected
root-ownership and read-only-mount facts. They exercise real descriptor traversal
and byte hashing, not actual root privilege or an enrolled Docker filesystem.
No real mount, daemon, cgroup, worker, service or provider is activated. Complete
credential inventory and root runtime/wrapper/dependency enrollment remain open;
selected-file hashes never establish credential absence. Default 900-second/full
run lease remains inactive.

Primary sources:

- [Linux open/openat/O_PATH](https://man7.org/linux/man-pages/man2/open.2.html).
- [Linux proc fdinfo mount IDs](https://man7.org/linux/man-pages/man5/proc_pid_fdinfo.5.html).
- [Python 3.12 descriptor/statvfs APIs](https://docs.python.org/3.12/library/os.html).

Verification: initial nine tests failed on the missing producer; the O_PATH
ordering regression independently failed before its fix. Final 71 focused tests
passed (8.370s), direct 13 tests passed (0.683s). One fresh final review found no
Critical, Important or Minor issues; its 67 focused and 11 additional adversarial
checks passed. No review-fix pass or rereview was needed. Full Ubuntu-24.04 Python
3.12 suite passed 782 tests (292.578s), actual exit 0, with only loopback enabled in
the isolated full-test network namespace and existing dependencies/HOME/cache.
Immutable `rootfs-review-source.tar.gz` SHA256
`c2e7321e12b7b760a85201e230b01d0e8bf4497b46c3d183dfffbb027d4af8d5`
matches both new code/test files byte-exact; documentation alone follows.
Durable source is
`/home/rslabinski/.local/share/hearth2-laptop-verification/rootfs-20261101/source`.
These are source/private-fixture checks, not enrolled-host root/mount/provenance
or full native/OS acceptance.
