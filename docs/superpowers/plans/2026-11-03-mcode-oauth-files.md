# MCode OAuth file parser implementation plan

> **For agentic workers:** Use superpowers:executing-plans inline, TDD and one fresh final review; no implementation delegation.

**Goal:** Safely classify published OAuth store/state and cached token projection snapshots with fake-token fixtures.

**Architecture:** New pure module `mcode_oauth.py` reuses bounded JSON decoding, with an exact expected OAuth NUL record-key exception. Validate independently declared namespace and supported schemas; return fixed labels/counts and token-equality only. No acquisition/authentication/inventory/activation authority.

**Tech stack:** Python stdlib/unittest, existing Ubuntu-24.04 isolated verification environment.

**Spec:** `docs/hearth2/MCODE-OAUTH-PARSER.md`, existing credential requirements and source map. Exact AAJMOWWM Z/me/de/Fe/J/k and 6BYKHQOV xi/oc/ac public source retained privately in oauth-schema-source-20261103.json.

## Global constraints

RSLABINSKI-PC/explicit workdir. Offline synthetic credentials only. No ambient credential files, client/helper/provider/daemon/worker/service/global/account changes. No push/merge. Existing900s/full-run and runtime remain inactive. Preserve history/private continuity. Hash/identity matching is not physical attestation or complete inventory.

## Review focus

- OAuth NUL record-key exception broadening unrelated JSON callers.
- Hidden credentials/unknown fields/foreign records silently skipped or reported absent.
- Token or identity leakage through exceptions/results/repr/decoder contexts.
- Generation/namespace/expiry mismatch or stale projection equality promoted to usable login.
- Bool/float/unsafe integer, missing source and transient authorization material handling.

## Task 1: Published OAuth snapshots

**Files:** new mcp/memory/hearth2/mcode_oauth.py, new test/test_hearth2_mcode_oauth.py; narrow private decoder change minimax_consumer.py, spec and plan.

**Interfaces:** decoder->OAuth schema accepts only an explicit expected control key; default Pi/MCode header callers retain strict key rules. Store+state->summary matches exact original namespace/generation/expiry. Projection->comparison preserves token presence even when expired/mismatched; no usable/complete authority. Pre-flight ruling: native record keys contain NUL and cannot pass current decoder; add exact per-call allowed key tuple rather than broad control-key acceptance. Cost: strict subset refuses foreign/extra records, requiring later source coverage work.

- [x] Write schema/refusal/redaction/mismatch tests; observe missing-feature RED.
- [x] Implement pure parsers and narrow decoder exception; focused tests GREEN.
- [x] Freeze NEW immutable source, full loopback-only offline suite and one fresh review; TDD fix pass only if Important/Critical findings.
- [x] Signed local commit, progress ledger and HM search/write/readback checkpoint. No publication or activation.

Evidence: initial19RED; onefreshreview42focused+33additionalchecks; oneImportant
JS/Python whitespace mismatch fixed by3regressionmethodsRED->GREEN. Final22OAuth
plus23existing focusedPASS; full849PASS144.990s ACTUALexit0, no rereview. Final
source44f8dbe012661adae219536e36ebce741960992d8d47c36ef65d41e2c17e590d,
code/testbyteEXACT, docs-onlyafter. Pre-fix846 result retained only historically.
Rulings: exact NUL namespace-key exception does not broaden other decoder calls;
strict legacy/extra-schema refusals cost future support; parser declarations and
equality never physical custody/complete inventory/native login authority, costing
separate acquisition/config/effective-resolution/OS acceptance work.
