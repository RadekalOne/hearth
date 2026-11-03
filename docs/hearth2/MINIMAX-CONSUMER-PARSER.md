# Inactive MiniMax credential input syntax parser

This component classifies explicit acquired byte snapshots, not running Mavis or
her configuration. It is not the complete credential inventory backend and is
not wired to the collector or launcher. Empty counts never establish absence.

Pi syntax semantics are pinned to public `@minimax-ai/code` 0.4.1 core
`chunk-ORVAHBJL.js`, SHA256
`ab278b848d10c3b8721fc00f76512994f39db9eba6691492b74c2135afa2703b`.
Static source was read locally; no client/JS/helper was executed. `getApiKey`,
`BC`, `mZe`, `Tfe`, `u$` and `getApiKeyAndHeaders` define the relevant branches.
Version/hash parameters express the parser contract, not physical attestation.

`MiniMaxConsumerParser(version, core_bundle_sha256)` accepts exact reviewed
identity. `pi_auth_json(bytes)` scans ALL provider entries, not just the selected
provider. Exact `{type:api_key,key:string}` records classify key syntax; OAuth,
unknown/missing types and extra fields count as unknown records. Their semantics
remain unresolved, even if another key would override them at runtime.
`pi_headers_json(bytes)` classifies a Pi ModelRegistry provider OR model header
string map; this is bundled syntax, not a live MCode header route.
`pi_runtime_overrides_json` and
`environment_json` classify ALL supplied strings as literal inputs, without
performing expression expansion. The latter is a snapshot parser, not discovery
of provider environment names, ambient process environment or consumer coverage.

For Pi stored API keys/headers only, a leading `!` denotes a command route and is
never run. Native templates support `$NAME` and `${NAME}` for ASCII identifiers,
with `$$` and `$!` escapes. Malformed references remain native literal text.
The output counts environment-bearing fields and reference occurrences without
resolving or outputting names/values. A literal string may itself be a credential;
literal does not mean safe. Empty fields are explicit. Whitespace is preserved.

Each input is at most 65536 bytes, JSON depth at most 8, at most 2048 total
nodes including keys, strings at most 8192 UTF-8 bytes, map names at most 256
ASCII bytes. Duplicate keys at every level, nonstandard numbers, invalid UTF-8 or
surrogates, excessive depth/nodes/strings and invalid supported-map types refuse
with a fixed redacted RecordError. No paths, values or source-controlled names
are retained by ConsumerSyntax repr/results. Source exceptions are suppressed.

This parser never selects an effective credential, resolves helpers, reads files
or ambient environment, refreshes OAuth, loads extensions, invokes keychain or
emits collector success schema. Auth storage can use environment fallback even
with includeFallback:false; effective runtime overrides precede stored auth while
status labels can report a different branch. Headers can independently carry
credentials. No precedence is inferred from these syntax counts. Full BYOK YAML,
OAuth, token projections, consumer closure and physical source acquisition remain
unimplemented here. Bundled Pi capabilities must not be inferred to be reachable
through the MCode CLI. See the source-map correction below.

Next work must bind independently acquired snapshots and full audited native
consumer manifests/parser closure to the original image/CID/assembly/scan policy,
cover environment/config/mount sources in both fresh collector rounds, and refuse
missing or unknown sources. No physical source/root/namespace/provenance,
credential completeness, native runtime or production acceptance is established.

Historical first-slice verification on 3 November 2026: 14 missing-feature tests first failed; 17 focused
tests then passed. One fresh final Codex review found no Critical/Important/Minor
issues and passed 17 focused plus 13 additional boundary/redaction checks. Full
isolated Ubuntu-24.04/Python 3.12 suite passed 821 tests in 288.517 seconds,
actual exit 0, with only loopback enabled. Immutable source archive SHA256
`4b7a1798067fc2ce072cc1eb88a1ef24fe33f4272d410cc29c916577c53b1974`
matched the original parser/test bytes at commit `76bcbe4`; that code is
superseded by the route correction below. No fix pass or
rereview was needed. These are offline source/fixture results, not native, OS,
physical provenance or complete credential-inventory acceptance.

## Source-map correction following Claude's investigation

Claude's source map (HM drawer_35c9d39c5611135a5ea498e0db2eb9e5) separates
MCode's LocalModelResolver from bundled Pi AuthStorage/ModelRegistry. Independently
checked all 11 locally available package/source hashes against his report (the
registry tarball itself was not independently fetched). Positive source anchors
in OFHDMZSQ, GOLYEPEW, AAJMOWWM and 6BYKHQOV confirm literal BYOK keys/headers, the explicit
codex-auth.json getter, file OAuth store and managed-host authMode inference.
This is static source evidence, not proof about active desktop sessions.

`mcode_headers_json(bytes, resolver_bundle_sha256=...)` classifies a single
acquired MCode header string map literally, including values beginning `!` or
containing `$ENV`. It requires the reviewed LocalModelResolver OFHDMZSQ hash
`7f91af66b8692739662669da6a04ba294d9da871bb667b19ce6ff98cddd42e73`
in addition to the parser's core identity. This is identity matching, not source
attestation. No YAML loading, field selection, header merging or effective model
selection is performed. Malformed maps refuse rather than using native silent
field filtering. The old ambiguous auth_json/headers_json/runtime_overrides_json
entrypoints are removed; their explicitly prefixed Pi replacements preserve the
previous grammar. No live callers existed in this checkout.

In MCode 0.4.1 the report traces Pi AuthStorage through `<dataDir>/codex-auth.json`;
Pi helper/env syntax there remains relevant. Pi ModelRegistry headers, extensions,
default auth.json and runtime --api-key overrides are bundled behaviors, not
established MCode routes. Do not scan these in place of real MCode sources.
The file OAuth store has a different schema from Pi: namespaced
`auth/<buildEnv>/<region>/mcode-public/auth.json` plus auth-state.json. Root and
namespaced/legacy local-runtime.auth.json projections, identity/scope/fingerprint
files, auth-lease capability, config.yaml and plugin MCP credentials also need
their own coverage/classifiers; account-identity fingerprints are not raw tokens.
This parser does not cover them yet.

Claude reports file-only OAuth and no Pi extension loading for the published CLI;
those global reachability conclusions remain attributed static findings, pending
complete audited consumer closure. They do not establish Electron lease-server
internals, future package versions or actual session behavior. `PD` preserves
header strings; no blanket claim that all MCode header values are trimmed is made.
Managed-host authMode inference, forced managed preset rewrites and no-model
fallback must be represented before claiming an effective credential route.

Correction verification: four regression tests first failed, then 23 focused
tests passed. One fresh final Codex reviewer found no Critical/Important/Minor
issues; 23 focused tests and 20 additional synthetic checks passed. Full isolated
Ubuntu-24.04/Python 3.12 suite passed 827 tests in 206.671 seconds, actual exit 0,
with only loopback enabled. Frozen source archive SHA256
`81dc0b0355984f63555d8ea97f08291c3b22d675fa03c4a928c29fb84dcc5874`
matches final parser/test bytes; documentation alone follows. No fix pass or
rereview. These are offline source/fixture results only.
