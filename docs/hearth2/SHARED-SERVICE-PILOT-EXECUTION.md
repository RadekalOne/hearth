# Approved shared-service receipt pilot: execution receipt

**9 November 2026 — shared pilot passed and closed. H2 is disabled on the pinned registry-aware fallback.** Rad explicitly approved the final packet and the recipient-only amendment in this existing laptop chat. The task did not authorize ongoing delivery, workers, observers, provider probes or additional pilots.

The evidence is [SHARED-SERVICE-PILOT-EXECUTION-EVIDENCE.json](SHARED-SERVICE-PILOT-EXECUTION-EVIDENCE.json). It contains public operational receipts and redacted HTTP checks, not credentials, customer memory contents or the live backup. The earlier fixture image/cutoff reports remain separate evidence.

## Final running state

| Property | Independently read back at 19:22:54 UTC |
|---|---|
| Host / service | `vps01hst4hermes`, `2.24.70.124`; project `hearth-project-hub`, service `hub` |
| Container | `2ca9c3291ec6792120a5b6c3dd6aeff489bdc7ce721a5fdcb74b038af281a652`, running; started `2026-11-09T19:20:29.554204655Z` |
| Fallback image | `sha256:26e3d1d4134dc1924fa2c1fbef66ebf1205e1f3e0411a615becf92664f448265` |
| Source / version | Signed selected source `5ce9ffefe09834fef763f22a9883adf97fe5380d`; health version `0.10.18-receipt-pilot-5ce9ffe` |
| Configuration | `/docker/hearth-project-hub/compose.json`; SHA256 `6016dc4f905e2fc1fd358cc065fc2c7bca3acb9edba4e33cdf86222453018ffc` |
| Delivery | `HEARTH2_ENABLED=false`, empty named-session enrollment; fallback entrypoint independently forces both off |
| Restart policy | `unless-stopped` on the fallback; candidate had `no` while the pilot was enabled |
| Health / legacy access | HTTPS Memory and homeserver both ok; existing-agent REST/MCP and existing admin human-cookie controls passed; anonymous API requests remained 401 |
| Security closeout | A expired, B revoked, C removed; retired session credentials denied REST/delivery/MCP/login, retired controller denied 401. Newest registry and required marker preserved. |

Original `codex` token values and authority were preserved. The credential-free logical recipient/worker was `codex-receipt-pilot-01a194ad`; no credential or process was created for that worker. Non-pilot token mappings and all configuration outside the reviewed image/restart/build/H2 fields matched their original values. Other Compose services, routes, DNS, accounts, unrelated jobs and inactive 900-second/full-run policy were not changed.

## Live backup and maintenance gate

Before writes, the exact original container ID/image/start/configuration, canonical mount, stopped legacy container and single-writer state matched the packet. All 21 original runtime file hashes were verified against the earlier live inventory. The recipient, session, temporary controller and negative-test alias names passed token/reviewer collision checks.

Only `hub` was stopped. Container and host file-descriptor checks found no remaining writer to canonical data. The cold archive captured the complete live directory and original private configuration: **236 files, 104,841,931 bytes**. SHA256:

`f39bc8f681fca6faae4238ddcfc4d5d33581c9882c367b41d66a8a8ff9df13e3`

The archive is `/docker/hearth-receipt-pilot-approved/pre-pilot.tar`, mode 0600 under a 0700 private root. It was restored into a fresh non-serving `restore-check` directory. Every restored file and the archived configuration matched exactly. SQLite integrity checks passed for `coordination.sqlite3`, `inbox-acknowledgements.sqlite3`, `reviewers.sqlite3`, `work.sqlite3`, `chroma.sqlite3` and `chroma/chroma.sqlite3`. No live data was overwritten to test restore, and no production clone was exposed as a second service.

The auth-only candidate then passed public health, ordinary REST/MCP, human token-to-cookie login/status/logout, anonymous enforcement and disabled-H2 controls. The full maintenance gate completed in **22.656 seconds**, within the five-minute budget. A detached maintenance guard reserved the last 60 seconds for backout; it exited normally after the successful gate.

This actual cold backup is separate from the user-requested Hostinger snapshot created at hPanel time November 9 13:42, expiring November 10. Neither the pre-pilot archive nor that older provider snapshot is an automatic data/security rewind after issuing session credentials. Preserve newest revocations and legitimate newer HM writes; data-disaster recovery still requires its own reviewed decision.

## Real named-session acceptance

Target: this `RSLABINSKI-PC` chat `01a194ad-865c-7100-a33a-e220e62cff8d`, session `codex-laptop-01a194ad`, principal `codex-session-01a194ad`, recipient `codex-receipt-pilot-01a194ad`. The existing named-session client ran locally with only its session bearer, real public HTTPS/certificate verification and a private durable local inbox. It received one explicitly labelled receipt-only carrier notice; no native worker or model invocation occurred.

Project `project_75a7fede9de14b3ab2e294acd4838cf6`; carrier task `task_741877b0d3314cb38c8da887cdcfdf26`; notice `notice_363cde2b556a414cad97a4af3fb69c0c`.

Original receipt: sequence **11**, offered sequence 10, timestamp **2026-11-09T19:16:22.878911Z**, actor `codex-session-01a194ad`, digest `6417fb8f1d63a94617d79c6abbc60fdbf3436fc8f626241c32cd8546ad76aced`.

- The client proved the exact body/digest was stored locally **before** acknowledgement, then recorded one matching receipt.
- Actual container restart preserved it. Local replay stored 0 new notices and recorded 0 new receipts; explicit acknowledgement retry returned the original sequence/time/digest/actor.
- A worked before actual UTC expiry, then was denied after expiry and after a restart with the expiry configuration removed.
- Fresh B worked before human-authorized application revocation, then stayed denied across another restart. Controller/session attempts could not invoke human revocation authority.
- Fresh C worked before de-enrollment. A temporary general alias with H2 disabled did not grant broader access. Removing that alias and restoring former enrollment did not reactivate C.
- Twelve acceptance stages exercised **437 phase-specific protocol checks**, including intended receive/ack success, inactive receive/ack denial, generic REST/work/export, H2 mutation, MCP GET/initialize/tools-list/tool-call/batch, login conversion and cookie/mixed-header denial. Ordinary-user/admin positive controls distinguished confinement from blanket service failure.
- Independent server SQL and local SQLite readbacks matched the original receipt exactly. **Understanding stayed unknown.** The carrier task stayed **running (claim recorded)**; project-scoped task/run/claim/notice/incident/attempt rows were unchanged. That state does not assert worker liveness, comprehension or completion.

Eight lifecycle container recreations followed enablement. They did not extend or rearm the cutoff.

## Fixed cutoff and cleanup

The exact host helper remained byte-pinned to `d61c45be14dcbb0a2ce61a496195e7be6e99098c533f5cef116a87b82479a4cc`. The sealed approved pilot plan SHA256 was `b03aa151f93b05972c29080d1b598f35cc9705e88e9db0ded2b8a6b1b3f1e5f2`. Its detached guard was verified alive before merging pilot tokens or enabling H2. Original deadline: **19:35:21.730218 UTC**, never extended.

After acceptance, the approved early-cutoff path began at **19:20:28.394300 UTC** and completed on the disabled fallback at **19:20:33.493331 UTC**, safely before the deadline. It retired only the session/controller mappings; the temporary alias was already removed. Repeating the cutoff verified the existing fallback state and did not restart it again. After verifying fallback, the now-unneeded finite guard was retired.

Final independent readback found no maintenance/cutoff guard remaining. Remote working credential files and the local session bearer file were removed; local notice/receipt evidence and private cold backup were retained. Historical authentication material remains inside the private cold backup and original configuration evidence; no claim of erasing every historical secret copy is made. No backup archive or raw credentials were uploaded to chat/HM or committed.

## Operator review and execution corrections

One independent read-only preactivation operator review found a timeout-backout race and global rather than project-scoped receipt comparisons. One author correction canceled the isolated foundation process group before watchdog backout and scoped comparison rows. A real dummy-process counterexample produced a late write without cancellation; the corrected cancellation prevented it. An unrelated-project mutation fixture verified the comparison scope. The reviewer checked application payload/client interfaces but did not inspect live credentials or remote execution; direct observations supply those facts. No independent re-review is claimed.

Two execution-harness corrections did not change application code or images. The first local launch hit the host script filename `operator.py` shadowing Python's standard library before any network/inbox work; launching the actual client with Python `-P` corrected import precedence. First closeout verification expected a role-level controller denial, while the already-retired controller correctly returned 401. The checker was corrected to distinguish disabled-but-mapped 409, active unauthorized 403 and retired 401; fallback remained disabled throughout that correction. The original assertion is retained in evidence as a resolved checker error.

This completes the approved shared receipt pilot. H2 remains disabled. Further enablement, another pilot, ongoing polling, observers, workers, provider access or a broader rollout requires new explicit scope; no such work was started.
