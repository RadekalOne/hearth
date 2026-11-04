# Compact absence accounting — first working increment

Rad chose small working increments with concrete examples on4November2026,
instead of further plan-approval gates. This increment implements the pure
absence/evidence validator underneath planned root accounting. It does not
complete the data-directory acquisition plan or its authority/enrollment task.

`CoverageRequirements.create(scope,sources,groups,source_limit=256,work_limit=64)`
pins immutable DECLARED logical file requirements by a private checksum.
`CoverageAccounting(clock=...).account(requirements,observations,coverage_nodes,
begin=...)` checks typed bounded current-round facts and emits fixed counts,
source-kind/status enums and logical ordinals. No caller identifiers, paths,
hashes or source metadata appear in public summaries/repr/errors.

A node can cover missing mapped leaves beneath auth/env/region[/mcode-public]
or cli-auth/env/region. Each leaf must be proven missing by supplied equal
two-pass directory snapshots on the expected mount; scope, context, root,
batch, round, timestamp and same-packet witness consistency are checked.
Unsafe/ambiguous siblings, duplicates, overlap, changed evidence or a source
present beneath an absent node refuse. Auth cannot conceal cli-auth. Runtime,
configured environment and unmapped MCP kinds cannot be file-absence claims.
Packet-wide reconciliation checks every listed or present path against every
missing prefix and full directory listing, including facts outside the leaves
matched by one node. A missing namespace cannot have an existing descendant
directory witness. Unique supplied directory metadata is bounded below256work
units across both passes; compaction does not remove that independent bound.

Logical leaves and work records stay distinct. A node covering two absent files
counts two logical absences but ONE work unit; a consumer group whose leaves
are all covered does not require a phantom group. Uncovered requirements and
groups still consume work. Logical-source and work limits are exclusive; they
remain enforced separately, including after compaction.

The requirements map is NOT the independently audited native source map or a
complete17-kind root manifest. A caller can provide a smaller conditional map;
that cannot clear ANY physical family. All3image or7container families ALWAYS
remain unresolved, including when every supplied leaf has absence evidence.
The evidence objects are supplied facts, not authenticated filesystem custody.
No observe/scan/complete/start/credential-inventory port exists. Root policy,
host authentication, actual acquisition, source audit and adapters remain future
work; no producer is wired to the collector.

Existing flat accounting now accepts an acquired empty byte string as present
input; its bounded parser rejects the syntax and reports unsupported. Empty
never means absent. No other flat-schema or activation rule is relaxed.

Run `examples/hearth2_coverage_demo.py` with the existing isolated project Python
for four actual synthetic accounting cases: namespace absent (two leaves/one
record), store absent with state present, auth absent with cli-auth projection
present, and a contradictory coverage packet that is refused. These are not
reads of a real Mavis data directory. The results also power the in-conversation
interactive example; it is an explainer of these cases, not the HM dashboard.

Development evidence:24missing-component tests RED, then24GREEN; subsequent
freshness/shared-witness/empty-source regressions RED (2failures+1error across76
credential tests), followed by76GREEN0.174s and97prior parser checks GREEN0.255s.
One fresh final review reproduced an Important packet-consistency finding: a
missing ancestor could conflict with another source or directory outside the
node's selected source IDs. Added four regression methods (six failing cases),
including a reconciliation-work bound;32core tests/80credential tests now pass
(0.166s). The legitimate partial-store and separate projection examples still
work. No Critical/Minor finding or rereview. New immutable full-suite evidence
follows separately; no physical acceptance is claimed.

Final verification:973offline Ubuntu-24.04/Python3.12 tests PASS148.848s, actual exit0; only loopback enabled/external networking disabled. New immutable coverage-core-20261104-source.tar.gz SHA256 `eaaadd3e16a647ee6270f87028c0fca0206db5ff69d9eecc8047b4fd55608f17`; tracked Hearth2 code/test/example bytes match exactly; only docs follow. One Important review finding fixed in one TDD pass; no rereview/deferred minors. The interactive explainer uses actual demo results, with four interactions/saved-state restore/model equality checked by a DOM harness; no real browser-layout or physical OS acceptance is claimed.
