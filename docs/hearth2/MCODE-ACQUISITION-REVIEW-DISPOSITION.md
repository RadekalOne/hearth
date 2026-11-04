# MCode acquisition review intake — 4 November 2026

Baseline: signed local `3b32ba2`; Claude's pre-implementation acquisition review
is attached as `mcode-acquisition-design-review.md` and in HM
`drawer_55aad043013fce11cfe92f6ca7f2bb7a`. Read-only review of proposed acquisition,
not a new parser/code review or evidence of actual acquisition. Codex verified
the current accounting, credential-policy, rootfs and collector contracts on
RSLABINSKI-PC. No native path resolver or private credentials were executed/read.

## Accepted requirements for the next design

- The17-kind map covers Claude's mapped artifact categories, not an exhaustive
  acquired universe. Enumerate all independently enrolled relevant roots and
  namespaces, including legacy sources and acquired configured-environment
  selectors. Discovery and namespace enumeration need explicit statuses. An
  incomplete discovery invalidates dependent root-scoped coverage; it must not
  leave the observed subset looking complete. Unexpected roots refuse.
- Model multiplicity by source scope: some artifacts occur per root, some per
  environment or namespace, and some are configured/runtime sources. Do not
  literally create17files for every namespace, infer absent roots from the
  acquiring process's HOME, or infer pairing from file contents. Deterministic
  group/role identity must bind enumerated root/env/region and immutable context.
- Add structured absence and unreadable-reason fields before a production
  adapter. No-evidence absence refuses; mismatched status/evidence combinations
  refuse. Oversize files become explicit unreadable(oversize) before bytes enter
  accounting; no truncation or retry with the source omitted. Readable malformed
  input remains present/unsupported, never absent.
- Implement Claude's R1–R7 as acquisition acceptance requirements: independently
  enumerated clean nearest ancestor, namespace/root discovery dependencies,
  unreadable/oversize distinctions, parser refusal preservation, fail-closed
  budgets/races, structured evidence, and separate evidence in each round.
  An enum is a required assertion type, NOT physical proof: bind its supporting
  acquisition record to the exact source, original context, round and parent
  enumeration. A cached observation cannot be made fresh by restamping it.
- Preserve strict whole-view rootfs refusal. Prefer a separate, narrowly scoped
  data-directory acquisition contract with per-source unknown/unscanned states;
  do not relax the existing image primitive or create a live-host backend under
  this intake. A socket can prevent absence claims for dependent siblings while
  an independently measured regular capability file may remain present.
  Exceptions must not clear parent/root discovery coverage or follow links.
- Filesystem acquisition cannot observe host-model-ref or process environment.
  Those remain unscanned pending separate authenticated runtime acquisition.
  MCP/plugin source paths remain unscanned until source mapping is complete.
  The proposed runner scope is Linux image/stopped-container views; this says
  nothing about credential absence on the Windows laptop or any other host.
- Carry all twelve review vectors into the eventual plan, including multiple
  roots, region conflicts, sockets, symlinks, unreadable namespace/env sources,
  oversize config, un-enrolled root, changing temporary files and legacy material.
  Mode000 alone is not a reliable unreadability fixture when a helper runs as
  root; use injected read failure or a separately verified permission boundary.

## Corrections and additional gates found against current source

1. **Current scan deadline is at most10seconds.**
   `CredentialAuditRequirements` caps seconds at10; `RootfsInventorySource.scan`
   enforces the lower policy deadline on command, wall and monotonic time. A scan
   taking more than60seconds cannot legitimately succeed under that contract.
   Keep all current time limits. A longer scan or changed freshness budget needs
   an explicit separately reviewed policy; it cannot be inferred from this review.

2. **No retained-fd extraction capability exists.**
   The rootfs helper closes descriptors and returns only tree/snapshot digests
   and counts. It exposes neither per-path records nor retained handles. A split
   inventory/extraction design therefore needs a new bounded authenticated capture
   contract, including handle lifetime, cleanup and stable original view binding.
   Independently reading paths later does not prove the bytes were in the earlier
   inventory. Any internal path/content linkage must remain protected evidence,
   not new public credential hashes, paths or fingerprints in summaries/HM/logs.

3. **Universe expansion also meets an existing budget gate.**
   Accounting requires entries plus declared groups strictly below the lower
   policy/64consumer cap; source entries separately stay below policy/256.
   Four roots with even one17-kind set each already have68entries before groups,
   so cannot fit. Namespace multiplicity adds more roles. The next design must
   define bounded aggregation and real consumer/source work accounting under the
   enrolled policy. Never truncate discovery, silently raise limits, or call
   independent per-root packets a complete host inventory.

4. **Mapping is not independent enrollment.**
   Claude's native resolution order, exact path patterns, account selection,
   namespace enumeration and lease-capability syntax are source-review inputs.
   This intake verifies their implications against existing interfaces, not every
   native anchor. Verify public bundle anchors before implementing those native
   semantics. The17-kind catalog is minimum coverage, not evidence that MCP paths,
   all launch/environment consumers or all historical arbitrary roots are known.
   Unsupported encrypted/capability material stays unknown until its parser is
   implemented; the current layer does not yet count a capability token.

## Status and next step

This intake changes documentation/continuity only. No acquisition adapter,
absence enum, reason enum, universe schema or deadline is implemented/approved
by the attached review. Current accounting still makes ALL physical families
unresolved, so caller-asserted absence has not become complete absence authority.

Next: draft a bounded acquisition design covering discovery dependencies,
structured evidence, protected snapshot/capture linkage, scope-specific kinds
and aggregate budgets. Settle the frozen-view/data-directory boundary before an
adapter; then follow design approval, TDD, one final fresh review and a new full
offline snapshot. No paid/client/helper/provider probes, credential reads,
live mounts/daemons/workers, deployment/push/merge or automation changes here.
Prior940PASS is historical code evidence only; no test rerun is warranted for
this documentation-only intake. Default900s/full-run activation remains inactive.
