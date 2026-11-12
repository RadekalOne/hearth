# Claude A–C review response — 12 November 2026

Piece2, inactive native turn components. Source reviews:
`drawer_18f1e5159f8e597090b90cd1f1754654` (desktop source PASS) and
`drawer_2d66799fe9dddde78923626460c0bb47` (Cowork Linux test evidence).
Their PASS is limited to inactive components. All A–E findings remain relevant
before a paid turn; this response addresses A/C and part of B only. Neither
surface observed the trial runs or verified the commit signature.

| Finding | Candidate disposition | Remaining verification |
| --- | --- | --- |
| A: expensive fence on every event | Local monotonic deadline and byte/event limits still checked every event; heavy live fence rate-limited to250ms during event flow. Forced checks at dispatch, after durable intent, after ACK, and before returning/after terminal audit. | Claude review of exact changed source; synthetic stress does not prove live provider timing. |
| B: unjustified45s live limit | Removed implicit turn timeout. Unconfigured turn refuses before wire; existing45s ceiling unchanged. Fixture selects45s explicitly. Paid packet no longer treats45s/90s as live policy. | OPEN: deliberate reviewed live timing policy and any real timing evidence, under existing approval/financial gates. No replacement guess or automatic longer timeout. |
| C: missing cause/send evidence | Fixed cause class, stage, RPC/session IDs, observed pipe-byte count, conservative send state, complete-write indicator and native response hash; same sanitized evidence available on raised error if audit fails. | Exact-source independent review; provider receipt/billing is still unknown from pipe writes. |
| D: denied read correlation | OPEN/unchanged | Proper JSON-RPC denial and pinned native-client reaction. |
| E: per-grant read budget | OPEN/unchanged | Enforced total read budget before real HM upstream. |

During continuous event flow, a live check is due on the first processed event
at or after250ms since the previous check completed; trusted callback duration
and inter-event gaps add latency. This is not a hard250ms revocation SLA.
Cadence is not an independent idle watchdog. On an idle pipe the read deadline
still applies; root cutoff/containment remain caller duties. Broker reads always
check the live grant before and after each read, without cached authority.
Callbacks remain trusted and must themselves be bounded. No shipped lifecycle
composition is claimed. Private `_exchange` guard prevents accidental API misuse;
in-process Python/private attributes cannot isolate hostile host-root code.
Other F notes (BaseException handling, bounded stop callback, repeated thread
start) are not closed by this increment.

Before transport writes, a durable dispatch intent records the SHA256 of the
canonical request params, RPC/session/thread correlation, explicit timeout and
a conservative possibly_sent_unconfirmed marker. A crash with only that marker
means possibly sent, never a no-spend or safe-retry conclusion. Later failure
evidence can refine known no-attempt/full-write/response state.

Failure evidence uses only fixed internal cause labels, never raw provider,
prompt or exception messages. Send states: not_sent; send_attempted_outcome_unknown;
partial_write_outcome_unknown; request_written_outcome_unknown; response_received.
`request_written` is false only before attempts, true after the full pipe frame,
null for attempted/partial writes. Bytes accepted by a local pipe do not prove
provider receipt or cost. A native error preserves only its response SHA256,
not raw text. Uncertain output still requires external stop/empty evidence and
financial reconciliation; there is no automatic retry or substitution.

Tests first reproduced the failure:17turn tests with1failure/4errors. Initial
55focused tests then passed. Controls cover5,000-event burst, deterministic
cadence/revocation and forced checks, unset timeout, invalid request before wire,
written/no ACK, provider error hash and actual7-byte partial pipe write failure.
A credential-free pinned0.159.1 stress pair on the trial VPS uses synthetic
provider/upstream and4,096 whitespace padding characters as one-character SSE
deltas. It measures actual SQLite-grant/Docker-inspect fence work, not provider
latency. Run IDs, final metrics, source hashes and full-suite evidence are in
`evidence/turn-review-abc-2026-11-12.json`.

Production, activation, paid/account turns, credentials and billing are unchanged.
The paid packet remains prepare-only; fresh seat evidence and Rad [APPROVED]
remain required after remaining implementation/review gates. Frozen inventory
work, supervisor and morning report were not started.

One fresh-context whole-increment source review found two Important/no Critical
issues: specific pre-ACK causes were lost in generic RPC error wrapping, and
audit-failure exception evidence omitted session/thread/turn correlation. Both
were reproduced (RED1failure/1error) and fixed in one pass. An additional RED
control showed malformed native turn IDs leaked into failure rows; IDs are now
validated before assignment.82 focused tests pass after these fixes. No second
review or new Claude PASS is claimed. Full and native final evidence is linked.

Final full repository suite:1,230 tests PASS121.010s, exit0, network disabled.
Final pinned native stress pair:
`/root/hearth-runner-trial/walking-44013c9a321c481da1442ca1f3385c13`:
positive `run_50f62e13ca8243ad994bcf4289dbe85f` enters review; missing-closeout
`run_b50c4b885fed41d19a5fcc199200f284` returns ready with one incident. Both
exit0, root observer confirms empty, containers removed, bearer absent and
understanding unknown/human acceptance false. These are synthetic task records,
not changes to live tasks. Earlier stress pair measured4,480events/7heavychecks/
0.825seconds; final metrics and exact source pins are retained in the evidence.
