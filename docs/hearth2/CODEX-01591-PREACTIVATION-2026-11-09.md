# Codex 0.159.1 pre-activation result — 9 November 2026

Follow-up: Claude accepted this native refusal failure and required Hearth's own
pre-thread guard. The targeted guard subsequently passed its offline unit/native
checks; see `NATIVE-MODEL-GUARD.md`. This original failure remains evidence; full
runtime compatibility and the remaining pre-activation checks are still open.

**Installed in the isolated trial path; pre-activation FAILED CLOSED.**
The native client accepted an unsupported model string at thread creation.
No turn was submitted, no actual substitution or inference was observed, and no
account entitlement is established. Service activation and paid runs stay gated.

Authority: Rad's direct `[APPROVED]` for isolated installation and credential-free,
network-none checks. Review: `drawer_0c02f4c2ca4904db4e7d8533390ecdec` and revised
packet `drawer_6325f88800fb5b2f7c7d4da792851cc3`. No production contact or change.

## Installation and fixture boundary

- Exact host: `srv2065995` / trial VPS2065995 / `179.236.82.242`.
- Installed binary:
  `/root/hearth-runner-trial/clients/codex/0.159.1/vendor/x86_64-unknown-linux-musl/bin/codex`.
- Archive SHA-512/SHA-256 and installed binary SHA-256 match the reviewed manifest.
  Binary: `f1cd7fa4ac866c724122f173d408a95385257cbcc9ac5ce5ddba42669c74ba97`.
- Fixed manifest profile selection: `pre_activation_profile`, ID
  `codex-01591-candidate`; no global launcher replacement or active service profile.
- Fresh version-owned home for each fixture, mounted only at
  `/scratch/codex-home`; explicit CODEX_HOME, no inherited login/auth/cache/session.
- Read-only vendor/config/managed-policy mounts; UID1000, read-only rootfs,
  dropped capabilities, no-new-privileges, resource caps and Docker network none.
- The old fixture image was absent and Docker listed no images/containers.
  Fetched a minimal official Python checker image before the exercise, pinned
  to `python@sha256:5e2bdb1b0d542d5039cffb8181c65930093949194a65c365dfb1b0fe13a4fa5b`.
  Candidate execution had networking disabled. No application service was started.

Remote evidence directory:
`/root/hearth-runner-trial/codex-01591-preactivation-ag1aa_2g`.
The exact controller/probe, installation receipt, baseline, raw native messages,
first failed receipt and final failed receipt remain there. These fixture IDs are
not Piece2 live task/run rows.

## Observed checks

| Check | Result |
|---|---|
| Mounted binary and embedded catalog rehashed before candidate exec | Match reviewed hashes |
| Actual `--version` | `codex-cli 0.159.1` |
| Managed override attempt | multi_agent=false and shell_tool=false despite enable requests |
| app-server initialize | Reports isolated `/scratch/codex-home` |
| Full model/list including hidden | Same eleven distinct manifest identities; no missing/extra/duplicates |
| Exact model thread creation | `gpt-6.1-sol`, effective readOnly/networkAccess=false despite unsafe sandbox request |
| Unsupported slug control | **FAILED: successful idle thread returned with the unknown model string** |
| Real credentials, turn/start, provider inference | None |

The unsupported string was `hearth2-unsupported-model-negative-control`.
Its successful result reported that exact model and `thread.status.type=idle`.
This fails the required pre-launch refusal; a later provider error cannot satisfy
that check, and no real request was sent to obtain one. Do not equate acceptance
of a model string with model availability or actual execution.

The first fixture `codex-01591-26a36fb75aa84fa288d1f6233c54ef91`
(17:24:22–17:24:28 Eastern) stopped at an extra implementer assertion requiring
the RPC display order to equal embedded JSON order. All eleven identities were
present; the RPC displayed the selected model first. Retained that failure and
its original source. Corrected only the presentation-order comparison to strict
count + uniqueness + identity-set equality; embedded catalog bytes/hash and all
expected identities stayed unchanged. This is a disclosed change from the
proposal's added ordered-list assertion, not a waived missing-model check.

The second fixture `codex-01591-44bf620e642045d69d7ad622aaa1f798`
(17:25:39–17:25:44 Eastern) reached the substantive refusal failure and stopped.
The container process returned zero after serializing its failed assertion;
the authoritative fixture receipt is `status=failed_closed`, not PASS.

## Cleanup and unaffected state

For both fixtures, a root host observer outside the UID1000 candidate namespace
sampled the live cgroup, then independently checked stopped container/Pid0,
removed cgroup, and removed exact-ID/label-verified container. A subsequent
inventory found no candidate fixture containers. Both homes were moved to
version-owned root-only quarantine; never reused with 0.154.0.

All309 recorded baseline files retained their exact paths/resolutions/hashes:
installed global Codex tree/launcher, root/home default config/model caches,
user systemd/Cloudroom config trees, system units/cron files and recorded trial
configs/probes. This is the stated inventory coverage, not a proof about unknown
unregistered consumers. Global0.154.0 binary still hashes
`3188814c35471432d4123203e0eb38e5bddc60226e3d7ddf0e59e649ea140022`.
The isolated package remains installed and unselected for service use.

## Remaining gate and limitations

The approved plan says to stop for a separately reviewed exact-model launch
boundary if native refusal is missing. That is the next review item; no
launch-boundary product fix was silently added. Do not activate this profile or
try a different model/client automatically.

The initial MCP endpoint was a credential-free synthetic discovery stub, not the
actual scoped Hearth broker. Later read/forbidden-tool/expiry/output-settlement
exercises were not run after the refusal failure. Native startup also warned
that bubblewrap was absent from PATH and it would use its bundled copy; native
tool-sandbox execution was not exercised. These checks remain incomplete.

Evidence claims: catalog present; pre-activation gate failed; complete runtime
compatibility unknown; real-account execution unknown. No A4–A9/N2/N3 acceptance,
service activation, paid run, production action, merge or frozen-track work.

Local evidence: `evidence/codex-01591-preactivation-2026-11-09.json`, SHA-256
`0bc019c9c063736a7edcb85a1cfc6f8c91c32f6075d9d10473ee8d3a6ca4d174`.
Remote final receipt SHA-256:
`2a9faa25aaf53fd664783953f126d024871a8a443b6167d6abbd65a5ba464695`.
