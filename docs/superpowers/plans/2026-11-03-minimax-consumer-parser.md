# MiniMax static consumer parser implementation plan

> **For agentic workers:** Use superpowers:executing-plans inline, test-first, with one final fresh-context review. No implementation delegation.

**Goal:** Classify bounded acquired MiniMax 0.4.1 credential-bearing inputs without running helpers, resolving environment references or claiming inventory completeness.

**Architecture:** A pure stdlib parser accepts explicit byte snapshots. It emits frozen counts only, never source values, names, hashes of secrets, effective credential selection, successful inventory packets or start authority. Physical acquisition, independently audited closure and complete inventory remain separate gates.

**Tech stack:** Python 3.12 stdlib; unittest; existing isolated Ubuntu-24.04 environment.

**Spec:** `docs/hearth2/CREDENTIAL-AUDIT-REQUIREMENTS.md`, `docs/hearth2/ASSEMBLY-COLLECTOR.md`, and `docs/hearth2/MINIMAX-CONSUMER-PARSER.md`.

## Global constraints

- Explicit command workdir and verified RSLABINSKI-PC; preserve ignored continuity.
- Inactive offline code only; no real credential reads, helper execution, provider probes, daemon/worker/service activation or deployment.
- Version and public core bundle SHA must match reviewed 0.4.1. Caller-supplied identity is not installed-source attestation.
- Unknown schemas/consumers remain unresolved. No collector/driver wiring or complete/absence output.
- Native effective account/tool checks remain required before prompt; default 900s/full-run policy inactive.

## Review focus

- Credential text or malicious keys leaking through errors, repr, debug output or output fields.
- JSON duplicate keys, invalid Unicode, nesting and aggregate byte/node exhaustion.
- Native expression escaping and mixed template references, without helper execution.
- Stored auth schema drift or extensions misclassified as supported safe inputs.
- Runtime/environment literal values mistakenly treated as helper or template expressions.

## Task 1: Bounded static input classification

**Files:** new `mcp/memory/hearth2/minimax_consumer.py`, new `test/test_hearth2_minimax_consumer.py`; specification and this plan.

**Interfaces:** Input: explicit bytes plus exact reviewed version/core bundle identity. Output: frozen `ConsumerSyntax` counts for source kind, literal/empty/environment/command fields, environment-reference occurrences and unknown auth records. No values or source-controlled names. This task does not consume scanner or proof packets. Pre-flight: no shared interfaces; only existing RecordError is reused.

- [x] Write refusal/classification/redaction tests first. Run with existing isolated WSL Python. Expected: missing parser feature failures.
- [x] Implement strict bounded JSON decoding and native template syntax classification; schema-unknown auth records increment unknown_records. Header maps classify native expressions; runtime override/environment snapshots are literal maps. Expected: focused tests pass.
- [x] Freeze a new source archive; run full offline suite with loopback only, one fresh final reviewer, TDD fixes only if Important/Critical. Expected: all tests pass; record precise limits and unresolved gates.
- [x] Commit local signed scoped changes, append private ledger and HM search/write/readback checkpoint. No push/merge without new authorization.

Evidence: full821 PASS288.517s/exit0; focused17PASS; one fresh review clean,
17focused+13additional checks PASS. Parser/test bytes match frozen archive
SHA2564b7a1798067fc2ce072cc1eb88a1ef24fe33f4272d410cc29c916577c53b1974.
No fix pass, rereview, activation or successful inventory authority. The private
project ledger and laptop Hearth Memory checkpoint retain the local commit and
readback evidence. Ruling: deliver syntax classification before effective route
and full consumer closure; cost is pending complete credential inventory.
