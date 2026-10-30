# Durable launch registration

This is a controller-side library, not an enabled runner or native launcher.
It implements part of the existing piece-2 controller task. It does not change
the SQL layout, add an HTTP route, activate a service or authorize a model run.

`DispatchRegistry` uses the work record's transactional, immutable audit journal.
Each registration binds the canonical claim, task, run, attempt, generation,
restore epoch, model, role revision and fixed run deadline. The deterministic
workload name comes from the record-generated run ID. A policy SHA256 identifies
the root-owned policy artifact that a future launcher must verify and enforce;
recording a digest does not establish that the policy is safe or installed.
No worker-supplied command, image, path, credential or PID is accepted.

The state transitions are:

1. `prepare(claim, policy_sha256=...)` rechecks the live claim and durably reserves
   the instance-wide slot. A changed policy for the same run is refused. Replay
   returns existing status, including an already consumed registration.
2. `consume(claim)` rechecks the authoritative lease, epoch, plan and role,
   and changes `reserved` to `launching` exactly once. Only the successful caller
   may proceed to a future root launcher after commit. A second caller fails.
3. `release(run_id)` reads a closed claim, run end and verified-empty containment
   evidence from the authoritative record. A worker cannot supply a boolean
   assertion to release the slot. Expiry, restart and unknown outcomes never
   release it. Repeated release is status only.

One unresolved registration blocks preparation of every other run across all
controller identities in that database. This is a database-wide invariant for
consumers of this library, not a host-wide lock or an OS isolation boundary.
Every real launcher must use it; the existing Store claim API alone does not
enforce one workload per instance.

Crash handling is deliberately conservative. A crash after preparation or after
consumption may leave no actual process, but the controller cannot infer that.
It inspects the persisted workload identity and obtains independent empty proof
before reconciliation and release. A crash after launching cannot repeat
`consume` to start another workload. No PID or native session is termination
proof. A restored database preserves registrations, fences old claims and keeps
unresolved registrations visible until post-restore reconciliation.

An export can occur after run reconciliation but before slot release. In that
case the restored run is already closed, so the existing record reconciliation
API cannot reopen it to attach fresh proof. The registry conservatively keeps
that slot blocked. A dedicated recovery operation for this edge is not yet
implemented; pre-restore proof never releases it. The normal active/held restore
path supports fresh reconciliation before release. This conservative recovery
gap must be resolved before enabling a production controller.

Controller identity rotation or replacement is another recovery case: ordinary
release is bound to the exact controller that registered the workload. A new
controller may inspect pending registrations but cannot impersonate that owner
or release its slot. Keep the slot blocked until a dedicated recovery operation
can verify fresh termination and explicitly transfer responsibility. Changing
credentials must not silently reassign controller identity or bypass this hold.

The registry's evidence is included in the existing version-1 export because
all audit rows are already exported. The previous binary retains those rows but
does not implement launch registration. Production is untouched.

The controller's combined `claim_and_prepare` operation checks the single slot,
the role revision observed before account preflight, and task eligibility before
committing a claim and registration together. Losing the global race or a failed
reservation write consumes no attempt. `record_and_release` similarly commits
receipt and eligible release together; a failed journal write rolls back receipt
and task/claim closure. Unknown outcomes retain the slot. These operations reuse
the Store transitions inside the caller-owned transaction; public standalone
Store APIs retain their signatures and behavior. The normal closed-run export
window is removed for this combined path. Existing/standalone closed-run and
controller-rotation recovery cases still remain conservatively held as above.

Tests exercise restart, duplicate consumption, changed policy, authorization,
expiry, unknown termination, global slot ownership, restore, and two independent
processes racing to consume the same registration. They use synthetic tasks and
no provider credentials. Native integration must still prove account/allowance
guards, exactly one provider credential, root-owned tool/network policy, resource
limits before prompt, deadlines, verified termination, recovery and alarms.
