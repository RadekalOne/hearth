# Absolute deadline trial primitive

This is an opt-in synthetic OS fixture, not an installed launcher or piece2
acceptance. It runs only as root on srv2065995 with explicit opt-in. No native
CLI, credential, provider, production service or account change is involved.

The fixture creates a stopped immutable Docker ID in its own retained parent
cgroup and arms a PID1-owned one-shot UTC calendar timer BEFORE any start. A
second simulated submitter tries to extend the same unit by sixty seconds; it
must fail and leave the original deadline unchanged. The submitter exits before
workload start; an outside observer stays outside the workload cgroup.

At the fixed deadline a separate root job first freezes and kills the whole
parent cgroup, including a detached SIGTERM-resistant descendant. Only then does
it use Docker. It verifies its own label/parent, observes actual exit where a
worker started, removes the immutable ID and requires successful absence and
cgroup-empty queries. Removing the ID prevents a later start of that same ID;
killing alone does not establish that property. The frozen parent is retained
until independent outside observation. All own containers/cgroups/transient units
are cleaned and checked inactive before success is printed.

Cases: delayed start consumes the original eight-second budget; never starting
until expiry still removes the stopped ID; injected Docker unavailability after
freeze/kill must stop all workload processes but FAIL the guard without a success
receipt or removal/release proof. The outside observer then does explicit cleanup.
An OS-empty observation alone must not be promoted to a full launch/recovery PASS.

Deadline scheduling uses the trusted host UTC clock. The fixture allows 1.5s
observation scheduling tolerance around an eight-second test; this is not a claim
of zero scheduling jitter or a new production grace period. Existing two-hour
limit and 900-second defaults are unchanged. Kernel-level freeze/kill precedes
Docker so the workload does not depend on a responsive Docker daemon to stop.

Still separate: seal the actual DB run deadline/epoch/generation/owner to the
immutable workload identity; arm and verify the guard transaction safely before
consume/start/prompt; handle partial arm/consume crashes; trusted late OS-only
observations and restart/restore reconciliation; real privilege/credential/egress
composition and outside alarms. Duplicate transient-unit submission is not an
actual controller/database restart drill, nor a host-reboot recovery proof.
Full-run lease/grant design remains CONDITIONAL/inactive pending that composed
proof; do not extend defaults or grants from these primitive tests alone.

Earlier development receipts absolute-deadline-lkcj6dga and qsdhplfe passed
delayed/never-started cases. Final source, daemon-failure and independent review
evidence will be recorded below after execution.

## Review and final execution, 31 October

Independent read-only review found two Important fixture defects: error cleanup
disarmed the timer before proving emptiness, and the daemon-failure branch lacked
the same absolute timing check. One fix pass adds independent kernel quiescence
first, retains the guard if cleanup cannot proceed, and checks bounded outside
observation time in the daemon branch. Normal cleanup disarms only after verified
container removal, then requires a successful active-unit inventory and absent
parent. Collected transient units are not mistaken for failed termination.

A private unsafe-order control and fixed regression each inject early observer
failure plus unavailable cleanup before the deadline. The unsafe copy reproduces
a live populated1 workload with guard gone; the fixed source has populated0,
actual stopped exit137 and original guard still armed. An outside root observer
then verifies own cleanup. Receipts absolute-deadline-3kxy6unc and r0o_7vl8,
file outside-negative-receipt.json. The unsafe copy is private test evidence, not
a committed implementation. Its running Docker State.ExitCode=0 is a raw state
field, NOT an observed successful process exit.

The opt-in --early-cleanup-failure path deliberately exits with failure and
retains its root-owned state/guard for the outside observer. Do not interpret
that path as a successful cleanup or run it without its paired outside cleanup.
The private reproducible driver is outside-control.py in the final source
directory below. Its state names/labels/IDs are validated before outside removal.
A separately delayed guard control waits two extra seconds before the kill; the
daemon-case absolute-time assertion refuses it, exit1, cleanup verified. Log and
receipt late-daemon-guard-control* remain in that same private directory.

Final fixture SHA256:
1d31a0a4786c5f86dee4699d0743ee6ab1662a898d1521519625af95a3e1ce89.
Final source/archive hearth2-absolute-fixed-20261031-8c952e40, SHA256
8c952e4017663280218ce432801abcda7364b338bb4a5a37bbc90e1e0b651ffd.
Three cases PASS, own cleanup verified:

- absolute-deadline-itytrm_3: delayed start, exit137, parent1->0; guard freezes
  0.043s after the sealed deadline.
- absolute-deadline-ga_havre: never started, no fabricated exit, ID removed;
  guard freezes0.041s after deadline.
- absolute-deadline-ev3ab324: injected Docker failure, actual exit137/populated0
  observed0.165s after deadline, NO guard success/removal/release receipt. Outside
  cleanup later succeeds, kept distinct from the failed guard's proof.

Full offline Python485PASS94.591s on hearth2-absolute-final-20261031-e481e6d8;
only the opt-in deadline fixture cleanup/timing checks and docs changed afterwards.
Native profile/helper/unit code is identical. Final actual native tool/discovery
cases on8c952e40 also PASS: direct-mcp-k3wgy8kj (Codex synthetic loop),
0n_thwpj (normal Codex ChatGPT-profile discovery/read), byqh2i1x (Claude loop).
No provider inference/login or real credential used; fixture limitations in
DIRECT-NATIVE-PROFILES.md remain. No repeat internal review claimed; real controls
verify the single fix pass. Claude exact-commit review remains separate.
