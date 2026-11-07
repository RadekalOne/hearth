# MCode 0.4.1 data-directory source audit

Static verification on RSLABINSKI-PC, 6 November 2026, against the installed
public `@minimax-ai/code` package. This completes the next **source-audit slice**
of the data-directory plan; it does not complete Task 1 or install a path map.
Product code and its existing four-role conditional acquisition map are unchanged.

Only public package text was read. No package JavaScript was imported or executed,
and no user configuration, credential file or ambient credential value was read.
These pins describe the inspected bytes, not authenticated provenance of a runner
image, effective runtime behavior or a complete credential inventory.

## Recheckable evidence

Private evidence is retained in this plan's existing workspace:
`.superpowers/sdd/2026-11-04-mcode-data-directory-port/native-source-audit-20261106.json`.
It contains six SHA256 pins, 18 exact anchor locations and 16 bounded excerpts,
with zero-based UTF-16 offsets. Every excerpt and file pin was read back against
the installed public source. Evidence SHA256:
`9543baa9a2a1fc4d05d876356fc5ebfd5f1d4eef706cf259690e9eeff3780ad5`.
The accompanying private `audit_public_source.ps1` reads only the fixed public
package paths and writes that evidence; rerunning it produces a new capture time
and therefore a different evidence-document digest.

| Public chunk | SHA256 |
|---|---|
| V7D3N7GI | `619ff2ee477d5339b7b3f70ab17c500d5618e52c64b53a270adbb0cd523e1e6a` |
| 6BYKHQOV | `b79bf405b47654e4295b918bfc0bf5d84e4f73d3b05197c89c909dedef8f9b9f` |
| AAJMOWWM | `acf1ff9d270aca155e09b747d3e475a7e48c24bd5f84241d5268c1e3e1155674` |
| GOLYEPEW | `fc77436612ef5b8d771252eb6f47772e2f4b19ee82e8a815b351f78540f4c9a0` |
| 4NX3LPKA | `0be24cbc0d87177be43f7e7888d85c2209f5565bf92d1fecea5fa12fe451a887` |
| 2ZG44JU6 | `a1c8ac338d1b66a9d71bd508f1d30e6c1ea0cf2b20a505b1ef32b2c910bc4c74` |

## Root resolution has separate entry points

`V7D3N7GI` resolves a trimmed `MINIMAX_DATA_DIR`, then trimmed `MAVIS_DATA_DIR`,
then its default. Its imports bind `s` from `6BYKHQOV` to the pure primary-path
builder `at`, and `ja` to profile selection `Qs`. The default is therefore the
home-relative `.minimax` or `.minimax-<profile>` spelling. Its build-environment
argument does not append an environment to that root. This helper does not itself
perform legacy migration.

Separately, `6BYKHQOV` functions `ii`, `nn`, `li` and `W` implement configuration
resolution. `ii` selects `--data-dir`, trimmed public data-dir environment values,
then the gated legacy runtime `DATA_DIR`; `nn` selects `--profile` then gated
legacy runtime `PROFILE`. The `__MAVIS_RUNTIME_*` inputs are honored only when
`__MAVIS_ALLOW_LEGACY_RUNTIME_ENV` equals `1`. The argument parser accepts both
`--name value` and `--name=value`; it is not a shell expander. Do not substitute
the acquirer's current argv, environment, HOME or working directory for enrolled
configured-source evidence. Relative configured paths require separately bound
resolution context; the current absolute-path scope gate still refuses them.

`W` considers both `.minimax[-profile]` and `.mavis[-profile]`. Its `cs` branch can
migrate/rename/copy legacy data, create compatibility links, or return the legacy
root when data is inaccessible or migration fails. A primary directory containing
only an empty `workspace` is considered empty; unreadable legacy data is not
treated as absent. Existing links and backup siblings require explicit discovery
disposition. The acquisition port must never call these mutating resolver functions
to discover roots. Naming the primary path does not prove the legacy root empty.

## Verified role paths and multiplicity

`R` is one independently enrolled canonical root. `E` and `G` are declared
environment and region identities, not arbitrary caller path components. Namespace
validation accepts `dev`, `test`, `staging`, `prod`, and `cn`, `en`; this package's
embedded standard build is `prod`. Enumerating other namespaces is not authority
to run another build. CLI `pre` aliases `staging`, and the inspected standard
package rejects explicit `--env` unless the internal-package gate permits it.

| Existing source kind | Verified location or bounded unknown | Multiplicity / source anchor |
|---|---|---|
| pi-auth | `R/codex-auth.json` | Root; GOLYEPEW provider-auth construction at 8362974 / 8523973 |
| oauth-store | `R/auth/E/G/mcode-public/auth.json` | Namespace; AAJMOWWM `J`, plus 4NX3LPKA passing `namespaceHome` as store `authHome` |
| oauth-state | `R/auth/E/G/mcode-public/auth-state.json` | Namespace; AAJMOWWM `J` |
| projection-namespaced | `R/cli-auth/E/G/local-runtime.auth.json` | Namespace; GOLYEPEW `lx`/`g6i`, imported `Xp`; 6BYKHQOV `an`/`oc` |
| projection-legacy | `R/cli-auth/E/local-runtime.auth.json` | Environment; GOLYEPEW `h6i`/`y6i`, gated by legacy scope marker |
| projection-shared | `R/local-runtime.auth.json` | Root; GOLYEPEW `n4`/`Xp`, 6BYKHQOV `an` |
| lease-capability | `R/run/mcode-auth-lease-v1.cap` | Root; GOLYEPEW `rha`/`FQi`; path verified, acquisition/parser still unsupported |
| account-identity | `R/cli-auth/E/G/account-identity.json` | Namespace; GOLYEPEW `fpa`/`ppa` |
| shared-selector | `R/cli-auth/shared-projection.json` | Root; GOLYEPEW `Sue`/`qpa` |
| scope-marker | `R/cli-auth/E/G/cli-auth.scope.json` | Namespace; GOLYEPEW `Eue`/`Cue` |
| legacy-scope-marker | `R/cli-auth/E/cli-auth.scope.json` | Environment; GOLYEPEW `y6i` |
| region-selector | `R/preferences/mcode-region.json` | Root file, keyed by environment; AAJMOWWM `ve`/`_e`/`mt` |
| legacy-encrypted | `R/auth/credentials.enc` | Root; AAJMOWWM `J` declares it, not evidence of decryption support or use |
| mcode-config | `R/config.yaml` | Root; 6BYKHQOV `ie`; route/header content still needs the existing pinned parser |
| host-model-ref | No stable file path established by this audit | Unscanned; request/config model references do not establish a file role |
| mcp-consumers | Consumer universe and closure not audited here | Unscanned non-file obligation; no recursive plugin/session walk |
| environment | Configured source set must be independently enrolled and measured | Unscanned by this static audit; never read ambient values to fill it |

The map therefore has **14 roles with source-established path spellings** and
three obligations without source-established file paths. Verified spelling does
not establish parser support, actual presence, clean absence or physical coverage.
Only the existing Pi/config/OAuth store/state conditional adapter remains enabled.

OAuth account derivation is now directly source-established: AAJMOWWM `J` computes
the SHA256 base64url digest of the resolved auth-home string, a NUL, then
`mcode-public`; its service is `com.minimax.mcode.oauth.E.G`. Store record keys use
service, NUL, account (`Q`). This is target-platform path-string dependent and
does not identify a human account. A later mapper may check an independently
enrolled expected value; it must not mint enrollment from its own derivation.

The shared selector compares a SHA256 fingerprint of JSON serialization of the
trimmed auth projection. This audit establishes the source relationship, not a new
cross-language serializer, identity proof or projection-selection implementation.

The non-shared lease branch also derives the Linux endpoint
`R/run/mcode-auth-lease-v1.sock`; Windows uses a named pipe derived from the
normalized lower-case root digest. The socket is an unsupported filesystem object
for the file reader, never a regular credential candidate and never absence.
`FQi` writes the capability file using a different temporary pattern:
`<target>.<pid>.<16 hex characters>.tmp`, exclusive creation, file sync and rename.
Its path is now independently verified after a prior HM landscape record supplied
the search anchor; that record's runtime claims were not adopted as test evidence.

## Transients are evidence, not broad ignore patterns

AAJMOWWM writes credential/state data via `<target>.<pid>.<milliseconds>.tmp`,
exclusive creation, file sync and rename. The same temporary spelling occurs for
region selection and CLI projection/scope/identity writes, but those writers do
not thereby inherit the OAuth writer's exclusive-open/fsync guarantees.
6BYKHQOV's config writers use `.config-tmp-` plus six random bytes encoded as
12 hex characters and rename. Config backups and native migration backups are
separate material; they are not blanket benign temporary files.

AAJMOWWM creates `auth.lock` as a file and delegates locking to bundled
proper-lockfile. The dependency in 2ZG44JU6 function `J` defaults to appending
`.lock` and uses `mkdir`, so the adjacent lock object is `auth.lock.lock`, a
directory. Config locking likewise uses a `.lock` directory; one writer resolves
the config realpath first. The port still refuses symlinks and unexpected mounts
instead of following native realpath behavior.

These exact spellings are inputs for later map tests, not installed exclusions.
Do not ignore arbitrary `.tmp`/`.lock` names, descend lock directories, or treat
their presence as proof that a credential write completed. Every visited entry
still consumes work and contributes type/metadata evidence. A future precise
transient classifier must preserve unsafe type, identity, race and budget failures.

## Next bounded implementation

Implement the pure version/hash-pinned source-map and enrollment contracts using
the established multiplicities, with synthetic tests before behavior changes.
Keep lease acquisition unsupported, and host-model-reference, MCP and environment
obligations explicit and unscanned until their respective contracts are verified. Discovery
must bracket the root rounds and independently compare the complete enrolled
root/namespace/configured-source universe. Fresh helper isolation, hard timeout
and reap, root/image provenance, complete physical inventory and live acceptance
remain subsequent gates. The 900-second/full-run policy remains inactive.

Validation for this audit is source hash/excerpt readback and an independent
read-only review. No product tests were added or rerun for this documentation-only
slice; the prior 1056-test result belongs to commit `1558f4f`, not to new runtime
acceptance.
