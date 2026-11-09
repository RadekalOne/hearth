# Declared source-map/enrollment increment

The pure `DataDirectoryPolicy` and `MCodeSourceMap` implement the next bounded
increment after the public 0.4.1 source audit. They do not complete acquisition
plan Tasks 1–4, authenticate an enrollment authority, or load a live policy.

The policy binds the original image/container/assembly/base-audit context,
helper/parser closure digests, authority reference, explicit configured-source
slots, 1–8 declared roots and separate discovery/batch/work limits. No values
come from ambient environment, argv, HOME, native execution or filesystem reads.
Every configured-source slot requires an opaque identity and independently
supplied expected digest. No default live policy or missing batch window exists.

Each root declares a canonical absolute POSIX target path, mount, parent identity,
root device/inode/ctime or an explicit absent slot, source owner and explicit
environment/region/account contexts. These are requirements to check later, not
observed facts. Ancestor chains, actual host/namespace identity, source freshness
and authenticated configured-source provenance remain future acquisition gates.
Root owner 1000 does not become helper UID 0. The later helper must independently
check its real effective UID and all enrolled identity facts.

Encoding is bounded canonical JSON; decoding requires a separate expected digest.
Every root-slice request revalidates the full policy and original context before
returning one root plus necessary closure pins/limits. It excludes other roots
and configured-source slots. The slice's content binding detects changed fields;
it is not a signature or independent authenticated enrollment.

The fixed map includes the audit's six source pins, 14 file role spellings and
three non-file obligations. Shared/root roles appear once, environment roles once
per declared environment and namespace roles once per declared environment/region.
Empty namespace declarations do not default to prod/en. All returned roles remain
**unscanned**, with acquisition support disabled. The preexisting four-role
conditional adapter is unchanged and is not wired to this broader map.

The account check compares the audited POSIX auth-home derivation with a separately
declared account; it never fills one in. Missing or different accounts fail the
match. Windows native path semantics are outside this POSIX contract.

Exact native temporary/lock name/type recognition is descriptive only. It cannot
ignore entries, establish absence, descend lock directories or waive stable
two-pass metadata, identity, race and work checks. Lease sockets remain unsupported
objects. Unsupported parser/acquisition roles remain unsupported even when their
file spelling is known.

Narrow choices: canonical printable ASCII paths without spaces, nested/duplicate
or case-colliding roots refused, document <64 KiB and root slice <16 KiB, logical
source count strictly below its declared cap. Legitimate unusual roots must be
handled by a later explicit contract revision, never silently normalized.

Verification: synthetic contract tests, existing data-directory regression tests,
one fresh read-only review and isolated full-suite execution. No real credentials,
native clients, providers, services, production policies or automations are used.
The 900-second/full-run runtime policy remains inactive.
