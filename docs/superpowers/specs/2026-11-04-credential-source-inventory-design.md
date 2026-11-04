# Credential source inventory design

Status: approved by Rad 4 November 2026, after local parser review fix `8b400cd`.
The offline implementation below describes no deployed scanner.

## Goal and approach

Build a bounded credential-source accounting layer in the existing Python
pipeline. Every expected source must have an acquisition and interpretation
result, including unsupported, absent, unreadable and unscanned sources. This is
the missing connection between `RootfsInventorySource`, the pure MiniMax parsers
and a future independently authenticated complete inventory producer.

Continue with Python stdlib and existing parser dependencies. The first build
is an offline accounting component, not a filesystem crawler, native client or
collector backend. Adding daemon/credential access now would mix unresolved
acquisition authority with parser coverage. Extending each parser independently
would leave no single check that all required sources had been accounted for.

## Existing evidence and limits

`CredentialAuditRequirements` pins image, assembly, manifests, parser closure and
budgets. `RootfsInventorySource` acquires a bounded whole-view tree summary; its
digests cannot identify credential consumers or supply parser bytes.
`MiniMaxConsumerParser`, `MiniMaxOAuthParser` and `MCodeConfigParser` classify only
supplied bytes or declared analysis context. Their output proves no physical
custody, complete discovery, effective credential route or current login.

`RootAssemblyCollector` requires a separate fresh complete credential inventory
in both observation rounds. That backend remains absent. The new accounting
type must have no `observe` method and must not emit the collector's success
packet or be installed as its credential backend.

## Required source accounting

Use the catalog in `docs/hearth2/CLAUDE-PARSER-REVIEW-2026-11-04.md` as the initial supported
MCode 0.4.1 requirements map. Stable source kinds cover Pi auth, OAuth primary
store/state, three projection scopes, lease capability, account identity,
projection/scope/region selectors, legacy encrypted material, YAML config,
host ModelRef, MCP/plugin consumers and explicit environment consumers.

Paths, namespaces, aliases and consumers must ultimately come from an
independently audited manifest. A caller-picked data directory or this static
catalog never establishes a complete source universe. Each required coverage
family from `CredentialAuditRequirements.require_scope` remains explicit;
post-create accounting adds container rootfs/configuration/native consumers and
mount sources. Image results cannot substitute for container results.

The first component takes a bounded immutable requirements map and bounded
source observations from injected acquisition ports. Each observation binds the
exact original image, nullable immutable container ID, assembly, audit-policy
digest, source kind and opaque source identifier. It carries a fresh observation
time and provenance reference. Context mismatches, duplicate/conflicting source
identifiers, unsupported schemas and exhausted budgets refuse the whole packet.
Copy nested inputs before classification; do not retain mutable caller objects.

Related sources use explicit manifest group IDs and role IDs, never matching by
filename, source kind or iteration order. An OAuth pair must share the exact
original context plus declared data-directory/build-environment/region group;
projection comparison also names its primary group and projection scope.
Require one member per role; a missing partner stays unscanned/unknown, and a
conflicting context or duplicate role refuses. No cross-group token comparison
or namespace inference is permitted. These are synthetic relationship inputs,
not independently established selection or custody.

Missing observations become unscanned, never absent. Absence needs its own
explicit acquisition evidence and remains an assertion from the injected port
until authenticated physical acquisition is implemented. Unsupported content
stays unknown even if some known material was counted. Parser refusal is an
unknown interpretation, not a native-client abort or credential absence.

The initial layer uses synthetic observations only. Production enrollment and
acquisition adapters are deliberately unconfigured; caller declarations and
hashes must never be presented as independent physical attestation.

## Result and privacy contract

Return an immutable diagnostic summary: required/observed/unscanned/unreadable/
unsupported source counts, known credential-material counts, and unresolved
coverage families. Preserve separate counts for known material and unknown
semantics; material categories can overlap and must not be added as distinct
credentials. OAuth expiry or scope differences never erase retained material.

Every manifest entry declares one fixed coverage family from `require_scope`;
unknown families refuse. Report unaccounted-source counts by required family,
but retain ALL required families as unresolved in this phase because no physical
complete producer exists. Empty or wholly unsupported families remain unresolved.
Even perfect observation of a caller's shortened catalog cannot clear a family.
The fixed artifact map expresses minimum obligations, not exhaustive enrollment.

Even an all-supported synthetic fixture produces only a candidate accounting
summary. No `complete:true`, `credentials:none`, start authority or automatic
retry/adoption is available in this phase. No arbitrary success flag is accepted
from a caller. Any future complete producer needs separately enrolled exhaustive
manifests, audited consumer semantics, authenticated acquisition, both fresh
rounds and OS/native acceptance before wiring to the collector.

Do not persist source bytes, tokens, identities, paths, URLs, raw exceptions,
credential hashes or fingerprints in summaries/logs. Use fixed redacted errors
and opaque bounded IDs; even opaque IDs are not provenance. Read no ambient
environment or real user credential files. Bound source count, aggregate input
bytes, nesting and work by the lower of policy and implementation limits;
reaching a limit refuses rather than truncating to success.

The public result allowlist is fixed field names, exact nonnegative integer
counters and internal source-kind/coverage/status enums only. No caller ID,
group, path, provenance reference or parser string passes through into output,
repr or errors. Raw byte fields and acquisition metadata are excluded from repr;
references are validated and compared only inside the supplied packet. Auditable
production reference retention needs a separate protected evidence contract.

Author decisions from the fresh design check: explicit role/group pairing,
all physical coverage families unresolved, and the output allowlist above. None
requires broader authority or a user-specific configuration choice.

## Implementation and acceptance sequence

1. Add the immutable requirements/observation/result contracts and deterministic
   accounting. Test missing, duplicate, wrong-image/CID/policy, stale/future,
   unreadable, unsupported and budget-exhaustion cases before implementation.
2. Adapt existing parser summaries using fake-token fixtures. Preserve unknown
   counters, projection primary-metadata gaps, conditional resolver assumptions
   and raw stored material even when selection is disabled or defaults change.
   Unsupported artifact kinds remain explicit unknowns.
3. Review the whole change once in a fresh context, fix important findings in one
   test-driven pass, then verify an immutable source with the full offline suite.
   Save a signed local commit, progress evidence and an HM checkpoint/readback.

Use the existing laptop feature checkout and isolated Ubuntu verification
environment. Preserve all user changes/history. No global installations, real
credential reads, provider/client/helper probes, worker/service activation,
push/merge, external posts or automation changes. The default 900-second/full-run
policy remains inactive. Physical acquisition, consumer closure and full native/
OS acceptance remain later explicit gates rather than claims of this build.

## Implemented API and conservative interpretations

`hearth2.credential_sources` provides frozen private-repr `SourceContext`,
`SourceRequirement`, `OAuthSourceGroup`, `SelectionSourceGroup`, `SourceManifest`
and `SourceObservation`, plus a frozen public `SourceAccountingSummary`.
`CredentialSourceAccounting(clock=..., monotonic=...).account(manifest,
observations, begin=...)` accepts exact typed immutable tuples and aware times.
Times must use exact builtin `datetime` and fixed-offset `datetime.timezone`
objects; custom timezone implementations (including ZoneInfo) are unsupported.
This prevents executing caller timezone callbacks at the redaction boundary.
The context must match the audit policy and every observation; time must fall
within the current round and60seconds. No acquisition backend is provided.

The full minimum17-kind source catalog is mandatory even for diagnostic input.
Unknown source kinds, duplicate IDs/group roles and missing declaration groups
refuse. An observation omitted from the tuple is unscanned. Nonpresent sources
must have no bytes, and even absent assertions require fresh provenance metadata.
The default parser adapters are pinned to the already reviewed MCode0.4.1 code.
Unsupported kinds remain unknown; they are not passed through a generic parser.

Conservative work accounting counts each manifest entry AND each declared group
against the lower policy/64 consumer budget. Entries separately use the lower
policy/256 source budget. Both reject equality. Source bytes must be below64KiB,
and aggregate input below the lower policy/1MiB budget. Finite nondecreasing
monotonic elapsed time must remain below the policy's seconds limit. End-of-work
wall-clock rollback or loss of freshness refuses the entire result.

OAuth pairs contribute primary material once; projection copies contribute their
own retained material, not a distinct-account total. Standalone projections keep
primary metadata unknown. Mismatched projections retain counts and unsupported
status. Conditional config/host analysis retains raw key/header/unparsed counters,
but stays unsupported for complete consumer accounting. Missing host selection
partners never become an invented empty config. Parser refusal yields unsupported
interpretation; it does not zero the unknown source or prove native termination.
Raw config schema counters and bounded ModelRef material counters are acquired
independently of conditional selection, so missing partners, unused host input
or a native migration fence cannot erase syntactically known stored material.

Public output contains source-status counts, a fixed material-counter tuple,
unaccounted counts per required family and ALL unresolved physical families.
Stored material/alert counters may overlap; they are not a credential total.
`parsed_sources` means supplied syntax was interpreted, not complete consumer
semantics or physical provenance. A partial unknown record can contribute known
material while its source stays unsupported. No caller string or fingerprint is
returned. These diagnostics do not satisfy RootAssemblyCollector's inventory API.

## Verification on the laptop,4November2026

Initial25missing-feature regressions failed, then35focused tests passed along with97existing parser tests. One fresh code review found3Important/noCritical/noMinor: raw config material loss with a missing host partner, nested string-subclass binding bypass, and caller timezone exception leakage. The single TDD fix pass reproduced4failures+1error across39tests before correction, then all39passed. No rereview.

Final full Ubuntu-24.04/Python3.12 suite:940tests PASS142.301s, actual exit0, external network disabled with only loopback enabled. Immutable credential-sources-20261104-source.tar.gz SHA256 `5d4fe10a51cc05021f9ce838d121e0651622c06c6ad9b343d79113b964aa69d0`; all tracked Hearth2 code/test bytes match; documentation alone follows. No real credential, client, helper, provider, worker, daemon or OS acceptance was attempted.

Retained rulings: the full17-kind minimum is mandatory, costing smaller synthetic catalogs compatibility; entries plus groups both consume the conservative consumer budget, costing some capacity; custom/ZoneInfo timezones must be normalized to builtin fixed-offset values by callers, costing timezone flexibility; physical acquisition/enrollment/native/account/OS proof remains separate work, so these diagnostic summaries cannot start workers or satisfy complete inventory. The reviewer deferred full-suite checking to the parent; the final940-test gate satisfies that check. No deferred minors.
