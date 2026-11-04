# MCode data-directory acquisition port — draft for review

Status: draft4November2026 for Claude/Rad review; NOT approved for implementation.
Baseline signed local4970e59, accounting code3b32ba2. Inputs: Claude's acquisition
review (`drawer_55aad043013fce11cfe92f6ca7f2bb7a`), its repository disposition and
Rad's relayed per-root/deadline/in-pass-read recommendations. No runtime port or
contract changes are installed by this document.

## Goal, scope and chosen approach

Acquire bounded credential-shaped sources from independently enrolled Linux
runner data directories, preserving each root's uncertainty and original context.
Keep `RootfsInventorySource` unchanged as strict whole-frozen-view acquisition.
Use a separate discovery round and independent two-pass data-directory rounds;
each reads credential-shaped files during its pass, with no extraction phase or
descriptor retained between commands. These are proposed offline components;
implementation/tests use private trees and injected root/runtime facts only.

Alternatives considered: relaxing whole-rootfs rules would weaken a completed
primitive; one host-wide data-directory packet would unnecessarily couple root
failures and budgets; retained-handle extraction would introduce handle lifetime
and cleanup protocols. The relayed recommendation selects separate per-root
in-pass reads. Preserve strict rootfs and implement neither alternative.

This is bounded diagnostic source acquisition, NOT proof of all credentials on
the host. Unknown native consumers, credential-shaped files outside the audited
path map, runtime sources and full-rootfs semantic auditing remain gates. Windows
laptop stores are outside this Linux enrollment and remain unscanned. Do not
automatically enroll a host/root/mount/image/CID from current filesystem facts.

## Immutable enrollment and discovery

A versioned independently approved data-directory policy binds original host,
boot/initial namespaces, immutable image/nullable stopped CID, assembly and audit
policy, helper/interpreter dependency closure, supported source-map version,
configured-environment consumers, approved homes/root patterns, allowed root
identities/mounts and maximum roots. The cap is at most8; lower enrollment wins.
This is a NEW explicit scope artifact, not a reinterpretation of the old global
audit budgets. Repeating the old requirements hash in eight calls cannot grant
eight times its authority. No production enrollment source exists yet.

Discovery lists the independently enrolled relevant home/configuration sources
without using the acquiring process's HOME or inherited environment. Public
native source anchors must verify path resolution/profile/migration semantics
before implementation. Configured env means exactly the enrolled consumers;
unknown shell expansion, arbitrary launch scripts, unresolved paths, unreadable
sources or incomplete home coverage make discovery incomplete. No native startup
or helper command is run to resolve data directories.

The discovery result binds a fresh round ID, original context/enrollment, exact
root identity set and namespace declarations, status and protected evidence.
Enumerate legacy roots and namespace directories even when not currently selected.
Discovering an un-enrolled root or more than the cap refuses the discovery packet.
That refusal has a bounded representation: a batch unknown-universe refusal code
and unscanned results for the at-most8ENROLLED roots, not a purported successful
list of the first8discoveries. Do not accumulate or publish all unexpected roots.
At most one protected bounded overflow witness may be retained; public output
contains only the refusal enum/count, and does not claim the actual root total.
Stop discovery at this refusal; no root scans run from the partial universe.
Missing/unreadable/unscanned discovery dependencies make ALL dependent root kinds
unscanned; an observed subset cannot stand in for unknown roots. Failure to obtain
stable namespace coverage inside one known root affects that root's dependent
namespace kinds; it cannot clear another root's uncertainty.

Root absence requires clean two-pass home and configured-source discovery.
Namespace absence requires the corresponding clean ancestor listings. The source
universe is hierarchical: root-level, env-level, namespace-level and non-file
sources have distinct multiplicity, not17literal files in each namespace.

## Independent root rounds and work limits

One discovery round, then one round per discovered root. Each round performs two
passes and has a fixed hard wall/monotonic/command deadline no greater than10s
(lower policy deadline wins), fresh original host/runtime sampling, and bounded
source/byte/output work. A root round's inputs are only its immutable enrollment,
the immutable discovery evidence and its own context; no measurement/cache,
status, handles or token comparison state is shared between roots. Read-only
helper code/policy constants are not shared measurement evidence.

Suggested initial caps for review: discovery at most8roots,256listed entries and
1MiB configured-source input; root round at most256visited entries,1MiB read over
BOTH passes, at most64credential candidates and nesting at most5relative path
components for the reviewed fixed path map. The stricter enrolled bounds win.
Work caps are exclusive (reaching a work cap fails); the enrolled root-count cap
is inclusive (exactly8may be allowed, a ninth refuses).
Every directory entry and read attempt counts, including refused siblings and
oversize probes. Reaching source/byte/time/work limits invalidates the WHOLE root
round: no partial present/absent packet escapes, all its kinds become unscanned.
Other roots retain their own results. Root-count/unexpected-universe refusal is
batch-wide. Do not loop/retry a failed round or raise caps automatically.

One root's accounting input separately stays below existing policy/256entries,
1MiB input bytes,64KiB per file and64entries-plus-groups consumer work. The new
scope policy explicitly authorizes independent per-root accounting; it does not
remove these caps. Root acquisition budgets and accounting budgets are separate
and both must be enforced. A root that cannot be represented within either budget
is wholly unscanned(budget), not a truncated or split complete root.

Per-root scope does not guarantee every namespace-expanded root fits64consumer
work: all source instances AND their groups count. Two roots with8OAuth
namespaces each mean16OAuth groups and32store/state source entries, not32groups.
Projection/selector/selection instances add work. A future larger per-root format
needs explicit reviewed policy/implementation changes; this draft does not raise
the old64cap. Test the fully populated namespace case as a supported-size or
explicit unscanned(budget) outcome, never silently omit inactive namespaces.

Enrollment bounds multiplication by at most9rounds (discovery plus8roots), with
each round independently bounded. These are diagnostic execution limits, not a
promise that all roots fit a collector round's existing global freshness window.

## Descriptor-relative pass and file classification

Pin the independently enrolled root/ancestor mount/device/inode identity; verify
actual root privilege, boot and namespaces through the enrolled independent
runtime source. Do not follow root symlinks or silently cross mount boundaries.
A symlinked root remains unscanned. An explicitly enrolled root may itself be a
separate mount; an unexpected descendant mount stays unknown/unscanned for its
dependent sources. Nothing here establishes mount/image/CID provenance by naming
a directory. Strict whole-rootfs source acceptance is unchanged.

List every entry in each visited directory, including hidden/transient entries,
bounded and sorted. Credential-shaped paths come only from the audited fixed map;
unknown consumers/path semantics remain unscanned. Other entries are typed and
their stable metadata contributes to a protected listing fingerprint. **No read
means no content hash** for those entries; metadata fingerprints never prove
credential absence or content auditing. No whole data-directory walk is claimed.

For each candidate, acquire O_PATH|O_NOFOLLOW, fstat/typecheck before read-open,
verify regular/single-link/same authorized mount, reopen the pinned inode through
trusted /proc/self/fd, then bounded read and fstat again. Use nonblocking/no-follow
guards where applicable; never read a socket/FIFO/device or follow a symlink.
Verify named-link and ancestor/root identity again. Compare inode/device/mount,
mode/ownership/link count, size, mtime and ctime, not just size/mtime. A changed or
unreadable existing candidate is unreadable(io/permission/type), never absent.

Read/probe at most65537bytes, charged to work. Because accounting currently accepts
only raw lengths STRICTLY BELOW65536, size or observed length >=65536 is
unreadable(oversize), including exactly64KiB; never pass/truncate those bytes.
An empty existing file is present acquisition evidence. Extend the observation
contract to allow present raw=b''; its existing parser may then return unsupported.
It is never absent or unreadable simply because empty, and it cannot make the
entire root disappear. Nonpresent statuses still require raw=None. This deliberate
accounting change must have its own regression before adapter implementation;
do not fake nonempty bytes or introduce an unreadable(format) substitute.

Both passes repeat listings/reads independently and compare all candidate content
hashes and identity/listing facts inside protected acquisition evidence. A
disagreement invalidates the root round; no repeated-until-stable retry. A normal
lease socket is typed as unsupported, not opened: it prevents dependent sibling
absence claims, but an independently stable regular cap may be present. Unsupported
siblings never erase their effect on namespace/root discovery or broader coverage.

Hash comparisons against a frozen-view record are OPTIONAL and supported only if
a separate authenticated port supplies the same original artifact/context binding.
Current whole-rootfs output has no per-path records and cannot supply that port.
Absence of a comparison source remains explicit unscanned linkage. A verified
same-target mismatch adds a conflict counter and marks affected evidence
unresolved/unsupported; the root may remain diagnostically accounted, but never
clean or absence-authoritative. The two passes of a single root must still agree.

## Evidence, accounting and composition

Extend observation contracts deliberately before adapters: fixed absence_evidence
enum (enumerated-parent/namespace/roots), unreadable_reason enum (permission,
oversize,type,io), plus bound universe/round/root evidence. Enforce exact
status/field compatibility. Enum values are assertions, never physical proof.
Absence needs independently verified clean nearest-parent two-pass enumeration,
same original source/mount/context and current round. Unknown/refused/symlink or
socket siblings make dependent absence unscanned. File exists but parser refuses:
present→unsupported. No failed acquisition or parsing becomes absent.

Group identity derives from enumerated root/env/region and declared role/scope,
not auth-state content or a region default. Cross-labelled files stay present/
unsupported. Namespace identity alone does not resolve an account: do not invent
a43-character account selector for absent/ambiguous stores. Current OAuth parser
accepts a declared single-account context; unsupported multiple-account selection
or missing enrolled account identity remains unknown. A typed acquisition packet
must preserve such uncertainty even if it cannot instantiate the current
SourceManifest; its accounting adaptation is unscanned(context), never fabricated.

Host-model-ref and live process environment stay unscanned without a separate
runtime port. Configured environment belongs to discovery and its original evidence
must not be reused as new per-root acquisition; diagnostic references may bind
to it. MCP/plugin consumer path coverage remains unscanned until source mapping
is independently checked. Capability/legacy-encrypted bytes remain present/
unsupported until their own supported parsers exist; do not report a token count
from an unimplemented parser.

After successful bounded discovery, account each root separately, retaining one
explicit result for EVERY enrolled or discovered root, including failures, and a
batch-level discovery status. Failed discovery instead uses the bounded
unknown-universe representation above; a partial root list is never success. Composition
does not sum statuses into a complete-host boolean and does not allow rootA to
replace missing rootB. Credential-material counters may overlap (e.g. projections);
do not add them as distinct accounts/credentials. All physical coverage families
remain unresolved; no collector observe/complete/credentials:none/start packet.

Each root measurement must fall within its own current begin..finish and60s
freshness window. At composition recheck discovery/root ages: stale roots become
unscanned(stale) in current diagnostics, while immutable historical evidence keeps
its original timestamp. Stale/incomplete discovery invalidates all dependent
coverage. No restamping, caching round1absence into round2, or reuse of prior bytes.
The collector's existing round-begin/global60s gate remains unchanged. Future
complete integration must schedule all required fresh work within that gate or
refuse; independent10s rounds across8roots can exceed it. No silent extension.

## Privacy, testing and acceptance

Raw bytes and per-file/path/identity hashes live only in bounded private acquisition
memory while accounting runs; no secret bytes or credential fingerprints in public
results, repr, errors, HM or logs. Public results expose fixed enums/counts only;
protected round/reference handles have a separate enrollment/provenance contract.
Strip inherited helper environment/FDs; use pinned stdlib/interpreter/command
closure, bounded output/time and verified kill/reap cleanup. No native client or
provider is launched. Failure to authenticate helper/host/mount/runtime refuses.

Run per-root parsing/accounting inside the same enrolled root-round helper while
the bounded private buffers exist. Return only the bounded diagnostic envelope;
do not send credential bytes through stdout, a log or a widened command transport.
The existing64KiB output cap remains. This needs a pinned approved parser
dependency closure (including PyYAML for config), not an assumption that the old
stdlib-only rootfs helper can import it. Missing/unverified parser closure refuses
supported parsing or leaves the relevant acquisition unsupported; it never enables
environment-dependent imports. Default production wrapper/runtime stays absent.

Plan must include Claude's V1–V12 and add: exactly65535/65536/65537bytes; empty
file; unreadable injection despite root privilege; changed ctime/inode with same
size/mtime; root timeout/budget with clean sibling root; source-only vsmetadata
hash distinctions; fully populated namespaces exceeding accounting caps;
8root schedule causing stale discovery/early root; mismatched frozen digest that
increments conflict AND preserves unknown; absent/ambiguous account context;
un-enrolled ninth root; both rounds using fresh source-specific absence evidence.

Physical host/root enrollment, MCP path mapping, complete consumer closure and
collector integration remain unconfigured. Initial work is offline contracts,
private-filesystem producers and injected failure tests; no real credentials,
Mavis configuration, native clients/providers, mounts/daemons/workers or services,
global installs/account changes, external posts, push/merge or automation changes.
Default900s/full-run stays inactive. After review and design approval: write the
implementation plan, TDD inline, one fresh final code review, new immutable full
offline suite, signed local commit and HM checkpoint/readback. No implementation
or OS/native acceptance is claimed by this draft.

## Draft builder check

One fresh read-only design check found an ambiguity between the eight-root cap
and retaining every discovered root on unexpected-universe failure. The author
resolved it with the bounded refusal representation above. No user-specific
authority choice was inferred. This is a builder check, not Claude's substantive
acquisition review or approval to implement. Source-mapping/provenance and all
runtime gates remain explicitly open.
