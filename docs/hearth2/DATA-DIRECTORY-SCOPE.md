# Conditional immutable directory scope

`DirectoryScopePolicy.create(view, requirements, manifest, max_entries=...,
max_bytes=..., timeout_seconds=...)` is a pure, single-root scope contract for
the existing synthetic acquisition/accounting adapter. `ScopedDirectoryCapture`
requires that policy AND a separately supplied expected SHA256. Its default
configuration refuses. No installed policy repository or trusted enrollment
authority supplies that pin yet: caller declarations/hashes are not physical
host authentication or credential-absence proof.

The canonical private policy seals original image/container/assembly/audit
context, root ID/path/mount/device/inode/ctime/owner/group, the complete source
manifest including account/selection hypotheses and parser closure requirements,
the conditional source map, group membership, coverage work limits and explicit
acquisition limits. Supplied source owner is preserved, not normalized to root.
The source-map version remains `conditional-mcode-four-role-v1`: Pi auth, root
config and explicitly namespaced OAuth store/state only. No new native path
semantics or production source-map audit is claimed.

Batch and round IDs are deliberately excluded from the persistent root-policy
digest. A new request must have valid equal scope on its view and requirements,
but can use a new batch/round ID without changing the root policy. Actual source
bytes are never part of that policy: every invocation reacquires them twice.
Changed root identity, scope, parser/account metadata, path map or budget must
have a new explicit expected pin. Self-rehashing a replacement does not satisfy
an old pin. No methods derive or automatically enroll current filesystem facts.

Construction performs no filesystem opens/discovery or clock calls. Execution
first checks exact immutable types, nested schema, digest, expected pin and full
canonical request equality, then uses the existing descriptor-relative reader.
All mismatches refuse before opening the root. The policy rejects noncanonical
absolute paths, including `.`/`..`, repeated/trailing slashes, backslashes,
control/non-ASCII/space characters, and `/` itself. This stricter entrypoint
does not alter the separately callable older lower-level readers; their prior
canonical-root limitation remains a pre-production integration gate.

Explicit entry/byte/time budgets cannot exceed the existing adapter/audit caps;
bool/float/string values are refused. Policy document size is strictly less than
32768 bytes, with a closed version/kind and fixed map version. Policy repr and
refusal text reveal no path/document/hash. The protected policy object itself
contains declared private paths/metadata and is not a public serialization API.
Returned results remain the existing fixed-count/enum/ordinal summaries, with
ALL physical families unresolved and no complete/observe/start authority.

This completes another lower-level conditional part of Task1, not the full
`DataDirectoryPolicy.load`, `RootEnrollment`, `MCodeSourceMap`, universe,
discovery or root-round contract. Independent host/boot/namespaces, audited native
map, authenticated root/policy provenance, helper/parser closure enrollment,
source custody, per-root process isolation and outside hard deadline/reap are
still absent. A matching metadata pin and two file reads establish none of
those facts. No live Mavis directories/config/credentials, native clients,
providers, workers, services or permissions are involved.

Tests use only private fake files and supplied identities. They verify pure
construction, real adapter consumption, changed-input rejection before IO,
fresh-round reuse, repeated actual content acquisition, redacted output,
strict canonical paths and lower policy budgets. One adversarial nested-scope
test first reproduced caller equality executing before type validation; fixed
by validating nested scope before comparing it. Full verification follows.

Verification6November2026:19newscope tests;83totaldata-directory and80credential
tests PASS. Single fresh review found no newCritical/Important/Minor; reviewer
independently83PASS0.370s exit0. FullUbuntu24.04/Python3.12 suite1056PASS188.439s,
actualexit0, externalnetworkdisabled/loopbackonly. Immutable archive SHA256
`c6da0c817e959cc03bf0f2973696b72695924d6e49b36c52ae4b245f18e6c9b3`;
all94trackedHearth2Python/testfiles byte-exact. Docs-only closeout followed the
run. Physical/native/production acceptance and fullplanTasks1-4 remain open.
