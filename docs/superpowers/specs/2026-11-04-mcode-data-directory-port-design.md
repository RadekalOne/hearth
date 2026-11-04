# MCode data-directory acquisition port — draft for review

Status: revised design approved by Rad4November2026 at4ae68fb for implementation
planning. The four requested design decisions are specified below. Approval does
not establish production enrollment or authorize runtime/service activation.
Baseline signed local4970e59, accounting code3b32ba2. Inputs: Claude's acquisition
review (`drawer_55aad043013fce11cfe92f6ca7f2bb7a`), its repository disposition and
Rad's relayed per-root/deadline/in-pass-read recommendations. No runtime port or
contract changes are installed by this document.

## Goal, scope and chosen approach

Acquire bounded credential-shaped sources from independently enrolled Linux
runner data directories, preserving each root's uncertainty and original context.
Keep `RootfsInventorySource` unchanged as strict whole-frozen-view acquisition.
Use discovery checkpoints before AND after independent two-pass data-directory rounds;
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
identities/mounts, maximum roots and discovery_to_composition_seconds. The cap
is at most8; lower enrollment wins. The batch window is an explicit positive
integer policy value (no inferred default), enrolled and
at most120seconds; it is separate from each10s round and the collector's60s gate.
This is a NEW explicit scope artifact, not a reinterpretation of the old global
audit budgets. Repeating the old requirements hash in eight calls cannot grant
eight times its authority. No production enrollment source exists yet.

Each discovery checkpoint lists the independently enrolled relevant home/configuration sources
without using the acquiring process's HOME or inherited environment. Public
native source anchors must verify path resolution/profile/migration semantics
before implementation. Configured env means exactly the enrolled consumers;
unknown shell expansion, arbitrary launch scripts, unresolved paths, unreadable
sources or incomplete home coverage make discovery incomplete. No native startup
or helper command is run to resolve data directories.
"Listing-only" means no credential-body acquisition: each checkpoint MUST still
independently read the exact bounded configured-environment sources needed for
root resolution and protected content-digest comparison. Metadata alone cannot
prove those source bytes agreed. Do not reuse checkpoint1bytes/digests as fresh
checkpoint2measurements.
Each checkpoint performs one bounded listing/configured-source-read set; the
before/after checkpoints are independent universe measurements. Each root's
own two passes remain separately required inside its round.

The discovery result binds a fresh round ID, original context/enrollment, exact
root identity set and namespace declarations, status and protected evidence.
Enumerate legacy roots and namespace directories even when not currently selected.
Discovering an un-enrolled root or more than the cap refuses the discovery packet.
That refusal has a bounded representation: a batch unknown-universe refusal code
and unscanned results for the at-most8ENROLLED roots, not a purported successful
list of the first8discoveries. Do not accumulate or publish all unexpected roots.
At most one protected bounded overflow witness may be retained; public output
contains only the refusal enum/count, and does not claim the actual root total.
Stop discovery at this refusal; no root scans run from an initially partial universe.
If the final checkpoint refuses, invalidate every root's batch acceptance.
Missing/unreadable/unscanned discovery dependencies make ALL dependent root kinds
unscanned; an observed subset cannot stand in for unknown roots. Failure to obtain
complete namespace enumeration AT A DISCOVERY CHECKPOINT is an incomplete
universe and invalidates the batch. A root-round content/permission failure can
remain root-local only when both discovery checkpoints independently establish
the same complete universe. It cannot clear another root's uncertainty.

An enrolled env-named root that is absent needs enumerated-parent evidence for
its nearest existing ancestor on an enrolled mount, corroborated at both discovery
checkpoints. A parent outside enrolled mounts is unscanned, not absent. Do not
launch the native client to create the missing root. Root absence otherwise
requires clean home and configured-source discovery at both checkpoints.
Namespace absence requires the corresponding clean ancestor listings. The source
universe is hierarchical: root-level, env-level, namespace-level and non-file
sources have distinct multiplicity, not17literal files in each namespace.

## Independent root rounds and work limits

Fixed order: initial discovery checkpoint, one root round per enrolled root in
sorted canonical enrolled-root-ID order, then final discovery checkpoint and
composition. Absent/unavailable roots still receive explicit bounded outcomes.
Root identity, namespace sets, configured-source digests and all original context
must agree across both checkpoints; disagreement, incomplete discovery or batch
window overrun yields unknown-universe(stale) and EVERY root becomes unscanned.
Checkpoint causes (changed, unreadable, budget, unexpected-universe) remain fixed
internal reason enums; no successful subset is returned.

Each round performs its required stable listing/read checks and has a
fresh helper process created with exec, stripped inherited env/FDs, and verified
termination/reap BEFORE the next helper starts. No persistent multi-root helper
or shared credential address space is allowed. Each root round performs two
passes and has a fixed hard wall/monotonic/command deadline no greater than10s
(lower policy deadline wins), fresh original host/runtime sampling, and bounded
source/byte/output work. A root round's inputs are only its immutable enrollment,
its own discovery slice (this root identity, namespace declarations and the
initial discovery digest/batch ID) and its own context; never the full root list
or other root identities. The coordinator checks universe agreement separately.
No measurement/cache,
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
Ordinary root acquisition/accounting failure does not stop later root rounds or
the final discovery checkpoint. Root-count/unexpected-universe refusal is decided
at discovery checkpoints. Do not loop/retry a failed round or raise caps automatically.
Safety exception: unverified reap/containment, host authentication loss or broken
coordinator integrity halts further launches immediately; pending roots become
unscanned(integrity), never a complete batch. Continuing after an unreaped helper
would violate structural isolation. This is not an ordinary root-data failure.

One root's accounting input separately stays below existing policy/256entries,
1MiB input bytes,64KiB per file and64entries-plus-groups consumer work. The new
scope policy explicitly authorizes independent per-root accounting; it does not
remove these caps. Root acquisition budgets and accounting budgets are separate
and both must be enforced. A root that cannot be represented within either budget
is wholly unscanned(budget-acquisition or budget-accounting), not a truncated or
split complete root. Keep those reason enums distinct.

Hierarchical absence is the chosen accounting-contract extension: a structural
coverage node, not an eighteenth artifact kind, represents PROVEN absent leaves
under an enrolled root/namespace branch. It carries exact original context,
root/env/region/branch, enumerated-parent/namespace/roots evidence and current
round binding. Its covered leaf roles derive from the fixed audited path map,
never arbitrary caller lists or a claim that an entire OAuth pair is absent.
One node costs ONE accounting work unit, with no invented account/OAuth group
for its absent leaves. It satisfies minimum-kind coverage only for those exact
leaves; disjointness, no duplicate coverage and no present/unreadable/unknown
descendant hidden beneath a node must be validated before counting.

Auth and cli-auth branches need their OWN absence evidence. An absent auth
namespace cannot conceal a present cli-auth projection. Root-level shared/legacy
artifacts, configured environment, runtime host refs and unmapped MCP consumers
are never covered merely because an OAuth namespace is absent. A namespace
directory present but empty can compact only the mapped leaves individually
proven absent by its clean enumeration; existence of a directory alone is not
enough. A present state with a missing store retains store absent(enumerated-parent)
plus state present. Pair interpretation is unknown/unsupported; do not erase the
store evidence or manufacture a single absent/unsupported acquisition record.

Two accounting changes are required: validate structural nodes as satisfying
the fixed-kind/role obligations they prove, and charge each node once without
expanding its absent roles/groups into consumer work. Keep logical required/
absent leaf counts distinct from physical observation/work counts, with explicit
coverage_nodes/covered_absent_sources/accounting_work_units counters. Logical
leaves still obey the separately enrolled source cap; compaction does not make
acquisition enumeration or metadata work free. Gate this extension with the new
root-scope schema/policy version; do not reinterpret old flat manifests/hashes.

Per-root scope and compact absence do not guarantee every populated root fits64consumer
work: all source instances AND their groups count. Two roots with8OAuth
namespaces each mean16OAuth groups and32store/state source entries, not32groups.
Projection/selector/selection instances add work. A future larger per-root format
needs explicit reviewed policy/implementation changes; this draft does not raise
the old64cap. Test the fully populated namespace case as a supported-size or
explicit unscanned(budget-accounting) outcome, never silently omit inactive
namespaces. Claude's approximate69units for8present namespaces is a warning,
not a pinned universal cost formula; derive exact costs from the audited map.
One/two present namespaces plus absent branches must fit through compact nodes
in the acceptance fixtures, rather than paying full per-file/group absence work.

Enrollment bounds multiplication by at most10rounds (two discoveries plus8roots), with
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

Visit ONLY mapped directories: root, auth/, auth/<env>/,
auth/<env>/<region>/, auth/<env>/<region>/mcode-public/, cli-auth/,
cli-auth/<env>/, cli-auth/<env>/<region>/, run/ and preferences/. Allowed env/region
values come from the verified fixed map. List every entry in those visited
directories, including hidden/transient entries,
bounded and sorted. Credential-shaped paths come only from the audited fixed map;
unknown consumers/path semantics remain unscanned. Other entries are typed and
their stable metadata contributes to a protected listing fingerprint. **No read
means no content hash** for those entries; metadata fingerprints never prove
credential absence or content auditing. No whole data-directory walk is claimed.
Never descend sessions/, logs/, skills/, plugins/ or other unmapped directories.
Their directory entries count once at the mapped parent; their contents are not
visited. Large top-level listings can still exhaust the root budget; do not skip
entries to avoid that. This restriction is NOT MCP/plugin coverage or an exclusion
from the separate complete consumer/rootfs audit.

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
Verified map-specific auth.lock and exact atomic-write temporary-name patterns
are known-transient siblings. Stable regular or directory entries of those exact
types are typed/fingerprinted without descending/reading and do not alone block
other file absence; a new/disappearing/changed entry between passes still fails
stability. Symlink/socket/FIFO/device/multi-link variants are NOT exempted because
their names look transient. Verify native naming anchors before implementation;
do not exempt a generic attacker-chosen *.tmp suffix.

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
A digest derived from a discovered auth-home path may only check an independently
enrolled account value. It cannot establish account truth; verify the exact native
derivation/encoding from pinned source before implementing even that check.

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
window when that root helper accounts it. At root start verify that initial
discovery belongs to this batch and is inside the enrolled batch window, not a
new60s universe age test. The coordinator accepts diagnostic root results only
after agreeing final discovery and composition inside
discovery_to_composition_seconds (<=120s, measured wall+monotonic from initial
discovery begin through final helper reap and composition). Unknown/stale universe
invalidates ALL root absence claims, not just late roots. Original per-root
timestamps are retained; earlier evidence is not relabelled globally fresh.
No restamping, caching earlier-batch absence, or reuse of prior credential bytes.
The collector's existing round-begin/global60s gate remains unchanged. This
diagnostic batch window is not its start/complete authority. Later integration
must schedule all REQUIRED enrolled-root evidence under that gate or refuse;
choosing a genuinely smaller enrolled universe needs independent scope approval,
not silently dropping roots to meet60s. No collector wiring is included here.

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
8root schedule within enrolled120s with old early-root timestamps preserved;
discovery disagreement/overrun invalidating ALL roots; mismatched frozen digest that
increments conflict AND preserves unknown; absent/ambiguous account context;
un-enrolled ninth root; both root passes and discovery checkpoints using independent
fresh source-specific evidence. Also: compact absent auth/cli-auth branches without
hiding present projections; store absent/state present; 1–2present+6–7absent
namespaces fitting work cap; fully populated root explicit budget-accounting;
large sessions/ directory never descended; enrolled env-root absent outside mount
unscanned; stable auth.lock vs new temporary file; root helper reap failure blocks
next launch; no cross-root evidence in helper argv/FDs; no early exit on ordinary
root failure; empty file→present unsupported with zero parsed/unparsed field
counters (zero counters do not mean absence).

Expired discovery fails root-round preflight without launching another helper.
The coordinator still records outcomes for every remaining enrolled ID and
reaches the final discovery decision (which can refuse immediately on the
expired batch window without launching a new process). No helper starts after
its authorization/window expires. This is batch preflight failure, not using a
root's ordinary data failure to skip other roots.

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

## Disposition of Claude's review of bfc2cff

Full review: attachment7627ad77/mcode-data-dir-port-review.md and
HMdrawer_6950d1b84c6f34cd9a58afcdcfcf0df2. These are design revisions, not code
fixes, runtime acceptance or a claim Claude approved this revised commit.

| Finding | Decision recorded in this revision |
|---|---|
| F1 blocking | Adopt compact structural absent-coverage nodes, fixed-map leaf validation and one work charge; no fake account groups, no cross-branch masking. Fully populated oversized roots remain explicit budget-accounting. |
| F2 important | Enumerate only the explicit mapped directory set; never descend sessions/logs/skills/plugins. |
| F3 | Separate budget-acquisition and budget-accounting reasons. |
| F4 blocking | Discovery before and after roots; require stable universe/configured-source binding. Changed, incomplete or stale universe invalidates ALL roots. |
| F5 important | Explicit enrolled batch window <=120s, separate from local10s/60s checks and unchanged collector60s authority. |
| F6 important | Absent enrolled env-root requires clean nearest existing parent on an enrolled mount; outside mount stays unscanned. |
| F7 important | Preserve store absence independently when state is present; interpretation failure never erases original source evidence. |
| F8 | Known native lock/tmp type/name patterns do not alone block sibling absence; races and unsafe types still do. Generic tmp exemptions forbidden pending verified naming map. |
| F9 important | Fresh exec helper for every eligible checkpoint/root round; verified reap before next launch, no persistent cross-root credential process. |
| F10 important | Root helper receives its own discovery slice only. Coordinator alone sees the bounded universe. |
| F11 | Sorted enrolled-root order, no early exit for ordinary data failures; integrity/reap failure or expired authorization prevents unsafe further launches. |

Small items: empty present bytes are explicitly supported by the proposed new
observation contract and parse as unsupported; account digest derivation can only
check enrolled identity; MCP source mapping remains open. Acceptance vectors pin
all these changes. The original flat accounting code at3b32ba2 is unchanged.
