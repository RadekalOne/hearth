# MCode conditional configuration analysis implementation plan

> **For agentic workers:** Use superpowers:executing-plans inline with TDD and one fresh final review; no implementation delegation.

**Goal:** Parse bounded supported configuration YAML and derive conditional resolver-specific selection facts without guessing runtime context.

**Architecture:** Pure new mcode_config.py consumes explicit source bytes and frozen SelectionHypothesis. Pinned PyYAML event parsing provides syntax only; strict fields/scalars/limits bound unsupported semantics. Return fixed route/source/error labels, credential/header counts and HTTP ambiguity flags. No effective/start authority.

**Tech stack:** Python stdlib + already available PyYAML6.0.3; unittest; existing isolated Ubuntu-24.04 verification environment. Explicit project requirement pin, no global installs.

**Spec:** docs/hearth2/MCODE-CONFIG-ANALYSIS.md, credential-audit requirements, Claude's private mcode-0.4.1-selection-test-cases-claude.md (37 labeled cases, SHAa4b10a18744d65ab9bd24c87946e45a985b4bc1e7da3b6aa0b048ebe3278f6a4).

## Global constraints

RSLABINSKI-PC, explicit laptop checkout workdir, preserve history/private state.
Offline synthetic bytes only; no live credential/client/helper/provider/daemon/
worker/service/global/account changes. No push/merge. 900s/full-run inactive.
Declared hypotheses and hashes are not physical attestation; unresolved context,
HTTP auth and source coverage cannot be promoted into inventory/start authority.

## Review focus

- YAML implicit typing differences, aliases/tags/duplicates and resource limits.
- Raw secrets disappearing from counts through rewrites, unused or disabled paths.
- OD fallback vs MI error and pre-resolver source-gating differences.
- Header merge/case collisions, user key plus bearer and ModelRef credentials.
- Conditional labels/hypotheses mistaken for physical effective-auth proof.

## Task 1: Bounded config facts and conditional selection

**Files:** new mcode_config.py/test_hearth2_mcode_config.py, spec/plan and explicit PyYAML requirement.

**Interfaces:** YAML event decoder->strict schema must never use SafeLoader1.1 implicit booleans or constructors; raw statistics->normalizer must retain all stored fields before dropping/replacing. Hypothesis->OD/MI branch is mandatory, never inferred. Context models supply order/catalog membership; no hardcoded current model list. Output is source analysis only. Pre-flight ruling: production-only supported context and strict unknown-field refusal bound native ambiguities; cost future compatibility/closure work, not a guessed effective route.

- [x] Add source-derived schema/refusal/conditional-selection tests; observe RED.
- [x] Implement bounded YAML/scalars, strict schema, raw counts and explicit-context transformations/selection; focused GREEN.
- [x] Freeze new immutable source, full offline suite and one fresh final review; one TDD fix pass for Important/Critical findings if needed.
- [x] Signed local commit, progress ledger and HM search/write/readback checkpoint; no publication/activation.

Evidence: initial26RED; onefreshreview5Important/nocriticalorminor,36finalfocused
PASS after6regressionmethodsRED21failures+1error->GREEN. Final885fullPASS144.222s
ACTUALexit0; source77d16407f100c994d1aed097416e675760afbdb517aca693ecb548a1da681701.
All3publicsourcepins independentlyhashed/matched; code/requirements/testbyteEXACT,
docsonlyafter, no rereview. Pre-fix879 result retained historically only.
Rulings: strict subset costs compatibility; conditional declarations never physical
context/start authority, costing independent enrollment/acquisition; native file
migration eligibility refuses (including unused entries), costing later migration
receipt/closure work; unsupported URL/type/test-build behavior refuses; HTTP/account
and OS/native/provider acceptance remain separate. No deferred minors.
