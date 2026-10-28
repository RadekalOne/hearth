# Piece 1 pre-build verification — 28 October 2026

Disposition: the six source/live questions have answers sufficient to begin
piece 1. This is a pre-build finding, not an implementation or execution-gate PASS.

1. **Schema / way back.** Existing operational work is a separate SQLite file,
   knowledge lives in Chroma. Implement a new versioned Hearth 2 database in the
   approved separate trial memory-service instance. Existing H1 tables stay intact.
   Explicit migration and tested backup restoration are new work.
2. **Export.** Existing `/api/export` is drawer NDJSON only. A consistent,
   versioned operational export/restore with relationship and active-run
   reconciliation is new work, not covered by today's drawer export.
3. **Claims.** Existing work store uses immediate transactions and claim IDs.
   H2 needs an independent generation/epoch on every worker mutation, no reclaim
   merely on expiry, and trusted termination/reconciliation before retry.
4. **Credentials.** Existing principal/reviewer tokens are not task-scoped broker
   grants. Piece 2 must provide read-only, revocable task/attempt/lease grants.
   No general HM/core credential belongs in a worker or export.
5. **Live Cloudroom.** Desktop SSH now succeeds after Rad installed its public
   key on the intended trial host. Cloudroom service is active, pinned version
   `0.1.58 (3949daaea3c7)`, with a loopback-only listener. Authenticated health
   and ready GETs return 200, ready=true. The configured storage policy uses
   cgroup v2; service delegates its subtree and uses control-group termination.
   Worker lacks noninteractive sudo, cannot read the core environment and cannot
   access the Docker socket; no active containers were observed. Both native
   account endpoints report connected. This is not a subscription-only launch
   check or evidence of current allowance. No model prompt was launched.

   Live historical receipt fields: request_id, command, input, model, state,
   workspace. Event envelope adds sequence, session_id, kind, timestamp_ms.
   Usage varies by harness: tokens/contextUsage/lastUsage; Claude also had
   estimated_cost_usd. No actual seat-charge evidence follows from that estimate.
   Exit diagnostics exist separately from request receipts. Source implements
   cgroup.kill followed by populated=0 verification, but that is not an
   independently persisted Hearth containment receipt. Service TasksMax is a
   broad host setting, not a demonstrated per-workload child-process cap.
   Existing two day-one sessions are closed. Catalog now advertises gpt-6.1-sol;
   actual unattended model acceptance has not been tested, so the earlier
   catalog concern is not declared resolved.
6. **Authority.** Existing Gate 1 covers slice build; trial isolation and own
   data/credentials were explicitly chosen; rules v1.0 approved. Rad authorized
   continuing as far as possible on 27 October. No production change, deployment
   executor, extra purchase or Climate Central rollout is included.

Implementation may proceed for the work record. Agent execution, broker,
containment acceptance and the seven-night test remain later independent gates.
Piece 1's 3–4 engineering-day estimate remains a planning range, not a promise
based on elapsed interactive wall time; report actual progress at the review.
