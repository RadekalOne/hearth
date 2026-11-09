# Shared-service receipt pilot: final approval packet

**Execution update, 9 November 2026:** Rad explicitly approved the final packet and recipient amendment; the real shared pilot passed and closed on the disabled fallback. See [execution receipt](SHARED-SERVICE-PILOT-EXECUTION.md). The proposal/preflight text below is historical. Any further activation requires new scope.

**Ready for Rad's review; NOT approved or deployed.** Request one supervised maintenance cutover and a receipt-only pilot for this existing laptop chat. Fixture cutoff/restore gates passed; [rehearsal receipt](SHARED-PILOT-CUTOFF-RESTORE-REHEARSAL.md) and [image validation](SHARED-SERVICE-IMAGE-VALIDATION.md) record their exact limits. Approval must explicitly grant this narrow exception to the isolated-trial activation restriction. This document grants no authority itself.

## Exact artifacts and target

| Item | Pin |
|---|---|
| Host / HTTPS | `vps01hst4hermes`, `2.24.70.124`; `https://hearth-memory.radekal.me` |
| Compose target | Project `hearth-project-hub`, service `hub`, container `hearth-project-hub-hub-1` |
| Configuration | `/docker/hearth-project-hub/compose.json`; pre-change SHA256 `24a2c0a0dcef3d97f58cfac4bbf04d5dd9b77b6d6ed8f8d88e35344fdf18d299` |
| Canonical data | Volume `hearth_memory-data`, `/var/lib/docker/volumes/hearth_memory-data/_data` mounted at `/data`; exactly one writer |
| Current container | `27439b7eac4483638d9ad7adde8a0bc0c475ba72081f423cfaf2838f69f08332`, started `2026-11-08T09:59:58.228502365Z` |
| Current source / image | `762fd5fa0e9cff64179f5ec80d8846c0855e802e`; `sha256:7b667708a22108f125d6e4382b6a70f95814d62afdca8489d74cd09c676a3e7f` |
| Candidate source | Signed `5ce9ffefe09834fef763f22a9883adf97fe5380d`, `codex/shared-receipt-pilot-candidate`; exactly 17 selected source files over the verified baseline |
| Candidate image ID | `sha256:d12b3f802136fdb35e73b5c1492526e0ba0b7b244a877987a949666e1432865c` |
| Disabled fallback image ID | `sha256:26e3d1d4134dc1924fa2c1fbef66ebf1205e1f3e0411a615becf92664f448265` |
| Host helper | `ops/hearth2/receipt_pilot_ops.py`, SHA256 `d61c45be14dcbb0a2ce61a496195e7be6e99098c533f5cef116a87b82479a4cc` |
| Fallback entrypoint | SHA256 `681d54b0ee4d4f389b620f30cfbb364ce5321c5fd6093e44a63781d2852ff61f`; forces H2 false and empty session enrollment before startup |

Images already exist on this host. Use image IDs above with `--pull never --no-build`, not a remote repository digest or development-branch build. No push, merge, dependency/base/model update, new network/route or whole-project restart is included. Full source/runtime hashes remain in `SHARED-SERVICE-ROLLOUT-MANIFEST.json` and image-validation evidence.

## Approved execution would proceed in these stages

1. **Recheck before writes.** Verify host, exact container/image/start/config pins, source/runtime hashes, one canonical writer, stopped legacy `hearth-memory-1`, available disk and both pinned images. Any drift stops execution for reconciliation. Keep existing secret values private. Use only existing SSH key access; no account/security-setting repair is needed. Record approval reference and actual start time privately.
2. **Cold maintenance backup before changing the image.** Proposed maximum preparation outage five minutes; if it cannot finish within that bound, leave pilot disabled and restore the original service/config before enrollment. Stop only `hub`. Verify all Docker writers intersecting canonical data are stopped and no host writer is present. Inventory the complete live data/config (not fixture sizes); helper refuses >512 MiB, >10,000 files, nonregular files or symlinks. If outside those bounds, stop and request a revised backup method. Make a private 0600 archive under new 0700 `/docker/hearth-receipt-pilot-approved/`, record SHA and exact image/config metadata, restore into a fresh absent subdirectory and check every hash and each SQLite integrity. No production data may be overwritten to test restore. The real backup hash cannot exist before this approved stop and is an execution gate, not an unresolved image artifact.
3. **Auth-only foundation.** Preserve all unrelated Compose fields, service/network/volume/ports/Traefik settings and credentials. Set candidate image by ID, `restart: no`, H2 false, empty sessions, build commit `5ce9ffefe09834fef763f22a9883adf97fe5380d` and distinct version `0.10.18-receipt-pilot-5ce9ffe` (replace the existing build/version override so health is honest). Start only `hub`. Require HTTPS health, anonymous protection, existing human sign-in and known-agent REST/MCP success. No pilot credential has yet been issued. If these fail, stop and restore original config/image only after proving no session fingerprint/required marker exists; otherwise use registry-aware fallback/maintenance.
4. **Arm before enrollment/enablement.** Prepare one fixed host plan (template below), finite deadline at most 20 minutes from arming; stage only the dedicated pilot human/controller/worker role names (worker is a logical recipient without a credential or process). Fingerprints cover every fresh A/B/C generation and temporary controller, with disjoint existing principals preserved. Seal the exact config and helper hashes, verify registry-aware candidate/target/mount, start detached guard, verify armed receipt and live PID, and let its launcher exit. Only then merge the fresh pilot token mappings and enable this chat's enrollment. Never extend/rearm this plan on service restart. A missing guard means no enablement.
5. **Supervised shared HTTPS acceptance.** This same native chat `01a194ad-865c-7100-a33a-e220e62cff8d` on `RSLABINSKI-PC`, session `codex-laptop-01a194ad`, principal `codex-session-01a194ad`, recipient `codex`. One explicitly labelled receipt-only carrier task and notice, private durable local inbox, no assignment or inference call. Baseline its task/run/claim/notice/incident/attempt rows after creation and before receipt. Run the matrix below; actual cutoff is mandatory even on success.
6. **Close out on the disabled fallback.** Retire only pilot token entries/temporary aliases; empty pilot enrollment; H2 false. Keep newest registry, required marker, tombstones, original receipt/task and audit. Guard puts the pinned fallback on `restart: unless-stopped`. Prove retired session and controller tokens denied, unrelated user/agent controls healthy, receipt unchanged and no pilot client/controller/guard left. Retire local working credential files. Retain private cold backups/evidence; do not claim historical credential copies in backups were erased.

The temporary controller bearer has existing legacy HM authority because that is the application model; this is disclosed and included in the requested exception. It stays operator-held and is never given to the session client. The session bearer is receipt-only. Proposed temporary controller ID is `supervised-controller`, negative-test alias `codex-pilot-negative-alias`; prove these and the named-session principal are absent from unrelated mappings before issuance, otherwise stop rather than replace an existing identity. Record the alias's C fingerprint in the same retirement plan even while the alias is absent. Resolve the existing authorized human browser principal before activation; do not invent a human account or repurpose its credential. No observer, worker, provider probe, room message, recurring automation, background poller or service activation beyond this exact Memory cutover is included. Inactive 900-second/full-run policy and unrelated jobs/notifiers stay as they are.

## Receipt-only acceptance and stop conditions

| Phase | Required shared-route evidence |
|---|---|
| Active A | Receive exact intended notice; persist body/digest locally before acknowledgement. One durable receipt with original actor/time/sequence/digest; another session cannot receive it. |
| Restart | Actual same-origin Memory container/process restart; one persisted receipt, replay 0/0 and retry returns original acknowledgement. Fixed host cutoff deadline remains unchanged. |
| Real expiry | A works before UTC expiry, fails after server clock passes it; restart/removing expiry config does not reactivate A. |
| Human revocation | Fresh B succeeds first, existing authorized human revokes it, B remains denied across restart. Controller/session cannot grant recovery/revocation authority. |
| De-enrollment | Fresh C succeeds first; remove enrollment and only its pilot mapping. A temporary fresh general alias and disabled H2 cannot broaden C's access; remove alias immediately. Restoring former enrollment cannot revive it. |
| Negative surface | For active and each inactive generation: generic status/recent/work/export, H2 mutation, MCP GET/initialize/tools-list/call/batch, cookie/login/mixed-header and alias conversions denied. Intended active receive/ack succeeds; inactive receive/ack fails. Capture method/path/status and no-store. |
| Controls and meaning | Ordinary known-agent REST/MCP and human session remain healthy at every phase. Original receipt exactly one, understanding **unknown**, task state unchanged; no inference of reading, comprehension or completion. Compare project-scoped rows, allowing legitimate unrelated HM writes. |
| Cutoff / backout | Actual detached cutoff or explicit early cutoff retires pilot mappings, switches disabled fallback, preserves security/receipt/user controls. Collect actual timing; rehearsal's 3.3–3.5 second lag is observed, not a guarantee. |

Stop immediately on any broader 2xx, inactive credential accepted, missing/corrupt security state, duplicate/changed receipt, invented meaning/completion, task mutation, unrelated auth regression or unavailable cutoff. Use early cutoff while the plan remains valid. Config/token/plan drift invokes scoped restart=no and stop, with maintenance recorded. It may interrupt shared HM availability; **that fail-closed availability tradeoff is part of the approval request**. Do not guess-delete an unknown mapping or continue experimentation against shared users.

## Sealed plan and bounded commands

`SHARED-SERVICE-PILOT-PLAN.template.json` is intentionally `awaiting-approval`, with no secrets, fingerprints, deadline or approval reference; the helper rejects it. After approval, copy the verified helper into the private root, create a new 0600 runtime plan from it and fill those runtime fields. Hash the staged approved config with `immutable_config(config, 'hub')` after deliberate role/build overrides; image/restart/H2-enabled/enrollment are the only fields excluded by that hash. Every other field stays pinned. Retain both pre-change config SHA and the reviewed narrow config diff privately. Include all planned credential generations in `retire`; compare unrelated token entries before/after, never clear the map wholesale.

The following are execution-time command forms, **not commands run during preparation**. `PLAN_SHA` and `BACKUP_SHA` must be read from the actual private sealed plan/backup receipts, not copied from fixture evidence. Foundation backup uses a separate approved plan with no pilot retirement entries; final cutoff uses the later sealed pilot plan. The CLI's backup/restore commands do not stop writers themselves.

```sh
docker compose -p hearth-project-hub -f /docker/hearth-project-hub/compose.json stop -t 10 hub
python3 /docker/hearth-receipt-pilot-approved/receipt_pilot_ops.py backup --plan /docker/hearth-receipt-pilot-approved/backup-plan.json --plan-sha256 "$PLAN_SHA" --archive /docker/hearth-receipt-pilot-approved/pre-pilot.tar
python3 /docker/hearth-receipt-pilot-approved/receipt_pilot_ops.py restore --plan /docker/hearth-receipt-pilot-approved/backup-plan.json --plan-sha256 "$PLAN_SHA" --archive /docker/hearth-receipt-pilot-approved/pre-pilot.tar --archive-sha256 "$BACKUP_SHA" --destination /docker/hearth-receipt-pilot-approved/restore-check
docker compose -p hearth-project-hub -f /docker/hearth-project-hub/compose.json up -d --no-deps --no-build --pull never hub
# After pilot plan is sealed: detached, finite guard; verify armed receipt/PID before enablement.
nohup python3 /docker/hearth-receipt-pilot-approved/receipt_pilot_ops.py guard --plan /docker/hearth-receipt-pilot-approved/pilot-plan.json --plan-sha256 "$PLAN_SHA" </dev/null >/docker/hearth-receipt-pilot-approved/guard.log 2>&1 &
# Early cutoff if needed; same immutable plan/hash and original deadline.
python3 /docker/hearth-receipt-pilot-approved/receipt_pilot_ops.py cutoff --plan /docker/hearth-receipt-pilot-approved/pilot-plan.json --plan-sha256 "$PLAN_SHA"
```

No `down -v`, prune, whole-volume rewind or legacy-container restart. Do not delete session registry/marker to get the old image working. After any session credential is issued, old `762fd5f` is not routine fallback. If the fallback/auth guard itself cannot safely serve current security state, keep Memory in maintenance and forward-fix under a separate recovery decision. Restore into a fresh private destination only; never overwrite newer legitimate HM writes or roll back revocations. Rehearsed restore is receipt-only, not native-worker disaster recovery.

Guard is a finite host process, not a reboot-surviving service. Host reboot or dead Docker daemon requires explicit operator recovery; candidate restart=no prevents automatic enabled restart. No availability or hard cutoff guarantee is claimed under host failure. If the supervised acceptance cannot fit the fixed 20-minute window, stop and report partial results; a second pilot needs fresh approval.

## Approval requested

Approve exactly the artifacts above, one supervised maintenance cutover (preparation outage budget five minutes), one at-most-20-minute receipt-only pilot in this chat, and permanent closeout on the registry-aware disabled fallback. Include the cold live backup/isolated restore gate and fail-closed maintenance tradeoff. This authorizes neither general v2 rollout nor ongoing polling/worker services. Until Rad approves, production remains unchanged. Claude's earlier component review is not an exact-release approval of these artifacts; none has been claimed or requested by sending a message elsewhere.
