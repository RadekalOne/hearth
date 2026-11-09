# Shared-service receipt pilot preparation plan

Goal: produce a narrow, reviewable shared-service rollout and rollback packet without deploying.
Scope authority: Rad requested preparation for review before deployment. Existing shared/trial activation restrictions remain in force.

- [x] Verify native host/checkout and reference source59ee081; read current public service health and DNS.
- [x] Search durable deployment history and compare reported live762fd5f to reference source.
- [x] Attempt read-only inventory; record Hostinger timeout/cancellation and SSH agent signing/public-key failure without changing credentials.
- [x] Define seventeen-file server subset, hash each source file and patch; check static package import closure and preserve baseline requirements.
- [x] Write staged cutover, per-stage receipt-only acceptance, security-preserving rollback ladder and concrete deployment gates.
- [x] Independent review of this preparation packet: no blocking findings; all17 reference hashes/three baseline hashes and relative-import closure independently verified.
- [x] Retain checked proposal, manifest and continuity; preparation complete, deployment gated by final artifact sheet.

Deployment work below is explicitly NOT executed by this preparation task:
- [ ] Resolve actual host/container/mount/configuration and image inventory through approved read-only access.
- [ ] Create a separate signed release commit; build exact pinned overlay and registry-aware fallback with no dependency upgrade.
- [ ] Run subset-image compatibility/lifecycle and rollback/cutoff rehearsal in staging.
- [ ] Fill final image digests, exact service/backup commands, interruption budget and review receipts.
- [ ] Rad reviews the concrete final artifacts and explicitly approves deployment.
- [ ] Execute only that approved pilot and preserve outcome/rollback evidence.

Rulings: prior whole-branch tests do not validate the proposed subset; pre-guard image fallback is unsafe after session issuance without a separately reviewed recovery; registry and marker are security state independent of ordinary data backup. No shared writes, live credential issuance, restarts, build, purchase, push or merge in this task.
