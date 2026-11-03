# Inactive MiniMax credential input syntax parser

This component classifies explicit acquired byte snapshots, not running Mavis or
her configuration. It is not the complete credential inventory backend and is
not wired to the collector or launcher. Empty counts never establish absence.

Supported source semantics are pinned to public `@minimax-ai/code` 0.4.1 core
`chunk-ORVAHBJL.js`, SHA256
`ab278b848d10c3b8721fc00f76512994f39db9eba6691492b74c2135afa2703b`.
Static source was read locally; no client/JS/helper was executed. `getApiKey`,
`BC`, `mZe`, `Tfe`, `u$` and `getApiKeyAndHeaders` define the relevant branches.
Version/hash parameters express the parser contract, not physical attestation.

`MiniMaxConsumerParser(version, core_bundle_sha256)` accepts exact reviewed
identity. `auth_json(bytes)` scans ALL provider entries, not just the selected
provider. Exact `{type:api_key,key:string}` records classify key syntax; OAuth,
unknown/missing types and extra fields count as unknown records. Their semantics
remain unresolved, even if another key would override them at runtime.
`headers_json(bytes)` classifies a single independently acquired provider OR model
header string map. Both layers must be inventoried; the caller cannot supply only
the final merged map and claim all sources covered. `runtime_overrides_json` and
`environment_json` classify ALL supplied strings as literal inputs, without
performing expression expansion. The latter is a snapshot parser, not discovery
of provider environment names, ambient process environment or consumer coverage.

For stored API keys/headers only, a leading `!` denotes a command route and is
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
credentials. No precedence is inferred from these syntax counts. BYOK YAML path
and merge semantics, OAuth refresh/provider closure, fallback resolver, external
keychain and extension consumers remain unsupported/unresolved.

Next work must bind independently acquired snapshots and full audited native
consumer manifests/parser closure to the original image/CID/assembly/scan policy,
cover environment/config/mount sources in both fresh collector rounds, and refuse
missing or unknown sources. No physical source/root/namespace/provenance,
credential completeness, native runtime or production acceptance is established.

Verification on 3 November 2026: 14 missing-feature tests first failed; 17 focused
tests then passed. One fresh final Codex review found no Critical/Important/Minor
issues and passed 17 focused plus 13 additional boundary/redaction checks. Full
isolated Ubuntu-24.04/Python 3.12 suite passed 821 tests in 288.517 seconds,
actual exit 0, with only loopback enabled. Immutable source archive SHA256
`4b7a1798067fc2ce072cc1eb88a1ef24fe33f4272d410cc29c916577c53b1974`
matches parser/test bytes exactly; only documentation follows. No fix pass or
rereview was needed. These are offline source/fixture results, not native, OS,
physical provenance or complete credential-inventory acceptance.
