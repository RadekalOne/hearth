# Conditional directory metadata — second working increment

`DirectoryMetadataCapture` connects the compact evidence core to actual POSIX
directory metadata in private test folders. It reads names/stat/procfs mount
metadata only, NEVER credential-file bodies. It does not implement full source
extraction, native parsing, root discovery, enrolled host policy, outside helper
process isolation, credential inventory or start authority.

`RootDirectoryView` is a private frozen SUPPLIED binding: CoverageScope, canonical
absolute supplied root path, expected device/inode/ctime and source owner UID/GID. It is
not independent image/CID/host enrollment, and there is no auto-enrollment helper
or default live view. Missing/malformed/foreign-scope input refuses before I/O.
DirectoryMetadataResult contains only fixed status/reason, counts and the existing
conditional CoverageSummary; ALL physical families remain unresolved.

The reader opens every root-path component without following links, compares
the supplied root identity/owner/mount, and visits only parents in the fixed
auth/env/region/mcode-public, cli-auth/env/region,run,preferences directory shapes.
Requested paths outside those shapes and non-file obligations stay unscanned.
The requirements map remains a conditional supplied map, not an independently
audited complete native-consumer map. No homes/environment/profile search occurs.

Each visited directory is fully bounded/listed with every child acquired O_PATH
and typed before any read-open. Only supported directory components are reopened
via pinned procfd; inode signature and mount are checked again, temporary FDs
are closed on failures, and named ancestors/root identity are rechecked. Candidate
file bodies are never read-opened. Source owners need not be root; the declared
owner must match. Actual privileged helper/boot/namespaces/ancestor provenance
remain separate future acceptance gates.

Two passes must agree on every observed name, directory and entry signature,
source status and proof-parent choice. Directory snapshots provide the compact
core's absence evidence. Safe absent auth/cli-auth branches compact; a present
state file preserves store absence individually. Unsafe siblings make dependent
absence unscanned while independently present regular files remain present.
Symlinks are not followed, hardlinked/special candidates are unsupported, mount
crossings and inaccessible parents are unscanned. Case ambiguities never become
absence. A changed root/entry or exhausted acquisition budget returns a whole-root
unscanned result with no partial summary.

Metadata work counts visited directories plus entries across BOTH passes,
strictly below the supplied1..256bound. Consumer work remains separately below
the coverage core's limit; distinct budget-acquisition and budget-accounting
reasons are returned. Elapsed monotonic checks bound acceptance at1..10seconds,
with wall-clock/freshness checks through the core. This synchronous library
CANNOT kill/reap blocked OS calls; the planned separate bounded helper process
is still required before physical timeout/containment acceptance. No hard-kill
or production deadline proof is claimed by the in-process tests.

Tests use temporary synthetic folders and injected failures only: no real Mavis
directory/login file/environment/client/provider is accessed. Initial17tests RED
missing module, then17GREEN0.148s. Reopen-descriptor cleanup, post-reopen mount
checking and exact nested scope validation regressions RED22tests2failures+1error,
then22GREEN0.207s. One fresh review found an Important order-dependent branch
compaction/membership defect. Two regression methods failed before deterministic
shallow-first nonoverlapping selection and strict-descendant membership were
implemented;24metadata tests now pass0.068s and80credential tests pass0.143s.
The full immutable suite follows; no rereview is required.

Deferred minor: PurePosixPath retains parent-directory (`..`) components, so
lexical canonicalization is incomplete. The reviewed alias still had to match
the exact supplied root inode/device/ctime/owner/mount and no-follow traversal;
no binding bypass was demonstrated. Explicit component rejection remains a
required canonical-enrollment improvement before production use. This limited
fixture-level port is not a canonical-path or physical-enrollment certificate.

Final verification: 997 Ubuntu-24.04/Python3.12 tests PASS in 146.999s, actual exit 0, external networking disabled with loopback only. Immutable archive SHA256 2c84f2d8f8a0439308717db032168a0f9ed36961137345e90099df4a3245f951; all tracked Hearth2 Python/test bytes match. One fresh review completed and Important findings fixed; documented Minor canonical-component rejection remains deferred before production enrollment. Metadata-only conditional fixture component; no credential bodies read, complete acquisition or physical enrollment claimed. Full plan Tasks1-4 remain unfinished.
