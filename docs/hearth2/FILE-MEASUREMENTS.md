# Inactive selected-file archive measurements

`ArchiveFileMeasurements.observe(image_id, container_id, path)` implements the
file-digest port used by `RootAssemblyCollector`. It measures a bounded raw
single-file USTAR archive without extraction or execution. No default archive
source, Docker adapter, image-layer resolver, enrollment or driver wiring exists.
Injected fixture evidence is not physical OS attestation.

The independently authenticated source must read the exact approved image and,
when supplied, original stopped immutable container ID. It must resolve the full
absolute source path without following links and acquire each ancestor's lstat
mode/UID in the same source. It returns frozen `FileArchive` evidence with those
identities, original path, ordered root-through-parent directory measurements,
archive bytes, acquisition timestamp and provenance references. The consumer
requires all ancestors to be root owned directories without group/other writes.
These values require an independently trusted producer; archive bytes alone
cannot establish source identity, ancestor resolution or trustworthy provenance.

Acquisition is limited to five seconds and 8 MiB + 16 KiB total bytes. The source
must enforce the supplied I/O limits itself; the consumer also checks elapsed
wall/monotonic time and byte limits. A blocked injected source is not forcibly
interrupted by this synchronous consumer. Production enrollment must verify the
producer's cancellation, bounded reads and namespace/path resolution.

The only accepted archive dialect is uncompressed POSIX USTAR, one regular member
named exactly the requested basename, UID/GID zero, mode 0444 or 0555, size 1 byte
through 8 MiB. Numeric fields use bounded octal; header checksum is verified.
Links, directories, devices, traversal, prefixes, PAX/GNU extensions, sparse files,
compression, extra entries, truncated payloads, nonzero padding/trailing data and
missing two-block terminators are refused. The result includes only the digest,
mode, size, identity/path and provenance, never file/archive contents. Collector
policy still applies its stricter per-profile 64 KiB and bootstrap mode limits,
expected hashes and two fresh stable rounds.

No Docker CLI compatibility is inferred: Docker documents `container cp` as a
container-path operation with tar output, not an image filesystem API. It does not
provide this complete no-follow ancestor/provenance contract. No temporary
container, archive extraction, worker command or daemon operation is added.
Unsupported layers, source resolution and runtime provenance remain unknown.
Credential inventory, root runtime/wrapper/dependency enrollment and all existing
OS/native/orphan/reboot/backup acceptance gates remain required separately.

Primary sources consulted:

- [Python 3.12 tarfile API](https://docs.python.org/3.12/library/tarfile.html)
  documents USTAR, header parsing, archive extensions and extraction hazards.
- [Docker container cp](https://docs.docker.com/reference/cli/docker/container/cp/)
  documents container-only paths, tar streams and link-following options.

All acceptance here uses private generated archive fixtures and injected ports.
The default 900-second/full-run-lease policy remains inactive.

Verification: initial 11 tests failed on the missing module; a negative ancestor
mode edge then failed before its range check. One fresh final review found no
Critical/Important issues and one Minor numeric-dialect gap. Its single fix pass
first reproduced four accepted checksum/device encodings, then rejected them
while preserving canonical unused zero fields. No rereview was performed.
Final 58 focused checks passed (10.011s), direct 16 tests passed (0.067s), and
Ubuntu-24.04 Python 3.12 full suite passed 769 tests (157.309s), actual exit 0.
Immutable `files-fixed-review-source.tar.gz` SHA256
`0f26eb31280a3d805bc44fd690b7733c254b9c3b75cb1ff301b5fa18123172f6`
matches both changed code/test files byte-exact. The full test namespace enabled
only loopback and reused existing project dependencies/HOME/cache. Durable source:
`/home/rslabinski/.local/share/hearth2-laptop-verification/files-fixed-20261101/source`.
The earlier 768-test pass predates the numeric fix and is retained as history.
These tests establish injected/source behavior, not physical OS/native acceptance.
