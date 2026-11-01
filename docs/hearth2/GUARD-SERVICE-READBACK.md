# Guard service configuration readback (inactive)

This SERVICE-ONLY component checks the configured guard identity and exact sealed
command against original immutable policy artifacts. It executes nothing. Its
`service_state` result cannot satisfy `consume_armed` or authorize a launch.

`RootGuardArtifacts` reads the original layout's `guard_sha256` and
`native_policy_sha256` files from an EUID-owned0700 repository. Files must be
0400 regular/no-follow, bounded64KiB, checksum-valid canonical JSON objects with
no credential fields. Native policy is checksum-pinned only: applying it inside
a native worker is a separate gate. The exact guard descriptor has version1,
ABI `hearth2-root-guard-v1`, absolute executable path and executable SHA256.
The executable must be EUID-owned0500 regular/no-follow, nonempty and at most8MiB;
hashing is bounded. Production requires UID0 and trusted ancestors/provisioning;
tests intentionally use private files under the test EUID.

The future guard ABI is an expectation, not an installed executable: its argv is
`[executable, "--binding-json", canonical_full_original_binding]`. This includes
the original host, container, guard, parent, creation epoch and deadline without
introducing a cyclic layout/guard digest. No worker credentials are included.
Executable hashing does not prove interpreter/dependency closure, namespace
mapping, absence of later replacement, or actual execution by PID1.

`SystemdGuardServiceProperties` uses the existing bounded fixed busctl runner.
It issues only `GetUnit` (existing units) and selected typed property reads, never
`LoadUnit`, start/stop or arming. It never queries Environment or credentials.
ExecStartEx is `a(sasasttttuii)`: path, argv, flags, four execution timestamps,
PID, code and status. Requiring no flags catches executable-prefix overrides.
Extra condition/pre/post/reload/stop commands are refused. The expected command
must have no execution history. The unit must be loaded/transient/inactive/dead,
with no invocation identity or main PID and a successful untouched result.

Selected configuration requires explicit numeric User/Group `0`, DynamicUser
false, Type oneshot, Restart no, RemainAfterExit false, WorkingDirectory `/`,
empty RootDirectory/RootImage and guard Slice `system.slice` outside the retained
workload parent. Numeric root configuration is not an observation of runtime UID.
Other execution namespace/mount/credential/sandbox settings and dependency
closure are not fully attested. These omissions remain activation gates.

Both properties and artifacts are read twice, checked against the original
binding/policy/host, and required to remain stable within60s wall/monotonic bounds
and strictly before the original deadline. The binding itself cannot change
during collection. Evidence is scoped to those observations, not a promise of
future service immutability or an atomic PID1 snapshot.

Primary protocol sources checked for systemd255:

- [Service properties](https://raw.githubusercontent.com/systemd/systemd/v255/src/core/dbus-service.c)
- [Execution context properties](https://raw.githubusercontent.com/systemd/systemd/v255/src/core/dbus-execute.c)
- [ExecStartEx signature](https://raw.githubusercontent.com/systemd/systemd/v255/src/core/dbus-execute.h)

Actual installed CLI/version support, root-host authentication, mount/layout,
runtime UID, service execution and native-policy enforcement, stopped-container
resource verification, concrete create/arm/start and independent observer/OS/
reboot/orphan/old-backup/native acceptance remain open. Timer-only and layout-only
proofs also remain partial. Default900s/full-run policy is inactive. Verification
uses only private files/injected ports; no bus/daemon/cgroup/service/worker calls.

Verification, laptop1November2026:12 missing-feature cases observed RED1.363s.
An initial expiry test assumed901s; it was corrected to the actual sealed deadline
without changing policy. Final component has15 cases. Implementer104 focused
checks PASS27.070s, then final15 component checks PASS2.285s after coverage fixes.
One fresh reviewer found no Critical/Important issues and one Minor masked
boolean-history assertion;102 reviewer-focused checks and five ephemeral edges
passed. An error-specific assertion reproduced the masking RED before moving it
to a clean fixture. Root closeout inspection similarly found the ABI test masked
by policy mismatch: an error-specific assertion reproduced RED before checking
the artifact reader directly. These are test-coverage corrections; the production
validator was unchanged and independently rejected booleans. No rereview is
claimed. Repeated executions are not additional distinct test cases.

Final Python3.12 full suite:680PASS142.898s, actual exit0, immutable
`service-final-review-source.tar.gz` SHA256
`e1d857f6780d4d9b3108795da8ae28c465db4b63eca9fbc741890641e9de0f62`.
All three changed executable/test files match that snapshot byte-exact;
documentation alone followed. Durable WSL source is
`/home/rslabinski/.local/share/hearth2-laptop-verification/service-final-20261101/source`.
Existing isolated dependencies/HOME/official embedding cache were reused; only
loopback was enabled in the test network namespace. Private archive, fresh review,
RED/focused and `service-final-full-python-offline.log` evidence remain in the plan
ledger. Historical680 runs (412bd9eb...272.560s; b5024cea...157.968s) preceded the
final test-coverage corrections and are not the final gate. No actual daemon,
service, cgroup, worker/provider, global account/configuration or credential changes.
