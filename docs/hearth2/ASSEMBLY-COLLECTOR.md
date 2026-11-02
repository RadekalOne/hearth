# Independent assembly facts collector (inactive)

`RootAssemblyCollector` derives the lifecycle observer packet from separate
metadata, file-digest/stat, credential inventory and runtime/installation observations. It accepts no
caller-supplied assembly-state packet. Missing enrollment or any backend refuses.
It is not automatically wired to the driver. Physical file/credential/runtime backends and
trusted enrollment provenance are still deployment gates, not delivered OS proof.

`RootAssemblyAnchor` is an explicit frozen, deeply immutable trusted enrollment:
original host, boot ID, initial user/PID/mount/cgroup namespace inode fence,
approved assembly/bootstrap/guard executable/dependency-closure and credential-inventory-policy hashes and an
authority reference. It must come from authenticated root configuration outside
the worker/controller record; the collector never creates it from current host
values, a restored database or the policy artifact being tested. Boot/namespace
changes refuse, rather than selecting a new restore-host mapping. Expected hashes
express approval; they do not themselves prove execution or physical placement.

The runtime backend must freshly measure numeric UID/EUID0, original host and
boot/namespace fence, installed guard executable, bootstrap prompt-gate and
dependency closure. The collector also reads the original private guard artifact
and actual executable checksum through RootGuardArtifacts and matches enrollment.
The backend's own authentication, outside-host/root-namespace identity, process
separation and actual measurements need independent OS acceptance. A Python
dictionary cannot establish those facts. There is no default runtime backend.

The credential backend must freshly inventory the complete approved image rootfs,
configured environment and native credential consumers before create; for a
container it must additionally cover the stopped writable filesystem/config and
mount sources. Its exact packet binds image, nullable/actual ID, assembly digest
and independently enrolled inventory-policy hash. Required scope differs before
and after create. Completeness must be true, credential entries/unknown consumers/
unreadable sources/unscanned sources all zero; missing, cached, partial, unknown,
dirty, wrong-image/container/policy/scope inventories refuse in either round.
Safe configured Env, no mounts and a few file hashes NEVER imply credential
absence. The actual comprehensive scanner/consumer policy/provenance is still
unimplemented and defaults absent, rather than guessing that an image is clean.

The file backend must independently inspect the actual approved image filesystem
before create, or actual stopped-container filesystem for a container ID; return
the matching image/nullable container/path, computed SHA256, regular-file type,
root ownership, permissions, size and acquisition provenance. It may not copy
digests from image labels or the requested manifest. Bootstrap must appear in the
approved file set and match enrollment, be0555/at most8MiB; profile files are0444/
at most64KiB, nonempty/root-owned/regular. There is no default image/container
filesystem backend. Archive/symlink/layer/provenance semantics remain a separate
implementation/OS gate; no container is started to inspect files.

`DockerAssemblyMetadata` implements bounded fixed read-only local Docker image/
container inspect projections. It emits comparison booleans and counts for
environment and argv, never their values or full mount paths. Unknown fields
refuse before returning data. Each expected argument has its own bounded template,
so a valid12-argument Unicode specification does not overflow one format string.
Entrypoint/argument count and equality, immutable image/ID, Linux/amd64 image/user,
disabled healthcheck, no image volumes/onbuild, exact identity labels, original
stopped state, read-only/nonprivileged/network-none and zero extra mount/device/
network mapping counts must match. Other resource checks remain with the existing
stopped-configuration reader. Metadata is not kernel or effective-policy proof.

Allowed configured environment entries are exact PATH/LANG/LC_ALL/TZ/HOME/
PYTHONDONTWRITEBYTECODE constants. Unknown values, credential environment or more
than16 entries refuse; no secret values are emitted. Effective process environment
and native/account policy still require the bootstrap's gate BEFORE any prompt.
Network-none v1 is not provider/broker connectivity or mounted-profile acceptance.

Every independent acquisition must be stamped no earlier than its collection
round and no later than trusted now, with bounded provenance. Two complete rounds
must have identical measurement values; returned nested data is copied so a reused
backend dictionary cannot rewrite the first snapshot. UID/original host/context,
policy/approved assembly/boot/deadline and60s wall/monotonic bounds are rechecked.
Only all matching observations produce the exact driver observer schema. No
partial/hash-only/caller states, cleanup, adoption, restart or mutation is inferred.

Primary formatting contracts: [Docker formatting](https://docs.docker.com/engine/cli/formatting/)
and [Go text/template](https://pkg.go.dev/text/template). Actual installed CLI/
template/runtime/version behavior remains separate acceptance; no Go compiler
was available and none was installed. Tests use private fake runners/facts, not
real Docker/PID1/procfs/cgroups/workers/providers. Default file/credential/runtime backends and driver observer remain
absent; no wrapper/service activation. Default900s/full-run lease stays inactive.

Verification, laptop1November2026:14 missing-feature cases RED1.273s then
GREEN2.042s. Two additional negatives (mutable enrollment pairs/unrequested
metadata) RED0.254s before fixes; a reused nested-fact alias RED0.128s before
copying measurements. One test insertion briefly misplaced an older assertion
(NameError); the boundary was corrected, not treated as a product failure.
One fresh reviewer passed69 focused checks38.271s and6 private edges1.510s, finding
one Important missing credential-inventory observation and one Minor direct-test
importlib.util dependency. Missing inventory was independently RED0.135s; one fix
pass adds its required complete/fresh/scoped evidence, enrolled policy and refusal
cases. Explicit import fixes direct invocation. Final21 direct tests PASS3.026s
and123 broad focused checks PASS16.640s. No rereview is claimed. Historical
pre-fix750PASS254.865s is not the corrected gate.

Final Ubuntu-24.04 Python3.12 full suite:753PASS150.548s, actual exit0, immutable
`assembly-fixed-review-source.tar.gz` SHA256
`117654e2ac7b1421ea3685d9984fc35019dd509fede52d87f5b43e70ead93756`.
Both changed executable/test files match that source byte-exact; docs alone
followed. Durable WSL source is
`/home/rslabinski/.local/share/hearth2-laptop-verification/assembly-fixed-20261101/source`.
Existing isolated dependencies/HOME/official cache were reused; only loopback was
enabled in the full-test network namespace. Private archive, review, RED/focused
and `assembly-fixed-full-python-offline.log` remain in the plan ledger. No actual
Docker/procfs/cgroup/service/worker/provider/global account or credential change.
These are injected/source checks; actual backend/collector provenance and physical
OS/native acceptance remain open. No default driver observer or service activation.
