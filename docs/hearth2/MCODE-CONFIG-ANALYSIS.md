# Inactive conditional MCode configuration analysis

This pure source-analysis component parses explicit config.yaml bytes and evaluates
a declared selection hypothesis. Results are conditional fixed labels/counts;
they do not attest the actual resolver, host, source completeness, authenticated
account, delivered HTTP credential or worker/start authority. Physical source
acquisition and runtime context enrollment remain outside this component.

The reviewed target is MiniMax Code CLI 0.4.1, with exact 6BYKHQOV/OFHDMZSQ/
GOLYEPEW bundle identities. `SelectionHypothesis` requires explicit OD or MI,
region, ordered preset and API model catalogs, managed-runtime/bearer declarations,
selection source, catalog/availability/remapping gates and a reference. These are
analysis inputs, not proofs. Missing/unknown context refuses. Only prod build
context is supported; test-build end-to-end behavior remains unverified. No
runtime is selected implicitly from the conversation controller's default.
Runtime-default hypotheses cannot enable requireCatalog or custom-prefix fallback,
which the reviewed SVr source does not set. The preset default model is explicit;
references must contain meaningful text.

`MCodeConfigParser.analyze(config_bytes, context, model_ref_json=None)` supports
the credential-relevant provider/custom_provider/minimax_api/minimaxModelSource/
defaultModel/beta fields, with strictly reviewed nested option/model fields.
Unknown sections/fields, nonboolean enabled flags, legacy minimax-legacy provider
remapping and unsupported URLs refuse. Config default selection and explicit host
ModelRef are separate sources; ModelRef may carry base_url/api_key overrides.
This is a supported subset, not full native configuration compatibility.
Under managed runtime, raw plain-provider entries with nonempty key/baseURL and
a models object are eligible for native `$r` file migration. Such entries refuse
even when unused: migration can change namespace, headers and default selection
and depends on filesystem success. Claude's H2 plain-provider vector cannot be
treated as an established post-load route from these raw config bytes.

PyYAML 6.0.3 is used ONLY as a bounded event parser, never load/constructors. YAML
aliases, anchors, explicit tags, merge keys, duplicate keys and multiple documents
refuse. A conservative YAML1.2 scalar subset preserves quoted strings and plain
on/off/yes/no strings; null, true/false and safe decimal integers are explicit.
Ambiguous numeric/date/float/octal/hex forms must be quoted or refuse. Input limits
are 65536 bytes, depth8, 2048 nodes including keys, 8192 UTF-8 bytes per scalar,
256 ASCII printable bytes per mapping name. JSON ModelRef shares existing limits.
All errors are fixed and suppress parser exception contexts; no values/names,
tokens, credential hashes, raw references, URLs or model/provider IDs are output.

Production managed rewriting follows Vr: managed runtime fixes minimax authMode
and baseURL; user apiKey resets only for an originally non-managed baseURL and can
otherwise survive alongside bearer. Nonempty user model maps replace preset
maps. Empty maps retain the preset. Raw credential/header fields are counted
before rewrites or reserved provider removal, including unused/disabled entries.
Vr's key-reset condition uses the original nonempty baseURL string, including a
whitespace-only value; this condition is not trimmed. A preset-generated dummy
key is labeled separately from a stored user key.

Stage-A catalog checking and availability are distinct inputs. Remapping a bare
custom key requires its explicit source flag and the requested prefixed model;
provider existence alone is insufficient. Provider-level and model-level disabled
remain distinct. OD may fall back on a missing/disabled
BYOK plan; MI returns an error. Missing minimax_api with minimaxModelSource API
also differs. A present but empty key produces an error, never fallback. Fallback
uses declared ordered models, with minimax preferred; no catalog is guessed.

Keys in config are literal and use explicit ECMAScript trimming. Headers are
literal; plain provider merging is case-sensitive and custom provider merging is
case-insensitive. Header case collisions and multiple credential inputs are
flagged as unresolved HTTP auth. Recognized competing headers include Authorization,
Proxy-Authorization, x-api-key, api-key, x-goog-api-key and Cookie. False flags do
not establish physical HTTP precedence or credential absence; arbitrary custom
header consumer closure remains outside this analysis.
Selected Pi/OAuth getters remain unresolved. This module never executes helper/ENV lookup or refreshes credentials. A future
activation gate must independently establish all effective account/auth behavior.

Canonical ASCII HTTPS URLs only: no userinfo/query/fragment/IDNA/IPv6/scheme-less
forms or nondefault ports. Mixed ASCII host case and explicit443 are supported by
explicit parsing; no general WHATWG URL compatibility is claimed. The known
managed origins are the three reviewed agent hosts. Unknown authMode refuses
rather than emulating the native warning/fallback.
Non-ASCII URL margins also refuse instead of guessing WHATWG vs ECMAScript
trimming differences. Source identities are exact full 64-character hashes.

The pinned [PyYAML event API](https://github.com/yaml/pyyaml/blob/6.0.3/lib/yaml/__init__.py)
is used for syntax events; construction/type semantics are intentionally narrower
than the [native YAML loader](https://github.com/nodeca/js-yaml).

Claude's 37 labeled cases are reference vectors, not established runtime facts.
Supported ordinary/conditional cases become synthetic regressions; ambiguity and
unsupported cases remain refusals/unresolved outcomes. Eight runtime/host/HTTP
questions remain open. There is no complete inventory schema, observe/scan port,
filesystem discovery, environment read, controller/driver wiring or activation.

Verification, 4 November 2026: 26 missing-feature tests first failed; 30 initial
focused tests passed after source-derived refinements. One fresh final Codex
review found five Important issues, no Critical/Minor: incorrect OD identity,
missing-model remapping, raw whitespace reset semantics, competing auth headers,
and migration-eligible raw inputs. Six regression methods first reproduced them
(21 failures plus one error); the single TDD fix pass then passed 36 focused tests.
All three public bundle digests were independently recomputed and matched.

The final full Ubuntu-24.04/Python 3.12 suite passed 885 tests in 144.222 seconds,
actual exit 0, with only loopback enabled. Final immutable source archive SHA256
`77d16407f100c994d1aed097416e675760afbdb517aca693ecb548a1da681701`
matches code/requirements/test bytes; documentation alone follows. No rereview.
The earlier 879-test result/archive is pre-fix historical evidence. This is
offline conditional analysis, not physical context, complete inventory, real
provider/account, native OS or production acceptance.
