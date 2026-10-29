# Piece 2 runtime containment spike — 29 October 2026

Status: OS primitives exercised with fixtures; native integration remains unproven.
No native model prompt, account change, service reconfiguration or pin change.
This does not verify piece 2 or A4/A6–A9/N2/N3.

## Reviewed foundation

PR #36 at `271e1bdf8501cf5947a62360bb3f11150725ffb4` has Claude's
component PASS (`$sYdx6PZZNMUZdoVJDTAiS7RKllQdvs-c5qDov1KvLF0`) and
CI 97 / run `40920099176` success. The later unattended wake reported no
ability to inspect; it did not identify a new defect or retract the earlier
specific source inspection. Neither event claims an independently rerun test.
The PASS applies to that component and commit, not this later spike.

## Pinned-source constraints

Read source on trial `srv2065995`, Cloudroom 0.1.58, commit
`3949daaea3c7613458e9ad14afddbd267a0a56bc`:

- `src/runtime/codex.rs:15-19` uses the configured binary to start the
  app-server. The thread start request at line 73 hard-codes `approvalPolicy`
  `never` and sandbox `danger-full-access`; turn start at line 226 repeats it.
- `src/runtime/claude.rs:47-98` invokes the configured binary with skipped
  permissions and a managed Cloudroom MCP server. A static prompt and the
  partial disallowed-tool list are not our role-specific enforcement boundary.
- `src/runtime/mod.rs:977-1002` clears inherited environment, then adds saved
  user environment, PATH and HOME. A launcher must apply its own explicit
  environment allowlist and must not mount the existing account home.
- `src/runtime/claude.rs:127-151` passes either a provider API key or a native
  subscription OAuth token to the CLI. This code read examined no actual token.
- `src/runtime/linux.rs:310-350` attaches the workload before dropping identity.
  This supports inherited process containment, including a child using setsid;
  it is not a filesystem or network namespace.

The live service runs as `cloudroom` (UID 999), delegates its cgroup subtree,
and uses control-group termination. The separate worker is UID 1000. Docker is
available only to the trusted host side; do not give its socket to the worker.

## Reproducible fixture evidence

Opt-in script: `test/fixtures/hearth2_containment_probe.py`. It refuses to run
unless explicitly opted in as root on exact host `srv2065995`. It starts no
Cloudroom/native process, has no provider credentials and calls no model.

1. Expected-failure control: `--mode parent`. A fixture starts a child that
   uses setsid and ignores SIGTERM. Killing the parent leaves its cgroup
   populated. The check returns exit 1, `process_check_passed=false`. Cleanup
   then kills the entire fixture cgroup and independently confirms empty.
2. `--mode cgroup`: an observer outside the workload writes cgroup.kill and
   observes `populated=0` before removing its own empty cgroup. Returns exit 0,
   `process_check_passed=true`. The pids cap is configured and read back before
   launch. It is not a fork-bomb or native per-task cap acceptance test.
3. Both modes run a separate disposable container using the existing local
   verification image with pull disabled: UID 1000, no capabilities,
   no-new-privileges, read-only root, no network and a 16-process limit. Its
   only source bind is the read-only fixture; scratch is an 8 MiB tmpfs.
   All 12 assertions pass: UID, capabilities, privilege escalation flag,
   scratch write, root/source/cgroup write refusal, absent Docker socket and
   host account path, unavailable host private directory, no supplied provider
   credentials, and refused reserved-address external connection.

The container isolation test and cgroup kill test use separate workloads.
They do not prove a composed native launcher, approved endpoint routing,
credential mediation, role-specific tools, durable identity, one-workload
locking, Hearth record reconciliation, a deadline scheduler or outside alarm.
The image is a fixture image, not an approved native workload image. A refused
connection without a route is not a tested model/broker egress allowlist.

Commands, on the trial host only:

```sh
python3 test/fixtures/hearth2_containment_probe.py --execute-trial-fixture --mode parent
# Expected exit 1; all isolation assertions and cleanup still pass.
python3 test/fixtures/hearth2_containment_probe.py --execute-trial-fixture --mode cgroup
# Expected exit 0; all isolation assertions and cleanup pass.
```

The two observed receipts are retained in private `containment-fixture-*`
folders under `/root/hearth-runner-trial`. No fixture container or cgroup
remained after the runs. No controller settings were enabled or changed.

## Concrete next integration contract

A trusted root-side launcher must own container creation and the authoritative
workload/cgroup identity. A workload receives neither Docker access nor a root
launcher administration route. Bind a single-use launch registration to the
already-claimed run/generation/epoch, fixed image and role policy; do not accept
worker-supplied images, host paths, credentials or arbitrary root commands.
Launch only after installing its resource limits and absolute deadline. A
persisted identity must survive controller restart; unknown containment stays
held rather than being retried.

Keep the CLI transport and task work inside the same restricted namespace.
Protocol mediation may rewrite/refuse dangerous core options, but it cannot
observe all internal CLI tools. Root-owned native policy must independently
deny unapproved tools, subagents/delegation and config escapes. Mount only the
approved code/input, scratch and read-only policy. Network requires a root-owned
fixed-destination gate for the selected provider and private broker. No global
HM/core token or existing agent home enters the worker.

Two points still require source-backed resolution before implementation or
activation:

1. Determine an exact, tested root-owned policy/launch configuration supported
   by the installed native CLI versions. Exercise unsafe flags, fork/resume,
   per-turn config, direct tools, delegated MCP and malformed messages. If the
   pinned core cannot be constrained externally, bring the minimal pin patch
   for review before installing it. No pin change has been made.
2. Clarify the native account boundary: the pinned Claude adapter passes the
   seat OAuth token into the CLI. Does "no agent-home secrets" mean no broad
   host home/HM/core credentials, while allowing the native client's own seat
   login, or must provider credentials also be mediated outside the workload?
   A CLI with its own login is not proof that an allowed shell tool cannot
   read that login. If provider credentials must remain outside, a provider
   credential gateway needs separate subscription-compatible verification;
   a scratch mount or protocol shim cannot establish that property.

Ruling: keep native launch disabled while these are unresolved. Continue
fixture/controller work that does not depend on the chosen credential path.
This preserves current account settings, the pinned core and the approved
premium-seat budget. Cost if wrong: live acceptance is delayed; no unsafe
native launch or claim of containment is substituted for the missing proof.