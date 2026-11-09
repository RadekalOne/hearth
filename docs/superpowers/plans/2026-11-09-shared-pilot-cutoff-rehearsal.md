# Shared pilot cutoff and cold restore rehearsal

Authority: rehearse on isolated fixtures and prepare the final packet; production stays unchanged.

Architecture: sealed host plan identifies one Compose service/data mount and pinned candidate/fallback images. A detached finite cutoff uses a fixed monotonic/UTC deadline, disables H2 on the fallback, and retires only fingerprint-matched pilot token entries after the fixture writer stops. Pilot restart policy is no until backout; fallback restores unless-stopped. Cold backup archives the full quiescent fixture plus private configuration; restore is into an absent isolated destination and refuses checksum/path/current-security mismatches.

- [x] Write failing unit checks for config scoping, token preservation, backup corruption/traversal/destination refusal and stale security.
- [x] Implement bounded cutoff/backup/restore helper and verify guards.
- [x] Independent read-only review before remote rehearsal; fix findings.
- [x] In fixture-only Compose: seed synthetic legacy stores, verify receipt/ordinary token, cold backup, arm detached cutoff, exit launcher, restart candidate without extending deadline, prove actual fallback/credential retirement.
- [x] Cold backup post-cutoff; refuse stale-security restore; restore latest into a fresh isolated service and verify integrity, legacy sentinels, receipt1/unknown understanding/unchanged task and denied retired token.
- [x] Remove fixture services/guards, retire credentials, prove production identity/config/start/health unchanged.
- [x] Final approval packet with exact images, reviewed operator artifacts, phase/abort/rollback instructions and explicit approval scope. Live cold backup remains an execution-time prerequisite, not a rehearsal claim.

No source service change, canonical-volume mount/copy, production credentials, Docker socket in fixture, DNS/proxy edits, provider/worker activation, recurring job, push/merge/deploy. Preserve inactive900s/full-run and unrelated jobs.

Completed fixture evidence and decision: `docs/hearth2/SHARED-PILOT-CUTOFF-RESTORE-REHEARSAL.md`, `SHARED-PILOT-REHEARSAL-EVIDENCE.json`, `SHARED-SERVICE-FINAL-APPROVAL.md`. Eight ops tests pass; images unchanged. Live backup and shared acceptance are future approved-execution gates. No deployment authority granted.
