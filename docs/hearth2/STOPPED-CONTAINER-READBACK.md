# Stopped container configuration readback (inactive)

This component observes selected original-container configuration and resources.
It neither creates nor starts a container. Its `container_config_state` result
cannot satisfy the launcher's full stopped-creation proof or armed consumption.
Guard, service and layout evidence likewise remain partial.

`NativeContainerPolicy` validates canonical private content-addressed JSON pinned
by the original layout's `native_policy_sha256`. The repository is EUID-owned0700;
files are0400 regular/no-follow, checksum-verified and bounded64KiB. The frozen
Python value also verifies its digest on construction. Version1 requires kind
`hearth2-memory-only-container-v1`, immutable `sha256:` image ID, full native-profile
hash, user1000:1000, exactly memory_search/memory_get tools, network none, explicit
64MiB–16GiB memory,0.1–4 CPU in integer nanocpus, and16–512 processes. These are
inactive policy-schema bounds, not changed defaults or deployed resource budgets.
Native profile hash/tool declarations do not prove the profile is applied.

Version1 intentionally supports no extra mounts, tmpfs, volumes, device grants,
links, extra host mappings or published ports. Earlier native fixtures use bound
profiles/executables and tmpfs: they cannot satisfy this narrower version. A later
assembly/egress policy needs its own explicit version/artifact and actual acceptance;
an old binding must never be silently reinterpreted. Network-none evidence is not
provider/broker connectivity or egress-allowlist acceptance.

`DockerStoppedContainerProperties` uses the existing bounded fixed Docker command
runner and explicit local Unix socket, requesting only a selected inspect format.
It excludes environment, argv/entrypoint/command, arbitrary labels, full mount/bind
paths, errors and health logs. Extra mount/device/network mapping collections are
represented only by counts. Exact four Hearth identity labels, image ID, configured
user, selected HostConfig/State and counts are checked. Unknown projection fields,
duplicate JSON keys, invalid ID and boolean count coercion refuse.

The readback accepts the original pre-bind intent plus returned immutable ID, or
an already sealed binding whose ID must match. It resolves only the original
layout/host and preserves logical parent, guard and creation epoch. Docker parent
must equal the explicit mapped daemon parent, including the absolute direct path.
Both state observations must be created, PID0, nonrunning/nonpaused/nonrestarting/
nondead, with zero start/finish history; raw ExitCode0 is never a successful exit.

Selected expected settings: memory and total-memory-plus-swap equal the original
limit, exact nanocpus/PID limit, read-only root, no privileged mode or added caps,
dropALL, no-new-privileges:true, private cgroup/IPC namespaces, no host PID/UTS/
user namespace override, no restart and no auto-removal. Optional empty CapAdd is
explicitly accepted as null or []; other unknown values are not defaulted to safe.
Canonical JSON comparisons preserve bool/int/float distinctions. Configuration
readback is not actual kernel enforcement, cgroup placement, effective seccomp,
rootless/namespace mapping or full execution-policy attestation.

Native policy files and Docker projections are read twice; both observations must
match, the original context must remain unchanged, and host/deadline are checked
again. Collection is bounded by60s wall and monotonic time and must finish strictly
before the original deadline. This is neither an atomic daemon snapshot nor a
promise against later configuration mutation. No cleanup, removal, disarm, retry
or recovery classification is performed.

Primary contracts checked from Moby28 source and Docker documentation:

- [Container state and image response](https://raw.githubusercontent.com/moby/moby/v28.0.0/api/types/container/container.go)
- [Configured user and labels](https://raw.githubusercontent.com/moby/moby/v28.0.0/api/types/container/config.go)
- [Host configuration/resource types](https://raw.githubusercontent.com/moby/moby/v28.0.0/api/types/container/hostconfig.go)
- [Memory/swap and CPU semantics](https://docs.docker.com/engine/containers/resource_constraints/)

Actual installed Docker/Go-format/version support, trusted root-host/repository/
mount authenticity, applied native profile and scoped credentials, command/image
dependency closure, effective OS limits, mounted-profile/egress assembly, concrete
create/arm/start and independent observer/orphan/reboot/old-backup/native acceptance
remain open. No actual Docker/cgroup/service/worker/provider operation occurs in
verification. Default900s/full-run policy stays inactive.

Verification, laptop1November2026:14 missing-feature tests RED1.783s then
GREEN2.610s;116 focused implementer checks PASS24.563s. One fresh review found no
Critical/Important/Minor issues:82 focused cases PASS10.090s on the other Ubuntu
distro on this same laptop;7 independent edge cases PASS6.904s on Ubuntu-24.04.
Both host and exact code/test hashes were independently matched. The first distro
emitted a nonfatal user-session warning; no runtime configuration was changed.
No fix pass/rereview was needed. Review covers this component and integration,
not an exhaustive reaudit of older components or actual OS acceptance.

Final full Ubuntu-24.04 Python3.12 suite:694PASS269.502s, actual exit0, immutable
`container-review-source.tar.gz` SHA256
`d5e78ab1fa0841323582ddc16a1b13020c09a2ffe3b75894fe30429e052c8d75`.
Both changed code/test files match that source byte-exact; documentation alone
followed. Durable WSL source is
`/home/rslabinski/.local/share/hearth2-laptop-verification/container-20261101/source`.
Existing isolated project dependencies/HOME/official cache were reused; only
loopback was enabled in the full-test network namespace. Archive, review, RED/
focused and `container-full-python-offline.log` evidence remain in the private
plan ledger. No actual daemon, cgroup, worker/provider, service, global account/
configuration or credential change. This is partial offline configuration evidence.
