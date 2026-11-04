# Claude MiniMax parser review disposition

Baseline `5eaf9a9`, independent Claude source review supplied 4 November 2026.
Source anchors independently checked in public0.4.1 bundles: Gt catches loader
errors to {}; ru writes logLevel plus full preset; me aliases jt; native OAuth
readUsableCredential gates on generation and checks required credential scopes.
No real configuration/credentials, native execution or provider calls were used.

Unknown records already prevent any future successful inventory; the existing
parsers have no inventory/activation port. Coverage gaps still deserve explicit
material counts and unresolved labels. Compatibility refusal alone is not proof
that the native client refuses or makes no request.

| Review item | Decision and scope |
|---|---|
| A1 | Count known Pi access/refresh material; exact supported OAuth records classified, unfamiliar shapes retain unknown_records. No refresh/provider execution. |
| A2 | Central known-artifacts table below, with honest parsed/count-only/unparsed status. This is a requirements catalog, not actual discovery or absence evidence. |
| B1 | Generation mismatch still refuses; record/state expiry difference reported explicitly, with expiry computed from the record. No token-usability claim. |
| B2 | Parse bounded string scopes, count extras/missing required scope and state divergence. Neither extra nor missing scope is silently treated as a usable account. |
| B3/B4/B5 | Keep authorizing-only authorization fields, unknown projection-field refusal, and legacy state/keyring refusal as explicit supported-subset limits. |
| C1 | Preserve parser refusal. Native Gt can replace YAML/load failures with {}, then proceed with managed defaults. RecordError must mean unresolved/blocked Hearth analysis, never native abort/no route/no credential. No synthetic empty-success inventory. |
| C2/C3 | Preserve ambiguous number and null-model refusal; native can parse/ignore them or fall back. Document the compatibility cost. |
| D1 | Bind every returned selection to fixed resolver and a canonical context-only fingerprint; exclude reference text and all secret-bearing source bytes. This is not provenance or runtime attestation. |
| D2 | Require the declared API and preset builtin catalogs to match the reviewed me=jt alias. User effective-model overrides remain distinct. |
| D3/E2/E3 | Document inert config override key, free-text label with zero evidentiary weight, and MI controller default with injectable alternative. |
| E1 | Use managed-bearer-assumed, mixed-assumed and pi-auth-unparsed labels rather than imply observed account auth. |
| F1 | Support leading-digit IDs, while matching JS integer-index-first property ordering. A regex-only relaxation would be insufficient for fallback. |
| F2/F3 | Accept bounded unparsed branches as explicit counters; force outcome/route/source unresolved and no computed header result. Never strip unknown fields to fabricate coverage. Known malformed credential fields still refuse. |
| F4/F5/F6 | Preserve nonstring headers/nonboolean enabled, nondefault ports, and unknown minimaxModelSource refusal. Document native filtering/defaults and explicit regression refusal. |

## Known source artifacts and current coverage

All locations are relative to independently established dataDir/buildEnv/region.
“Parsed” means supplied byte syntax only: no filesystem custody, namespace
selection, freshness, source completeness or effective credential is established.

| Artifact/source | Current support | Remaining obligation |
|---|---|---|
| codex-auth.json | API-key expressions and bounded Pi OAuth material counts; unknown shapes remain unknown | Provider closure, environment fallthrough, refresh and actual selected consumer |
| auth/env/region/mcode-public/auth.json + auth-state.json | Supported file/schema pair and explicit mismatch/scope metadata | Independent namespace/custody/fresh acquisition; legacy/unsupported fields remain refused |
| cli-auth/env/region/local-runtime.auth.json | Version1 projection syntax/token comparison only | Selector/custody/freshness evidence |
| cli-auth/env/local-runtime.auth.json | Same legacy projection shape only | Migration and scope-selection evidence |
| local-runtime.auth.json | Same shared projection shape only | Shared selector/fingerprint evidence |
| run/mcode-auth-lease-v1.cap | Unparsed bearer-like IPC capability | Presence/material acquisition and lease-server consumer closure |
| cli-auth/env/region/account-identity.json | Unparsed linkable token fingerprint/identity metadata | Count material without exposing fingerprint/identity; validate selector semantics |
| cli-auth/shared-projection.json | Unparsed fingerprint selector | Bind actual selected shared projection |
| cli-auth/env/region/cli-auth.scope.json and legacy scope marker | Unparsed namespace selector | Establish scope before interpreting projection kind |
| preferences/mcode-region.json | Unparsed namespace selector | Establish region with environment/native precedence |
| auth/credentials.enc | Unparsed encrypted legacy material | Independent presence/absence and migration inventory; never infer empty from unreadability |
| config.yaml | Bounded supported source fields; unparsed branches explicitly unresolved | Full schema/consumer coverage, migrations, actual resolver/source context |
| host agentConfig.model | Known credential/selection fields; unparsed metadata explicitly unresolved | Actual host provenance, context/source gates and full field semantics |
| plugin.json / mcp.json env, headers, URLs | Unparsed MCP credential consumers | Plugin acquisition/consumer closure; no broad credentials copied into workers |
| Explicit environment snapshot | Counts all supplied string values; no semantic discovery | Complete acquisition and name-specific consumers below |

Environment obligations include MCODE_PROVIDER_API_KEY / --api-key-env during
provider-add persistence, MAVIS_ACCESS_TOKEN for content review,
MCODE_OAUTH_DEVICE_AUTHORIZATION_ENDPOINT / TOKEN_ENDPOINT / REVOCATION_ENDPOINT
which choose token destinations, MINIMAX_DATA_DIR/MAVIS_DATA_DIR, MAVIS_REGION,
MAVIS_BUILD_ENV and reachable Pi provider-map variables. Names here are a source
map, not an exhaustive or scanned environment declaration.

Every unparsed artifact/branch, missing or unreadable source must remain unknown
or unscanned in future inventory. Zero known-token counts never mean clean when
any of these gates is open. The complete scanner, independent enrollment,
runtime/account/HTTP/OS acceptance and activation remain unimplemented/gated.

## Verification

97 focused synthetic parser tests passed. The final immutable snapshot passed all 901 offline Ubuntu-24.04/Python3.12 tests in 188.251s (exit0), with external networking disabled and only loopback enabled. Source archive SHA256: `2ee6d5c8ac960046648def2ae02ac2048f6d4ca3cfde9717c54ecbc2ce3d4c5b`. All tracked Hearth2 code/test bytes match that archive; only documentation changed afterward. Claude supplied the independent review; this is its single TDD fix pass, not a new approval of the resulting commit. No real credential, native-client, provider or OS acceptance is established.
