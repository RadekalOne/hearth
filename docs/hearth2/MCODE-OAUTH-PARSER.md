# Inactive MCode OAuth file parsers

Pure parsers accept explicit acquired byte snapshots and return frozen summaries.
They do not open any file, read ambient environment, log in, refresh or revoke
tokens, resolve helpers, call providers, modify Mavis or emit inventory/start
authority. Source authenticity, complete enumeration, private filesystem custody,
freshness and independent collector-round binding remain acquisition gates.

`MCodeOAuthParser(version, oauth_bundle_sha256, projection_bundle_sha256)` requires
0.4.1 and the reviewed AAJMOWWM and 6BYKHQOV hashes. The published source functions
`J`, `Q`, `Z`, `me`, `de`, `Fe`, `k`, `readUsableCredential`, `xi`, `oc`, `ac` were
read as text. Identity parameters do not physically attest the installed package.

`store_json(auth_bytes, state_bytes, *, build_env, region, account, now_ms)` parses
file payload schemaVersion1 with zero or ONE exact independently expected
`com.minimax.mcode.oauth.<env>.<region>\0<account>` record. The account must be the
43-character base64url namespace digest supplied by independent enrollment, never
guessed from a caller-selected directory. Additional/foreign records refuse;
none are skipped. The bounded decoder permits only this exact control-character
key for this call; all other callers retain the original printable-key rule.

Credential record schemaVersion1 requires accessToken/refreshToken, Bearer,
mcode-public, agent-backend, exactly agent.default scope, a nonnegative safe-integer
expiry/generation and optional string subject/accountId/loginEpoch. State supports
schemaVersion2, file store, explicit matching buildEnv/region and the known native
status enum; optional expiry and authorizing-only authorization lease/progress
fields follow the published shape. Sensitive token fields/unknown fields refuse.
Legacy state1/os-keyring, missing namespace, extra scopes, unknown shapes, floats,
unsafe integers and unsupported schema versions refuse instead of partial success.
These strict supported subsets intentionally reject some native-permitted data.

With a credential, state generation and expiry must match. Without one, a state
claiming authenticated/refreshing/expired/scope_upgrade_required refuses. An
anonymous/error/authorizing/logout state with a retained matching record still
counts both tokens; it never becomes an absence report. Expiry at or before the
explicit now_ms counts expired, including if state still says authenticated.
Status alone does not determine actual provider authorization or token usability.

`projection_json(bytes, *, source_kind)` validates exact version1 writer shape
{version, updatedAtMs, auth:{accessToken, optional identity strings}}. source_kind
is one of namespaced/legacy/shared; that declaration does not authenticate its
path. Whitespace follows native xi trimming; empty effective tokens refuse.
Projection expiry/generation is UNKNOWN because those fields are absent.
Projection token trimming uses the explicit ECMAScript WhiteSpace plus
LineTerminator set, not Python's default strip: U+FEFF is removed; U+0085 and
U+001C are preserved. Primary stored tokens are never normalized. Empty effective
projections refuse after normalization. See the normative
[TrimString algorithm](https://tc39.es/ecma262/multipage/text-processing.html#sec-string.prototype.trim)
and [whitespace table](https://tc39.es/ecma262/multipage/ecmascript-language-lexical-grammar.html#sec-white-space).
`compare_projection(auth_bytes,state_bytes,projection_bytes, ...source_kind...)`
additionally returns matches_primary as a constant-time comparison of the stored
access token with the effective trimmed projection. False includes a projection
with no primary record. Equality never establishes login validity, freshness,
identity verification, namespace custody or a current usable token.

Results contain only fixed source/status/expiry labels, token/identity/authorization
field counts and an optional matches_primary boolean. No token, account/subject,
record key, token hash, identity value, lease/user code, URLs, generation or raw
timestamp is retained/output. Authorization fields can themselves carry sensitive
material and are counted separately; state is not blanket credentials:none.
All exceptions are fixed/redacted with no decoder exception context.

Each snapshot retains 65536-byte/depth8/2048-node/8192-string-byte/256-name limits.
Comparison parses at most three such snapshots. Missing bytes always refuse;
an empty parsed store is different from a missing source. There is no observe,
scan, complete, credential_entries, collector proof or driver wiring.

Remaining work: independently acquired/enrolled complete source inventory;
config.yaml/effective selection/managed rewrites; scope/shared projection and
account-identity metadata; legacy migrations/auth-lease IPC capability; plugin MCP
credentials; full native consumer closure, OS/native/provider acceptance. No
automatic discovery, enrollment, cleanup or credential changes are authorized.

Verification, 3 November 2026: 19 missing-feature tests first failed. Initial
19 OAuth plus 23 existing parser tests passed. One fresh final Codex review
passed 42 focused and 33 additional synthetic checks and found one Important
Unicode trimming mismatch, no Critical or Minor findings. Three regression
methods reproduced it (four failures plus one error), then explicit ECMAScript
trimming and unnormalized primary tokens passed 22 OAuth plus 23 existing tests.
The one TDD fix pass was verified by the full final suite: 849 tests passed in
144.990 seconds, actual exit 0, Ubuntu-24.04/Python 3.12, loopback-only namespace.
No rereview was performed. Final immutable source archive SHA256
`44f8dbe012661adae219536e36ebce741960992d8d47c36ef65d41e2c17e590d`
matches implementation/test bytes; only documentation follows. Earlier 846-test
source/result is pre-fix evidence, not the final gate. These are source/synthetic
tests, not physical inventory, native login/provider or runtime acceptance.
