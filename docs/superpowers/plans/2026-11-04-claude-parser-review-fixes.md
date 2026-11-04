# Claude parser review follow-up

> **For agentic workers:** Use receiving-code-review and TDD; implement inline. Claude's requested independent review is the fresh review for this fix run. Verify one fix pass with regression tests and the full offline suite; no rereview or implementation delegation.

**Goal:** Address confirmed coverage/labeling gaps from Claude's read-only review of baseline5eaf9a9 while preserving unresolved-source and activation boundaries.

**Architecture:** Extend count-only Pi/OAuth summaries, attach conditional results to non-secret hypotheses, represent unparsed config/ModelRef branches as unresolved, and document every known acquisition gap. No actual source reads, token values, native login or runtime/start proof.

**Spec:** docs/hearth2/CLAUDE-PARSER-REVIEW-2026-11-04.md and the existing three parser specs. Full original review retained privately from attachment2caba3c8/Pasted text.txt. Same reviewed MCode0.4.1 public bundles.

## Global constraints

RSLABINSKI-PC/explicit laptop checkout; synthetic data only. Preserve history and private continuity. No live credentials, client/helper/provider/worker/service/global/account changes, publication or merge. Root lifecycle/900s/full-run remain inactive. Unknown/unparsed counters must force unresolved output, never effective selection, no-route or credential absence.

## Task 1: Confirmed review corrections

Interfaces: known Pi OAuth fields contribute counts even if record remains unknown; OAuth generation remains a refusal fence while expiry/scope differences are metadata. Config unknown branches force unresolved labels, catalog declarations match native alias, numeric identifiers use JS Object.keys ordering, and results carry resolver plus context-only fingerprint. No fingerprint includes config bytes, tokens, ModelRef values or free-text reference. Pre-flight: all changes remain outside inventory/driver interfaces; no unknown counter may be silently dropped on a result path.

- [x] Write regressions for A1/B1/B2/D1/D2/E1/F1/F2/F3, including unresolved counters, native numeric-key order and reference-independent fingerprints. Observe RED.
- [x] Implement verified changes and update existing intentional-refusal assertions; focused tests GREEN.
- [x] Publish the known-artifact/disposition tables. Keep YAML/unknown-field refusal semantics explicitly distinct from native abort/absence; document intentional unsupported formats.
- [x] Freeze new source, full offline suite; signed local commit and HM/progress search/write/readback. No new provider or native probes.
