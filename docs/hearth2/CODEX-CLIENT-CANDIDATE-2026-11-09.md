# Trial Codex client candidate — 9 November 2026

Later execution update: Rad approved isolated installation and offline checks.
The candidate is now installed on the trial, but the unsupported-model refusal
check failed; no turn or service activation. See
`CODEX-01591-PREACTIVATION-2026-11-09.md`. The revision-2 proposal and manifest
below are the historical pre-execution review snapshot, not current run receipts.

**Review proposal only.** Smallest catalog-compatible stable candidate above
the current pin: **0.154.0 → 0.159.1**, retaining `gpt-6.1-sol`. Candidate runtime,
profile and account compatibility remain unverified. No candidate was executed.

Revision 2 addresses Claude's four required changes in
`drawer_0c02f4c2ca4904db4e7d8533390ecdec`. His verdict was PASS with required
changes before the exercise, not permission to install, activate or spend.

## HM and the WSL/Windows distinction

Rad reports switching from WSL to native Windows. Relevant HM records predate
this investigation:

- `drawer_5995445a540b793895f130aa1962c187` (23 October, Mavis): laptop PATH
  client 0.144.5 rejected the model; bundled Windows 0.163.0-alpha.11.2 reportedly
  ran it successfully. A newer-cache schema warning indicated an old client;
  deleting the cache was explicitly discouraged.
- `drawer_4956d0b90145c7b81823fe65eb76213d` (29 October): Windows chat still
  used a WSL checkout; native checkout recommended, not yet moved.
- `drawer_096b2dd4446a41d3fbe11119e103c656` and
  `drawer_cc4fe530cb2eefc89d75002988390692` (1 November UTC): native desktop
  checkout preparation and laptop transfer history, on distinct hosts.

Fresh local observations: Windows bundled client reports 0.167.0-alpha.3.2;
Windows npm package reports 0.164.0; native Windows catalog lists the exact model.
WSL Ubuntu-24.04 resolves codex to the Windows npm wrapper under
`/mnt/c/Users/rslabinski/AppData/Roaming/npm/codex`, which fails with
`exec: node: not found`. This establishes current path confusion, not the
historical WSL version or cause of every earlier failure. This chat's GPT-6.1 Sol
access and the separate trial worker's compatibility are different facts.

Read-only trial SSH confirms `srv2065995` runs Linux Codex 0.154.0. Both its
embedded catalog and the worker cache lack `gpt-6.1-sol`; the latter was fetched
28 October by 0.154.0. Thus there is a verified local trial catalog gap, with no
claim of a fresh server-side entitlement refusal. The earlier Cloudroom catalog
claim did not prove native CLI support. No cache deletion or model substitution.

Official documentation cautions that app-server model/list may use a bundled or
cached catalog. Listing alone, including supported_in_api, does not prove this
trial account can execute the model:
https://developers.openai.com/siwc/token-sharing-open-source/models-and-inference

## Candidate boundary and exact bytes

Inspected the published stable version sequence including patch releases.
Downloaded public Linux x64 archives to ignored local review storage, checked
SHA-512 against registry integrity, and decoded the JSON catalog embedded in each
binary. No npm install/lifecycle script or downloaded binary was executed.

| Stable versions above 0.154.0 | Exact model in embedded catalog |
|---|---|
| 0.155.0, 0.155.1, 0.156.0, 0.156.1, 0.157.0, 0.157.1, 0.158.0, 0.159.0 | No |
| **0.159.1** | **Yes, visibility=list** |

This is the first stable release above the pin with the entry in the checked
published sequence, not proof of the first version able to use a refreshed
server catalog. Alpha builds and custom backports are not proposed.

- Artifact: `https://registry.npmjs.org/@openai/codex/-/codex-0.159.1-linux-x64.tgz`
- Archive SHA-256: `9d6476abf421afe566c7afade3bb3c4aa1586c6f673c6a9e346b625e6b19561f`
- Binary member: `package/vendor/x86_64-unknown-linux-musl/bin/codex`
- Binary SHA-256: `f1cd7fa4ac866c724122f173d408a95385257cbcc9ac5ce5ddba42669c74ba97`
- Embedded catalog SHA-256: `719c75b77ed02c783263f8fe62532ecd0abc1d1ccf2c34b12e5d221d509995a1`

`evidence/codex-client-candidate-2026-11-09.json` contains registry integrity and
archive/binary hashes for all nine release checks. Registry integrity establishes
byte equality with registry metadata, not an independent supply-chain audit.
The SLSA provenance verification described below additionally authenticates the
artifact's signing/build identity; it does not establish runtime correctness.
Attempted public source-tag reads returned 404; no tagged-source behavioral diff
is claimed. Reviewer can reproduce by fetching the pinned registry artifact,
checking its SHA-512/SHA-256, reading only the specified tar member and decoding
the embedded JSON object beginning with `{\n  "models": [` without executing it.

## Proposed change, after review and applicable [APPROVED]

Select a private, root-owned, versioned binary only for the Hearth 2 trial profile:

```text
from: installed trial global Codex 0.154.0
to:   /root/hearth-runner-trial/clients/codex/0.159.1/vendor/x86_64-unknown-linux-musl/bin/codex
model: gpt-6.1-sol (unchanged)
selection: evidence/codex-client-candidate-2026-11-09.json#/pre_activation_profile
profile_id: codex-01591-candidate
host CODEX_HOME: /root/hearth-runner-trial/clients/codex/0.159.1/homes/<exercise_id>
container CODEX_HOME: /scratch/codex-home
```

That destination is proposed, not installed. Retain global `/usr/local/bin/codex`,
global npm, Cloudroom, other workers, login/config/cache and provider route.
No active profile is introduced. Existing fixtures' exact 0.154.0 checks stay
intact; broadly relaxing version checks would invalidate their evidence.

The exact selection point is the manifest's `pre_activation_profile` key with
the fixed ID `codex-01591-candidate`, in a candidate-specific fixture copy only.
There is no PATH lookup, automatic selection, environment-based binary override
or change to the existing fixtures' CODEX constant. A future fixture must reject
any different profile ID, path or hash. The data profile is prepared here; its
fixture consumer is not implemented or executed by this documentation change.

Every exercise, including --version and the negative control, must use a new
root-allocated host home under the versioned `homes/<exercise_id>` tree, mounted
only at `/scratch/codex-home` with explicit CODEX_HOME. HOME remains `/scratch`.
Provision the reviewed config into that fresh home; never inherit or copy the
installed client's config, auth, model cache or sessions, and never link/mount
its home. The offline exercises use no real login. A later approved real-account
profile also needs a separate version-owned home and its separately approved
credential projection; this proposal does not copy credentials. Keep reviewed
config/managed requirements read-only and cache/state writes inside the isolated
candidate home. Never let rollback point 0.154.0 at candidate-written state.

Before each future exercise, inventory the global Codex launcher and every other
Codex trial client/profile consumer, record their exact resolved paths and wrapper,
binary and profile-config hashes without exposing config contents. Recheck the
same complete inventory afterwards: the global Codex launcher and all other
Codex profiles must still resolve the installed 0.154.0 binary hash below, with
unchanged wrappers/configuration. Missing, changed or unenumerated consumers
block promotion; a global PATH check alone is insufficient. Inventory/readback
are required acceptance evidence, not checks already performed in this revision.
Other providers retain their own unchanged pins; they are not required to
resolve the Codex binary.

Before activation or paid runs, a separately approved trial-only exercise must:

1. Verify artifact/binary hash, root ownership and read-only mount. Execute
   --version in a fresh credential-free, network-none disposable container.
   Record exactly `codex-cli 0.159.1`. After mount and before candidate exec,
   independently hash the mounted binary and recompute its embedded catalog
   hash. The resulting model/list must have exactly the manifest's eleven
   distinct slugs, with no omissions, additions or duplicates; compare the exact
   ordered list as well. A mismatch fails the exercise. Do not seed/refresh a
   cache to make the assertion pass.
   Request the full catalog including hidden entries using the candidate's
   reviewed protocol option, and retain that exact request. If it cannot expose
   the eleven-model catalog, stop rather than weaken the expected list.
2. Use a candidate-specific fixture copy with one exact version/hash. Verify
   managed requirements and effective never-approval/read-only policy, no
   shell/web/delegation and only scoped memory_search/memory_get. Unknown or
   ignored policy fields block promotion.
3. Initialize app-server, list models and create an exact-model thread without
   turn/start. No account credentials. No warning-based fallback.
   Negative control: request `hearth2-unsupported-model-negative-control` under
   the same profile. It must produce an explicit refusal with no replacement
   model, accepted runnable thread or native turn. Merely echoing an unknown
   model string, warning, or accepting it for a later network failure is not a
   pass. Do not submit a real provider request to obtain this refusal. If the
   native client lacks fail-closed selection, record the finding and stop for a
   reviewed exact-model launch-boundary fix; do not silently add an adapter or
   substitute a model.
4. Exercise existing synthetic loopback provider/broker tests with fake auth,
   network none and synthetic data: allowed read, denied write/shell, expiry,
   bounded output/settlement, no credential output and independently verified
   cleanup. This proves protocol compatibility, not entitlement or live A-tests.
5. Obtain Claude's review of the exact candidate/fixture changes/receipts. A
   failure leaves it inactive; do not automatically advance to latest.
6. Only with applicable explicit [APPROVED], current seat/spend evidence and the
   $75/month stop rule, attempt real-account exact-model execution and bounded
   paid acceptance. Subscription-only, one-workload and existing inactive
   900-second/full-run policy remain unchanged.

Rollback after any future approved run requires independently confirmed empty
workload before reverting trial-path selection. Retain 0.154.0 binary hash
`3188814c35471432d4123203e0eb38e5bddc60226e3d7ddf0e59e649ea140022`.
Rollback leaves senior launches blocked on the old unsupported catalog, never
substitutes a model, and never retries while termination is unknown. No global
or credential rollback is required; the private package may remain inactive.

Here independent stop confirmation means a non-controller observer principal or
Rad, not the candidate controller's own claim. Only after confirmed stop,
quarantine the candidate-written home/cache under a root-only retained path;
never merge, restore or reuse it with 0.154.0. Unknown termination stays held.

## SLSA provenance verification — required change 4

Registry endpoint:
`https://registry.npmjs.org/-/npm/v1/attestations/@openai%2fcodex@0.159.1-linux-x64`.
Selected only the `https://slsa.dev/provenance/v1` attestation, not npm's separate
publish attestation. Using the already installed Sigstore 4.1.1 verifier and an
isolated local TUF cache, verification passed for the DSSE signature, trusted
certificate chain, exact GitHub Actions OIDC issuer/workflow identity, and
certificate/signature transparency verification (threshold 1 each).
No package was installed and no candidate binary was executed.

The authenticated statement binds the package's SHA-512 to the exact archive:
repository `https://github.com/openai/codex`, tag `refs/tags/rust-v0.159.1`,
workflow `.github/workflows/rust-release.yml`, source commit
`8e68a98ef03cdde76d2e6800791ebdf1b3b95b24`, GitHub-hosted builder, invocation
`https://github.com/openai/codex/actions/runs/36619060118/attempts/2`.
The verifier explicitly pins issuer `https://token.actions.githubusercontent.com`
and the exact workflow URI at that tag. Wrong-identity and tampered-payload
negative controls were refused. This authenticates build identity and artifact
binding; source behavior, reproducible build and runtime compatibility are still
separate claims. Public bundle, statement and verification receipt are retained
in `evidence/codex-client-provenance-2026-11-09.json`, referenced by hash in the
candidate manifest. Temporary registry access URLs are excluded.

## Required-change disposition

1. Separate CODEX_HOME and quarantine: specified in the profile and every step.
2. Selection point and unaffected consumers: exact manifest key and mandatory
   full before/after resolution/hash inventory specified.
3. Unsupported-slug refusal plus exact version/catalog: mandatory fail-closed
   assertions specified, including mounted-byte/catalog recheck before exec.
4. SLSA provenance: cryptographically verified and recorded, with negative
   controls. Runtime assertions above remain planned, not executed or passed.

Current work changes documentation and an evidence manifest only. No executable
product/fixture change, installation, candidate execution, activation, paid run,
merge or production contact. This is not the live A4–A9/N2/N3 review packet and
does not advance Piece 2 to verified.
