# Concrete root lifecycle ports and composition (inactive)

`RootLifecycleDriver` implements the existing injected driver's create, inspect,
arm, inspect-armed, start and outside-termination interfaces. No factory, service
or CLI activates it. An independent trusted assembly observer is REQUIRED and
defaults to absent; without it the driver refuses before external mutation.
All verification uses private files/fake command and observation ports.

`NativeAssemblySpec` is a canonical private immutable artifact whose digest must
equal the existing native-container policy's native_profile_sha256. Version1
names an immutable image ID, absolute bootstrap entrypoint, bounded explicit argv
and1â€“8 absolute image policy-file paths with SHA256. It does not contain real
credentials, mounts or provider turns. Image ID must also match native policy.
The assembly specification is a declaration; independently observing its actual
image/installed runtime is mandatory. Hashes alone are not native-policy proof.

The observer's exact typed packet binds original host/run/creation epoch/policy,
nullable pre-create or actual immutable container ID, assembly digest, timestamp
and bounded references. Its required states mean: root host authenticated,
namespace verified, image native-profile files verified, bootstrap prompt gate
verified, no credentials or mounts, disabled egress, pinned dependencies and
installed guard runtime verified. Account/effective runtime-policy checks remain
required before any prompt. It must attest the exact spec's command/image and
policy application path, not translate a partial receipt or a model assertion
into those states. Its implementation/process identity/provenance is an OPEN
deployment gate; packet validation does not authenticate an arbitrary Python
observer or make its declarations physically true. No production observer exists.

Version1 still uses network-none/no-extra-mounts/user1000/memory-only policy.
Current mounted native fixtures and real provider/broker egress are unsupported.
They need explicit new policy artifacts/version and actual acceptance, not a
reinterpretation of an already-bound digest. Verified baked-image/bootstrap
configuration is pre-start evidence, not an assertion that a stopped native
process has already initialized or passed effective-policy/account checks.

`FixedLifecycleCommands` uses bounded fixed Docker and systemd-run executables.
Docker create targets the explicit local Unix socket, never pulls an image, sets
exact resource limits without float conversion, no restart/network/healthcheck,
read-only root/user1000/dropALL/no-new-privileges/private cgroup and IPC, no log
driver, original mapped cgroup parent, four identity labels and pinned bootstrap
entrypoint/image/argv. No caller environment, mounts, shell, attach or user-selected
daemon route is projected. Image defaults still require assembly attestation.
Start addresses only the sealed64-hex ID. No cleanup/remove/disarm command exists.

Arming uses one original absolute UTC calendar with the original guard unit,
explicit oneshot/User0/Group0/root working directory/system slice, matching fixed
timer settings and literal binding JSON. Systemd-run's default argument expansion
would alter dollar characters inside that JSON: `--expand-environment=no` is
mandatory and service readback now requires ONLY the `no-env-expand` ExecStartEx
flag. Privilege/ignore-failure/other flags still refuse. Source confirms trigger
creation uses StartTransientUnit mode fail, so existing units cannot be replaced
to extend a deadline. There is no monotonic relative timer or retry path.

`RootLaunchAttempts` adds private root durability to the DB's one-use intent.
Before each create/arm/start command it writes an exclusive0400 checksummed exact
context marker and fsyncs file+0700 owned directory. After create, a separate
known-ID receipt is durably recorded before returning the ID for DB binding.
Arm must match that receipt and a durable execution seal must precede arming.
Start requires the original arm marker and fresh full observations. Existing,
partial, corrupt or ambiguously acknowledged attempts refuse replay, including
after constructing a new driver/store. Files are never deleted on failure.
Capacity is bounded; no adoption/retry is inferred from a known created ID.

Driver inspections combine original stopped-configuration readback with REQUIRED
independent full assembly evidence; arming/start also require the original durable
seal, exact service configuration and original timer/deadline/invocation readback.
Only then can the trusted driver emit the existing full created/armed schema to
the controller. UID/original host/immutable context and60s wall/monotonic/future
original deadline fences are rechecked around each operation. The concrete driver preflights static configuration, independent assembly and
complete command count/UTF8 budgets BEFORE the controller commits one-use intent.
Legacy injected drivers without preflight retain existing behavior; begin still
revalidates the live exact claim after observations. Every concrete mutation also
validates its complete argument plan before writing an attempt marker. The global
transport remains40 arguments/32KiB;12 bootstrap arguments plus28 fixed Docker
arguments fit exactly. The controller
still commits guarded consumption and its DB live fence before calling start.
Root attempts prevent duplicate external operations after lost acknowledgments.
They do not make DB/OS calls atomic or guarantee daemon scheduling. Independent
expiry freeze/kill/immutable removal is still required to block delayed start.

Outside termination forwards only to an explicitly configured independent
collector after original-seal/host checks; it does not require current policy
repository availability. Strict RecoveryCoordinator retains current epoch/
generation fencing and decides any DB release/classification. No worker result,
automatic retry, orphan adoption or guard disarm follows from driver status.

Primary source contracts:

- [systemd255 run.c: fail mode and literal argv](https://raw.githubusercontent.com/systemd/systemd/v255/src/run/run.c)
- [systemd-run properties/calendar/expansion](https://www.freedesktop.org/software/systemd/man/255/systemd-run.html)
- [Docker create flags](https://docs.docker.com/reference/cli/docker/container/create/)

Actual root-host/UID namespace authentication, installed wrapper/dependency and
assembly collector, image defaults/effective native policy and scoped credential/
mount/egress, CLI/PID1/Docker/version compatibility, kernel timing/limits, observer
separation, orphan/reboot/backup inventory and composed native/OS acceptance stay
OPEN. No actual driver/worker/service activation or provider call. Default900s and
inactive full-run lease policy remain unchanged.

Verification, laptop1November2026:19 new lifecycle tests plus the literal-argument
service regression initially passed;135 broad focused checks PASS19.809s.
One fresh reviewer found one Important supported-contract defect:13–32 accepted
bootstrap arguments plus28 fixed Docker arguments exceed the existing40-argument
transport bound after consuming the create marker.147 distinct reviewer-focused
checks passed after correcting two reviewer module-name errors; five independent
edges and one full-path reproduction confirmed the defect. An additional inline
19-case execution was repeated evidence, not new cases.

One fix pass observed two regressions RED:13 arguments were accepted and missing
assembly configuration consumed a DB creation intent. It caps specs at12, factors
pure unchanged transport validation, validates complete plans before root markers,
and adds optional concrete-driver preflight before DB intent. The existing begin
live fence remains after preflight. Exact40-word valid and canonical UTF8 overflow
boundaries are also exercised. Final137 focused checks PASS19.877s. No rereview
is claimed. Historical pre-fix730PASS251.096s is not the corrected source gate.

Final Ubuntu-24.04 Python3.12 full suite:732PASS161.706s, actual exit0, immutable
`driver-fixed-review-source.tar.gz` SHA256
`14b69c47f97fb8ffc4d79f4bb6fdaeeba4a4fd588433a49ba8f823e0852cb544`.
All six changed executable/test files match that source byte-exact; docs alone
followed. Durable WSL source is
`/home/rslabinski/.local/share/hearth2-laptop-verification/driver-fixed-20261101/source`.
Existing isolated dependencies/HOME/official cache were reused; only loopback was
enabled in the full-test network namespace. Private archive, review, RED/focused
and `driver-fixed-full-python-offline.log` remain in the plan ledger. No actual
Docker/PID1/cgroup/service/worker/provider or global account/configuration change.
This proves injected offline composition, not installed collector/wrapper or OS/
native acceptance. Default observer remains absent, with no activation.
