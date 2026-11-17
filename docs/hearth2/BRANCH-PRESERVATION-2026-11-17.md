# Hearth 2 branch preservation and local only inventory

17 November 2026. New runner implementation is paused at Rad's request. This is a preservation checkpoint, not a merge, deployment, login or run. The existing read-only relay and unrelated jobs are untouched.

Scope checked: the dedicated native checkout on RSLABINSKI-PC at `C:\Users\rslabinski\Projects\hearth2-transfer`, its registered Git worktrees, and the supplied HearthV2 work directory. There is one registered worktree. No other Hearth checkout appeared in the immediate Projects directory; the supplied G-drive work folders are not Git repositories. Historical WSL/desktop copies and trial-VPS artifacts were not re-inventoried by this request.

## Branches preserved remotely

Origin was freshly fetched and each of these 12 local tips matched the actual GitHub remote (`git ls-remote`). `git push origin --all` confirmed everything was already up to date before these two documents. There were no uncommitted tracked changes or non-ignored untracked files to rescue, and no local-only branch commits. These documents are committed and pushed on the current feature branch; final remote equality is checked after that push. No empty commits, force pushes, merges or main-branch updates.

| Branch | Preserved tip |
| --- | --- |
| `codex/hearth-offline-relay-disabled` | `cb77197` |
| `codex/hearth-offline-relay-pause-outcomes` | `b4f23af` |
| `codex/hearth-offline-relay-pause-recovery` | `1eda058` |
| `codex/hearth-offline-relay-plan` | `49c6977` |
| `codex/hearth-relay-live-adapters` | Code tip `caa4488`; this report adds a documentation-only commit |
| `codex/hearth2-broker-denials-budget` | `c77177c` |
| `codex/hearth2-minimax-consumer-parser` | `0056dc2` |
| `codex/hearth2-native-turn-private-broker` | `b33d25d` |
| `codex/hearth2-runner-broker` | `7e13418` |
| `codex/hearth2-turn-review-abc` | `6170160` |
| `codex/hearth2-walking-skeleton` | `55095c7` |
| `codex/shared-receipt-pilot-candidate` | `5ce9ffe` |

Remote repository: https://github.com/RadekalOne/hearth . Preservation does not mean reviewed, merged, deployed or accepted. The frozen inventory/receipt tracks are preserved without reopening them.

## What remains local only

The following ignored material is not covered by the branch pushes. Counts describe the inventory at this checkpoint, not a promise of an independent backup.

| Private artifact directory | Files | Bytes |
| --- | ---: | ---: |
| `.superpowers/ccusage-evaluation-20261110/` | 23 | 16,584,659 |
| `.superpowers/model-client-review/` | 84 | 5,228,168,265 |
| `.superpowers/sdd/` | 12,640 | 749,860,168 |
| `.superpowers/shared-pilot-approved/` | 31 | 256,260 |
| `.superpowers/shared-pilot-rehearsal/` | 22 | 98,569 |
| `.superpowers/shared-service-image-validation/` | 126 | 2,365,528 |
| `.superpowers/shared-service-rollout-review/` | 194 | 4,304,059 |

There are also 32 files directly under `.superpowers/`: helper scripts, logs, manifests, local source/test archives and release/rehearsal receipts. The scripts include `walking-evidence.py`, `walking-recover.py`, four `ccusage-*.py` helpers and four lifecycle-verification helpers. These private helper implementations, plan ledgers and raw evidence remain **local-only**, even though the reviewed product code and concise public evidence are in Git.

Python `__pycache__` directories are ignored, regenerable and local-only. App chat histories, local automation settings and personal memory files are outside this repository; branch pushes do not back them up. Existing HM checkpoints/outcomes and HC posts are remote continuity, not copies of every local artifact. The G-drive handoff found here is for VERDIGRIS and is unrelated to Hearth 2, so it was left alone.

Raw artifacts may include authentication-bearing or environment-specific material. Nothing under `.superpowers/` was bulk-added or published; no credentials, auth caches, environment files, database copies or broad transcripts were copied into Git. No claim is made that local-only artifacts are backed up elsewhere. Trial-VPS receipts/test snapshots remain on that host unless their concise evidence was already committed; their current inventory was not checked in this preservation pass.
