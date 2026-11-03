# MiniMax route distinction correction plan

> **For agentic workers:** Use superpowers:executing-plans inline with TDD and one fresh final review; no implementation delegation.

**Goal:** Make the supported Pi syntax and literal MCode header semantics explicit at the parser API boundary.

**Architecture:** Rename ambiguous Pi parser methods and result source kinds. Add a separate literal MCode header map parser requiring the reviewed MCode resolver bundle identity. Keep counts-only output, unresolved schemas and no acquisition/inventory/start authority.

**Tech stack:** Existing Python stdlib parser/unittest and isolated WSL Ubuntu-24.04 environment.

**Spec:** `docs/hearth2/MINIMAX-CONSUMER-PARSER.md`, Claude's 3 November source map in HM drawer_35c9d39c5611135a5ea498e0db2eb9e5, independently checked public bundle anchors in private `claude-routes-verification-20261103.json`. Prior primitive remains source syntax, not complete MCode consumer coverage.

## Global constraints

Explicit laptop workdir/host, offline only, no credential reads/helper/client/provider/daemon/service activation; default 900s/full-run policy inactive. Preserve existing commit/history and private continuity. No push/merge. Snapshot provenance and audited complete inventory remain separate gates.

## Review focus

- Any remaining ambiguous entrypoint applying Pi template rules to literal MCode values.
- Generic core bundle identity being promoted into MCode resolver attestation.
- Unknown OAuth/config/token projection routes mistakenly counted as covered.
- Incorrect global reachability/absence claims from static excerpts alone.
- Regressions in existing bounded decoding, redaction or no-execution behavior.

## Task 1: Explicit source layers

**Files:** `minimax_consumer.py`, its tests, parser specification and this plan.

**Interfaces:** Existing parser methods have no callers outside tests/docs (verified rg). Rename them to pi_auth_json/pi_headers_json/pi_runtime_overrides_json; remove old ambiguous names rather than silently reinterpret. New mcode_headers_json requires resolver_bundle_sha256 matching reviewed OFHDMZSQ. Pre-flight: source grammar supplies counts to the same summary helper; MCode must use expressions=False, Pi uses existing expressions=True. No inventory interface is implemented.

- [x] Write regression tests for distinct Pi/MCode behavior and source identity; run and observe missing-feature failures.
- [x] Rename methods/source kinds, add literal MCode method with exact source identity, and correct scope docs. Run focused tests; expected all pass.
- [x] New immutable full offline suite and one fresh final review. Fix Important/Critical findings with TDD if any. Expected all tests pass, no widened authority.
- [x] Signed local commit, progress ledger and HM outcome/checkpoint with exact readback; no publication/activation.

Evidence: four regressions RED, 23focusedPASS0.020s; full827PASS206.671s/exit0,
immutable81dc0b0355984f63555d8ea97f08291c3b22d675fa03c4a928c29fb84dcc5874.
One fresh review clean/23focused+20additionalsyntheticPASS/nofixpass/norereview.
Rulings: remove ambiguous prototype aliases (no live callers; cost local API name
change); keep global keychain/extension absence attributed rather than claim full
closure (cost further audit); leave full source/effective-route/physicalOS/native
acceptance unimplemented (cost subsequent source-backend and acceptance work).
