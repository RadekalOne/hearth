# Durable named-session lifecycle implementation plan

Goal: Preserve credential scope across restart, expiry, revocation and de-enrollment.
Architecture: a separate SQLite credential registry in the existing private data directory stores only SHA256 token fingerprints and immutable session bindings. Configuration enrolls current credentials; removed entries become permanently disabled; explicit human revocation and expiry remain terminal. Historical fingerprints and principal reservations never become general HM authority. New enrollment requires a fresh credential. This registry is security state and must survive H2 restore and disablement.

Constraints: no shared service, native client, credentials or automations changed; understanding unknown and task tables unchanged. Existing enrollment JSON remains compatible; optional expires_at is UTC ISO8601. Runtime checks use server clock. Registry errors fail closed.

- [x] Add failing temporary-registry and actual-app lifecycle tests: restart receipt replay, expiry, revocation authorization, de-enrollment and credential aliases.
- [x] Implement registry, integrate early auth and login, add human-only revoke endpoint and configuration expiry validation.
- [x] Run focused tests and full offline suite, fresh read-only review, fix findings, document limitations and retain continuity.

Review focus: missing/corrupt registry; token rotation/alias collisions; expired configuration cannot extend old credentials; disabled H2 preserves restriction; replay after restart does not duplicate receipt.

Ruling: use existing checkout and native execution under established small-increment authorization. No live enrollment or service activation.

Verification: two registry tests and the fresh-app acceptance pass; 11 updated boundary tests pass. Dashboard/reviewer compatibility checks pass. Final immutable full offline suite: 1,145 tests PASS in 184.561 seconds, actual exit 0, external network disabled and loopback enabled. All 164 tracked Python files match the source snapshot. Source archive SHA256 6d9e247712589a79316f7836d1ded916ef7fb396270b5dc23cf3c142944f11ad.

Independent read-only review found missing-registry restart and transient token-file retirement risks. A persistent required marker and strict policy reads/atomic token writes fix them; token-read failure was reproduced RED before the fix. Policy token-map loading occurs under the registry transaction lock. No re-review claimed. Revocation/receipt fixtures preserve all task tables and understanding unknown. No live service activation or deployment.
