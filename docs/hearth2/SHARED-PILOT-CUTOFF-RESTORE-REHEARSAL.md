# Shared-pilot cutoff and cold restore rehearsal

9 November 2026. **Fixture rehearsal passed; production deployment is unapproved.** The final decision is in [SHARED-SERVICE-FINAL-APPROVAL.md](SHARED-SERVICE-FINAL-APPROVAL.md).

The host helper is `ops/hearth2/receipt_pilot_ops.py`, SHA256 `d61c45be14dcbb0a2ce61a496195e7be6e99098c533f5cef116a87b82479a4cc`. It is a separate operator artifact; neither validated service image changed. Eight operator regression tests passed in 0.066 seconds on WSL Python 3.12. The earlier image validation remains 409 selected tests, plus actual TLS lifecycle and fallback restart checks; these counts are separate.

## Isolation and observed results

Rehearsal host `vps01hst4hermes` (`2.24.70.124`), private root `/docker/hearth-receipt-rehearsal-20261109-cutoff`. Only prior synthetic data was cloned. Containers used network none, no published ports, Traefik disabled, read-only roots and bounded resources. No canonical volume, production secrets or Docker socket was mounted. Fresh fixture tokens stayed private.

| Check | Observed evidence |
|---|---|
| Detached cutoff | Sealed plan `3562e53b449c3969a073cbc0439375565dc419ceba9e9fa738a58c9c7dca2833`; launcher returned; fixed deadline `17:28:20.887256Z`; trigger `17:28:20.912544Z`; fallback ready `17:28:24.193101Z`, 3.306 seconds after deadline. |
| Actual fallback | Candidate `1c2249db6dba…` became fallback `7cfbc859f3d1…`; exact pinned fallback image; H2 disabled, ordinary REST/MCP 200, retired pilot delivery 403. Only the two fixture pilot entries were retired; ordinary token/config preserved. |
| Restart across deadline | Separate fresh 35-second plan `a3d8f11ad6a2c1ab9dc1e29471323bd40b7623bac09966b25c4224493876aedf`; launcher exited `17:33:04.914930Z`; same candidate ID `56e9bf95e92d…` restarted from `17:33:00.187776722Z` to `17:33:05.693378812Z`; active delivery and controls verified at `17:33:10.064877Z` with 29.782 seconds remaining. Original deadline `17:33:39.846867Z` unchanged; fallback ready `17:33:43.360519Z` (3.514 seconds after deadline). |
| Guard fault | After arming, replace the pilot credential and prove the changed generation active. At deadline, fingerprint mismatch caused nonzero guard exit and scoped candidate stop, maintenance true; unrelated token retained. No guessed credential deletion. |
| Cold backup | Writer stopped; no intersecting running Docker writer. Full data and archived private Compose configuration, 18 regular files each. All file hashes checked. SQLite integrity ok for Chroma, H2 and session registry. |
| Restore | Latest archive restored into absent destination; every restored file hash exact. Boot used the **archived** configuration, changing only fixture identity/mount/restart. Legacy drawer/checkpoint/relay sentinels survived; ordinary REST/MCP 200 and retired session 403. |
| Refusal | Bad overall checksum, existing destination, stale security snapshot refused remotely; traversal, duplicate/symlink members and stale-success idempotence covered by regression tests. |
| Receipt semantics | Before cutoff, after cutoff, after restart and after restore: one original receipt, original digest/time/sequence, local inbox one record, understanding unknown, carrier task running and task/run/claim/notice/incident/attempt values unchanged. |

Private archive hashes: `before-cutoff.tar` = `32fb111064d651daab0c398b7e415f67ab002b36332cbd835c2ce9c791c371ce`; `after-cutoff.tar` = `c3d8464e533f459d8dbff71f6ccd7320bd11bceeba2ab025c190c107d25894a5`. Both archive modes 0600, private root 0700. Archives retain historical **fixture** auth material and remain private; they were not uploaded to chat/HM or committed.

The first fixture setup stopped on a probe import error before arming; adding `/app` to the probe import path fixed the harness. No service/image source changed. The first finish receipt's restart boolean alone did not establish restart timing; Docker history did not provide the missing timestamps. The separate restart trial above supplies direct before/after container start timestamps and active-before-deadline evidence. The original plan was not extended or rearmed.

## Review and limits

One fresh independent read-only operator review found guard drift could exit without stopping the candidate, restore boot could use current instead of archived config, and idempotence could report stale success. The author corrected all three before rehearsal, added failing-then-passing regression coverage and exercised actual credential drift remotely. No second independent review or Claude approval is claimed.

The guard retains a validated scope in memory. Later plan/config/fingerprint failures attempt restart=no and stop of that exact scoped container, recording maintenance. The successful path replaces it with the registry-aware disabled fallback. Repeated cutoff verifies current disabled state before returning its prior receipt. Candidate restart=no prevents automatic enabled-pilot resumption after host failure; fallback uses unless-stopped.

This is not a host-reboot/Docker-daemon-failure or persistent supervisor proof. An unresponsive Docker daemon can prevent an immediate stop; host/operator recovery is required. No new recurring job was installed. The helper bounds backups to 512 MiB / 10,000 regular files; larger live data requires a separately reviewed method. Restore refuses stale registry/token/reviewer security, and does not solve general native-worker epoch recovery or safely merge newer HM writes.

Cleanup removed all owned fixture containers, emptied working token maps (including restored/fault/restart copies), removed probe credentials and ended finite guards. Private scripts, public receipts and archives remain as evidence. There are no enabled pilot sessions or ongoing fixture services.

Production identity, image, start time and Compose SHA matched the pre-run snapshot; HTTPS health remained Memory/homeserver ok on `762fd5fa0e9cff64179f5ec80d8846c0855e802e`. These are narrow verified deployment properties. Legitimate HM writes continued; no frozen-data claim is made. Production backup/restore and shared-route pilot acceptance remain execution-time gates after Rad's approval.
