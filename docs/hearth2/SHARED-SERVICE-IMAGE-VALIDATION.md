# Shared-service inventory and image validation — 9 November 2026

Status: **requested inventory and candidate/fallback validation passed; deployment remains gated on Rad's approval.** Only isolated validation resources were created on the existing VPS. The running shared Memory service was not stopped, recreated or reconfigured.

## SSH blocker resolved without credential changes

The default SSH-agent signing path failed. An explicit command-scoped existing identity succeeded:
`ssh -o IdentityAgent=none -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes -i ~/.ssh/hermes-key root@2.24.70.124 ...`.
The hostname read returned `vps01hst4hermes`. No key was copied to the server, added, rotated or exposed; no agent/service/account/global SSH configuration or trust setting changed. This resolves this task's SSH access, not every application's agent path.

## Verified live target

- Container `hearth-project-hub-hub-1`, ID `27439b7eac4483638d9ad7adde8a0bc0c475ba72081f423cfaf2838f69f08332`.
- Compose project/service `hearth-project-hub / hub`, file `/docker/hearth-project-hub/compose.json`.
- Compose SHA256 `24a2c0a0dcef3d97f58cfac4bbf04d5dd9b77b6d6ed8f8d88e35344fdf18d299`; private environment values were never printed.
- Canonical volume `hearth_memory-data`, actual host path `/var/lib/docker/volumes/hearth_memory-data/_data`, mounted at `/data`. Exactly one running writer; legacy Memory container remains stopped.
- Network `hearth_default`, backend bind `127.0.0.1:8010`, existing Traefik HTTPS route retained.
- Live image `sha256:7b667708a22108f125d6e4382b6a70f95814d62afdca8489d74cd09c676a3e7f`, reported build `762fd5fa0e9cff64179f5ec80d8846c0855e802e`.
- All 21 runtime application/assets/requirements hashes match that Git source after CRLF normalization. Raw hashes are retained separately; no unnoticed source discrepancy was waived.
- Python 3.11.17; installed versions captured. No H2 database, session registry/marker or H2 role/enrollment config existed in the production service.
- Initial capacity: about 6.5 GB available RAM and 83 GB free disk. The canonical data directory is root-owned; existing permissions were observed, not changed.

## Exact validated artifacts

Candidate source is the separate signed commit `5ce9ffefe09834fef763f22a9883adf97fe5380d` on `codex/shared-receipt-pilot-candidate`, parented by the verified live Git baseline. Its diff contains exactly the 17 reviewed source files, not the whole development branch. Signature verification passed using the existing signing public key and a temporary command-scoped allowed-signers file; no global trust configuration changed.

| Artifact | Exact host-local Docker image ID |
|---|---|
| Candidate | `sha256:d12b3f802136fdb35e73b5c1492526e0ba0b7b244a877987a949666e1432865c` |
| Fallback | `sha256:26e3d1d4134dc1924fa2c1fbef66ebf1205e1f3e0411a615becf92664f448265` |

Tags are `hearth-receipt-validation:candidate-5ce9ffe` and `hearth-receipt-validation:fallback-5ce9ffe`. IDs and the Docker-reported local RepoDigests are recorded in the manifest. Images remain unused by production and were not pushed or published; this does not prove external registry pullability.

Both overlays reuse the verified live image's base layers, existing dependencies and model cache. Builds used no network, pulls, apt/pip or model downloads. Independent inspection matched all **35 candidate** and **36 fallback** runtime files: reviewed payload bytes plus untouched raw live files, with the fallback wrapper as its one extra file. Every installed package version remained unchanged. The baseline requirements file remains unchanged; no extra native/acquisition/launch modules were shipped.

The fallback uses the same registry-aware authentication code but forces `HEARTH2_ENABLED=false` and an empty session enrollment before starting Uvicorn. Its entrypoint SHA256 is `681d54b0ee4d4f389b620f30cfbb364ce5321c5fd6093e44a63781d2852ff61f`. It is a feature-backout artifact, not a separate implementation that can repair arbitrary shared-authentication corruption or defects. Registry failure still fails closed; maintenance/forward repair remains the plan for an unhealthy guard.

## Isolation and checks

Local Docker integration was unavailable. Validation ran on the verified VPS in its own private directory `/docker/hearth-receipt-validation-20261109-5ce9ffe`, with fresh fixture storage/credentials, network `none`, no published ports, `traefik.enable=false`, read-only root filesystems, 768 MiB/one CPU/256 PID limits and transient independent cleanup guards. No canonical volume, production secret file, Docker socket or production network was mounted. TLS traffic stayed on loopback inside each validation namespace. This is actual-container fixture acceptance, **not another real-chat/shared-route rollout**.

- **409 tests passed, zero failures/errors/skips**, in 109.161 seconds. All legacy Python suites plus the selected shipped server/session/client/control/status/record contracts ran against image code at `/app`. The client/inbox modules were mounted as test-only client code, not added to the image.
- Actual direct-application TLS lifecycle exercised initial store-before-ack, receipt retry, eight server-process restarts, real-clock expiry, human revocation and de-enrollment. Receipt stays exactly one, with original timestamp/sequence/digest.
- Candidate default Docker CMD was separately started unchanged against the fixture. Active delivery and acknowledgement retry passed; broader session access failed; operator REST and actual MCP initialize succeeded.
- Fallback used its **real entrypoint**, while the container configuration deliberately tried to enable H2. H2 remained disabled. An additional generation D first succeeded on the candidate and was then permanently removed by fallback startup.
- Fallback passed a **real Docker restart** with the same fixture data. Expired A, revoked B and removed C/D still failed delivery/ack, broader REST/MCP/login checks. Positive operator controls passed.
- Independent post-run read-only SQLite/inbox verification found one identical server/client receipt and matching canonical body digest. Understanding remains **unknown**; the carrier task stays **running / claim recorded**; task/run/claim/notice/incident/attempt values match the pre-delivery baseline.

The selected suite does not claim all 1,145 full-reference tests. Root/native dispatch recovery is intentionally outside the shipped package; the server control/recovery suites were exercised instead. No native worker, provider or paid API probe was invoked.

## Corrections and limits recorded

The first runner attempt was stopped after a multiprocessing setup error: a spawned child re-entered runner initialization. A subsequent completed attempt exposed a missing test-document fixture and one accidentally selected out-of-scope native recovery module. The runner was guarded correctly, the real specification fixture restored, and selection aligned to shipped server contracts. No product code, image ID or dependency changed to make the tests pass; no missing-module stub was introduced. Failed attempts remain recorded and are not counted as passes.

One read-only preactivation review found incomplete fixture credential retirement in the test orchestrator. Cleanup now removes generated operator/session/TLS-key/env files **and clears the fixture token map** after owned containers stop; final independent verification passed. The review also prompted the separate normal-CMD check. No re-review or exercised deadline-expiry/forced-kill branch is claimed. Normal guarded closeout was observed.

## Closeout and approval boundary

All validation containers were removed and the transient guard exited. Generated fixture bearer credentials and TLS private key were retired; the fixture token map is empty. Public certificates, databases, logs and manifests remain private evidence; unused image tags remain for review. No background pilot, worker or automation remains.

Production container ID, image, start time `2026-11-08T09:59:58.228502365Z`, mounts and Compose hash remained unchanged. Final public health at `2026-11-09T16:45:40.417688+00:00` returned Memory/homeserver ok and the original `762fd5f` build. Normal shared HM writes may change global counts; no claim is made that the shared database was frozen.

The rollout packet/manifest now records resolved inventory and these image identities. **Do not deploy either image or change shared enrollment on this task's authority.** Remaining gates are explicit review/approval of these exact artifacts, the final pilot cutoff/cutover sheet, and the cold-backup/restore checkpoints at an approved maintenance boundary. A validation-only cleanup guard is not proof of the future shared-service pilot cutoff.
