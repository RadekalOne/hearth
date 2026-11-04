# Credential source accounting implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: use superpowers:executing-plans, implement inline with TDD. One fresh final review, no implementation delegation or rereview.

**Goal:** Account for required credential sources without promoting syntax or acquisition assertions into complete inventory.
**Architecture:** Immutable synthetic manifest and observation types feed a bounded pure diagnostic adapter. Reuse pinned parsers; preserve unresolved coverage in every result. No filesystem/provider/backend wiring.
**Tech Stack:** Python3.12 stdlib and existing PyYAML6.0.3.
**Spec:** docs/superpowers/specs/2026-11-04-credential-source-inventory-design.md (approved by Rad4Nov).

## Global Constraints

Actual RSLABINSKI-PC; explicit C:\Users\rslabinski\Projects\hearth2-transfer, existing feature checkout as approved. No credentials/ambient environment/native clients/providers/global/account/service changes, push or merge. Synthetic fixtures only; all physical families unresolved; no observe/complete/absence/start authority. No new dependency. Keep private continuity; automation paused/900s inactive.

## Review Focus

- Related-role substitution across namespaces or missing partners: preserve unknown, never cross-pair.
- Caller metadata or parser exceptions in output/repr: only fixed enums/counts, no input strings.
- Disabled/expired/unsupported input retaining material: never erase known counts or unknowns.
- Mutable/subclass/malformed packet or policy values: refuse fixed redacted error.
- Budget/freshness edges or shortened source map: refuse or remain unresolved, never truncate to clean.

## Task 1: Immutable source accounting and parser adapters

**Files:** create mcp/memory/hearth2/credential_sources.py and test/test_hearth2_credential_sources.py; update approved spec with API/verification evidence.
**Interfaces:** consume CredentialAuditRequirements.require_scope and pinned MiniMax parsers. Produce SourceContext, SourceRequirement, OAuthSourceGroup, SelectionSourceGroup, SourceManifest, SourceObservation (frozen/private repr) and SourceAccountingSummary (fixed counts/enums), CredentialSourceAccounting(clock,monotonic).account(manifest,observations,begin=aware_datetime). Required kinds constant SOURCE_KINDS, no caller parser/summary injection.
Implementation caps:256 sources,1MiB aggregate bytes,65536bytes per source,64 groups,60s freshness; lower policy limits apply, reaching work limits refuses. Every initial catalog kind required at least once; family requirements from policy always unresolved. Absent needs explicit metadata; omitted observation unscanned. Present unsupported raw input is unknown; nonpresent bytes refused. Tuple inputs only, fixed enums, exact types, no output caller strings. OAuth pair by explicit group/role; projection primary_group_id must equal same namespace group. Host ModelRef paired only same config group; absent/unknown counterpart cannot become {} fallback. Config contexts conditional only. No collector success schema.

- [x] Write direct regressions for bound context, missing/absent/unreadable/unsupported, duplicates, freshness, exact budgets, output redaction, mutability and all-family unresolved behavior. Run new module tests; Expected RED missing module.
- [x] Implement immutable bounded core and pinned parser adapters; run focused tests. Expected all GREEN. Extend tests first for adapter-specific gaps.
- [x] Run97 existing parser tests plus new tests; Expected all GREEN. Record ledger preflight: single task, no shared task interfaces; parser summaries consumed only internally, no collector interface changes.
- [x] Stage scoped files; create unique immutable tracked-source snapshot. Dispatch one fresh reviewer against0e9856d+scoped diff/spec/plan, grade findings, fix important ones RED→GREEN once. Run final immutable full offline suite (only loopback) and compare code/test bytes. Expected exit0; actual count recorded, never infer acceptance.
- [x] Mark checklist, append verification/rulings, create signed local commit and HM outcome/checkpoint search/write/readback. Expected clean scoped checkout/unpushed; no activation.
