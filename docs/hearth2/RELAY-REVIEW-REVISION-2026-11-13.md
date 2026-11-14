# Intake-only relay — Claude review revision

This follows Claude's desktop review `$gxLSTtKeu_b4RyiBBwOSI-66h8FnBgYanmVdrvYBM2I` and Cowork review `$ccJiyaQvyafIv0n-DFOB6ZDAE20FK9a308PitLXf8X0` of head `af4e934` / runtime `9166cf7`. The revised source received two Claude PASS reviews and intake-only mode is now enabled under Rad’s current direct instruction. See the activation receipt below. Model turns and paid runs remain blocked; production is unchanged.

Rad's current direct instruction in the existing Hearth v2 chat is: “Check Claude’s review, address any findings, and enable the intake-only relay once it passes. Keep model turns and paid runs gated on my [APPROVED], and production unchanged.” This is recorded as conditional intake-only enablement authority. Claude's relayed Cowork approval remains attributed context, not a substitute for Rad's own instruction. Review and human authorization remain distinct; this report imposes no escalation rule on another reviewer.

## Findings addressed

1. **Missing installed artifact provenance.** `relay_install.py` now deterministically builds `manifest.json` and `live-config.json` from the public program/recovery sources, fixed non-secret path settings and hardware model. The installer invokes this committed producer; no follow-up manifest patch is needed. It backs up previous configuration/history and stays disabled. Generator, installer and activation script are included in the twelve pinned program files; the independent recovery file is separately pinned. Unknown existing configuration refuses instead of being overwritten.

   Both files are published verbatim under [evidence/relay-live-adapters-2026-11-13](evidence/relay-live-adapters-2026-11-13/). Their schemas contain only paths, model/host, mode, seed event and public artifact hashes, never credentials. Independent regeneration from the source checkout equals the actual installed files byte for byte. Manifest SHA256: `17ff37f50dcc2dffe0d8b33b933a68aefa679356c8de79930cb5464fb86aa8c8`; configuration SHA256: `4ee9fa2a008bd70353a9e99444ff83d2c751b679412d401ef7c9787cfc26b51e`.

2. **Refusing review quoting an activation packet.** A passing packet must occupy the entire body after `[REVIEW]`, either plain JSON or one complete JSON fence. Prefix/suffix prose, quoted pass packets in a HOLD/FAIL message, malformed JSON, wrong source or manifest/mode mismatch refuse. A reviewer can post commentary separately. This gate is a procedural safeguard for the trusted owner, not a security boundary against that owner. No claim is made that review revocation is continuously checked at runtime.

3. **Work review not bound to verdict/work.** Intake requires an authenticated Claude whole-body `hearth_relay_work_review` with verdict `pass` and exactly the approved work's work_id, generation, base_commit, paths, aliases and scope. The Rad approval separately names the fetched review event. The review excludes its own event ID because the server assigns that only after posting. HOLD/FAIL, other work and quoted packets do not qualify. This does not open dispatch: `ready_for_claim` stays false and financial authorization still refuses.

4. **Intake-only posting/error behavior.** Live relay ports prohibit room posting, including legacy pending outbox rows and first-read errors. Intake failure records the local receipt and `intake_unavailable_or_gap` control status on each attempt, rather than sending the stale “adapter required” message. A gap still does not advance the cursor. Automatic cursor recovery is deliberately absent: it would need a separate bounded recovery design rather than silently adopting a new position.

5. **Procedural gate pinning.** The activation script and installer now have manifest pins. They remain trusted-owner operator steps; runtime source integrity is checked, but a continuous review revalidation claim is not made.

6. **Legacy task description.** Deferred cosmetic: “disabled candidate” remains the existing exact-owned-task identity string used by independent recovery. Current scheduler/control state is reported separately and is authoritative; renaming this string would change the recovery contract.

7. **Public RPC response digests.** Raw response digests are omitted from the current public evidence; private diagnostic receipts retain them. Historical Git commits are preserved, not rewritten.

## Independent reproduction

Without executing the client or reading a credential source:

```python
import sys, hashlib
from pathlib import Path, PureWindowsPath
sys.path.insert(0, 'ops/hearth2')
from relay_install import build_artifacts
root = Path('docs/hearth2/evidence/relay-live-adapters-2026-11-13')
import json
m = json.loads((root/'manifest.json').read_bytes())
cfg, manifest = build_artifacts(Path('ops/hearth2'), Path('ops/hearth2'),
                               PureWindowsPath(m['program']).parent, m['model'])
assert cfg == (root/'live-config.json').read_bytes()
assert manifest == (root/'manifest.json').read_bytes()
print(hashlib.sha256(manifest).hexdigest())
```

## Validation and chronology

Ninety focused credential-free Windows tests pass (12.162s). All **1,330/1,330** full canonical-source tests pass (133.737s test runner; actual Docker exit0). Outside-controller timestamps: **2026-11-14T04:41:15.518619Z–04:43:34.377474Z** (13 November,11:41–11:43p.m. ET),138.859s including container startup/shutdown. Source tree `63a7905e036f808feb963af7fa90dfbfd10d6e8c`, archive SHA256 `e0824ccfce0b1aaf6a72e364462abf7cfee6292fd3639ff957da743e5bf0ce77`. Runtime `f13de43f0be982e884cb77cae3bbe74e659420a4` has that exact tree and all installed source/recovery pins match its Git blobs. See [timed evidence](evidence/relay-review-revision-2026-11-13.json). External networking is disabled and source/dependencies/cache are read-only.

For the earlier chronology question, the retained original test log's filesystem creation/last-write timestamps, observed retrospectively, are `2026-11-13T23:11:31.406170638Z` and `2026-11-13T23:13:35.953020568Z`. Runtime `9166cf7` was committed at `2026-11-13T23:13:57Z`. These are retrospective filesystem observations, not newly invented historical runner timestamps. The new explicitly timed run provides the replacement evidence for this revision.

The actual revised installed paused diagnostic completed `2026-11-14T04:40:11.674811Z`–`04:40:14.813632Z` (13 November, 11:40 p.m. ET): authenticated intake complete, no pending work, native metadata complete, zero model turns, original login bytes unchanged and named native Job empty. These are Codex's laptop observations; Claude's source/Linux tests remain independent evidence of their own scope.

## Activation review format

After reviewing the exact revised artifacts, a passing Claude review for intake-only activation must contain only `[REVIEW]` followed by this packet (one JSON fence is also accepted). Any analysis/refusal goes in a separate post; copying this packet inside refusing prose no longer passes.

```json
{"hearth_relay_activation_review":{"verdict":"pass","mode":"intake_capacity_only","manifest_sha256":"17ff37f50dcc2dffe0d8b33b933a68aefa679356c8de79930cb5464fb86aa8c8"}}
```

Only after authenticated review passes may the user's conditional intake-only enable instruction be executed using the installed, pinned activation script. Existing hourly 07:00–23:00 ET triggers remain unchanged. An enabled schedule or future next-run timestamp is never proof that a timer run executed. Manual diagnostics and manually triggered scheduler checks are labelled as such. Outside-window checks must remain outside-window; do not alter the clock/window for acceptance.

Intake-only is not an autonomous coding loop. No task generation is claimed, no model or paid run is authorized, understanding remains unknown and task completion is unchanged.


## Actual activation — 13 November,11:52p.m. ET

Claude's desktop analysis `$2jFKjWvtxbOeycnDN7eiBe4t-PV4ObgxjahsbuY-CII` and laptop analysis `$YYoI-9ZrXQtzjEFxmQ9DCrqC5uCm4X5inI-S1j-nbM8` both passed the exact revised intake-only source. Both were source reviews; neither ran the new tests. At activation, the separate Cowork Linux rerun had not yet been observed. It subsequently completed at05:59Z on14Nov with a scoped intake-only PASS; see [Cowork closeout](COWORK-LINUX-CLOSEOUT-2026-11-14.md). The desktop pass packet `$iPpI7hkqAGrdu0mApksvcgh7_211u-yR-B_Q2wyOW48` was fetched in full and verified against actual installed manifest SHA17ff37…aa8c8. The second matching packet is `$WdbdX0Qpu9Ycqwh8Yra3jJCc6vHQai5ZbmxwHDeDFwg`.

Human enablement authority is Rad's **current direct instruction in this active Hearth v2 laptop chat**, quoted above, conditional on review passing. It is not Claude's review packet or the relayed Cowork approval. Earlier relayed wording about an additional on-commit approval is attributed context; the current direct instruction supplies the conditional intake-only action. No model/paid authority is inferred.

The installed, pinned activation script verified the exact manifest, authenticated Claude packet and fresh live diagnostic, backed up SQLite and enabled only the existing owned task. Actual activation timestamp `2026-11-14T04:52:49.600208Z`; epoch21, paused0/enabled1. The manually triggered Task Scheduler invocation started04:52:50Z and exited0. Its intake poll ran04:52:51.126846Z–04:52:54.127030Z, processed through `$WdbdX0Qpu9Ycqwh8Yra3jJCc6vHQai5ZbmxwHDeDFwg`, no pending work, no outbox rows, zero model turns, no active process and no remaining native home. State: `enabled_inference_gated`. [Activation receipt](evidence/relay-intake-activation-2026-11-13.json).

The existing17 hourly07:00–23:00 ET triggers, limited interactive user, no-wake/no-catch-up settings are unchanged. A next-run time is not execution proof. The desktop **Pause Hearth relay** action remains the single-step stop/disable control. No production change, paid run, model turn, merge, deploy, global credential/account setting or unrelated job change occurred.

Remaining non-blocking notes: the unused installer hash variables and duplicated fixed-path constants are retained; normalization mismatch or constant drift fails closed. Task's legacy “disabled candidate” identity text is retained for recovery matching. Cursor recovery and continuous review revalidation remain absent. Original review edits do not revoke the original event; redaction does. If configuration or a credential source fails before the live adapter is constructed, `control.last_check/status` updates but `live-receipt.json` may retain its previous successful poll; operators must inspect both, and silence is not health proof. No claim of actual unattended coding is made. The later independent Cowork Linux acceptance and its test-only clock fix are recorded in the closeout.
