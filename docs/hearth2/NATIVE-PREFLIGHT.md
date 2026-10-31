# Native policy and preflight controller

Status: inactive libraries plus installed-client startup fixtures on the isolated
trial VPS. This is not native model, billing, tool-call or full runner acceptance.
The existing core service, account settings and pinned binary are unchanged.

## Observed native policy

`test/fixtures/hearth2_native_policy_probe.py` requires explicit opt-in, root and
exact host `srv2065995`. Each client runs in a disposable network-none container
as UID 1000, with a read-only root, no capabilities, no-new-privileges and bounded
memory/processes. Only its public executable and read-only policy are bound.
Home and `/tmp` are disposable private tmpfs. No real provider login is mounted.
Claude receives a visibly fake fixture key and a closed loopback API URL solely
to initialize its SDK; this is not an allowed production credential route.

Installed versions tested: Codex 0.154.0 and Claude Code 2.1.280. The fixture
refuses an unexpected version instead of silently changing its claims.

- Codex baseline command-line overrides enable shell and multi-agent features.
  Root-managed requirements keep both disabled despite those same overrides.
  The real app-server accepts initialization and a thread-start request that asks
  for danger-full-access, but returns effective readOnly, networkAccess=false and
  the :read-only permission profile. It clamps the request rather than returning
  an error. No turn-start/user task is sent.
- Claude's validated arguments replace skipped permissions with dontAsk, remove
  built-in tools and slash commands, skip user/project settings and restrict MCP
  configuration to the pinned core SDK declaration. Exact model/session identity
  is retained. Unknown flags, duplicate identities, changed models, resume/fork,
  provider/helper configuration, additional tools and malformed settings fail
  closed. Fast mode and workflows remain off. Root-managed denies independently
  prohibit delegation and Cloudroom MCP tools. The real SDK handshake preserves
  hooks_applied=true, has permission mode dontAsk and zero workflow commands.
  A later request to enable bypassPermissions is refused by managed settings.

The current trial policy is memory-only, appropriate to planning/review tasks.
It does not authorize general coding tools. A recorded policy digest is not
proof of an installed policy. Effective requirements can be influenced by other
managed sources; a live launcher must verify the resulting configuration before
each prompt. CLI flags alone are not a security boundary.

These fixtures prove startup/configuration properties. Actual forbidden tool
calls, fixed provider/broker egress, native credential scope, task-scoped memory
wiring, process caps/deadlines and composed containment still require tests.
Network none is intentionally not a model/broker allowlist demonstration.

Relevant primary documentation:

- https://learn.chatgpt.com/docs/enterprise/managed-configuration
- https://learn.chatgpt.com/docs/config-file/config-reference
- https://code.claude.com/docs/en/permissions

## Account guards

`launch_guards.py` consumes trusted controller observations, never a worker's
claim that it is signed in. It reads no credentials and calls no provider.
Collectors and their isolated execution remain to be wired.

- Native observation age must be 0-60 seconds against an aware trusted clock.
- Each route must explicitly identify the expected provider and native login,
  with no API key, unexpected environment override or other account credential.
  Unknown metadata refuses launch.
- Codex requires native ChatGPT authentication, requiresOpenaiAuth=true,
  hasCredits=false and unlimited=false. Both limit-window keys must be present;
  null windows are permitted under the accepted returned-window policy, but at
  least one window must exist and every returned percentage must be finite,
  numeric and below 100. Booleans, strings and absent/invalid limits are refused.
- Claude requires loggedIn=true and the accepted seat-cap/admin-review evidence
  for the current billing month. A positive reviewed amount requires the setting
  review to be recorded, as Rad already did. The cap must match the root-supplied
  accepted policy, with reviewed usage below it. No numeric pre-run allowance or
  worst-case-loss guarantee is invented. This is the accepted admin-review trade;
  the old reviewed amount is not a live per-run measurement or audited build cost.

Sources: piece-2 verification `drawer_4d2218a564ee655b5d1cd1fa70e2a88e`,
billing policy `drawer_07d5151703d16c043e02fb7479f78ba1` and Rad's renewed
review `drawer_773843c44471103f3cd0f94acfc75cde`. Existing approvals stand.
MiniMax is an additional preliminary test and does not pass these canonical
Codex/Claude gates or silently substitute for their exact-model acceptance.

## Preflight-to-dispatch transaction

`PreflightController` reads an eligible ready task and role, performs the trusted
native observation outside the database lock, then uses `claim_and_prepare` to
claim and reserve the instance slot in one transaction. The observed role
revision is fenced inside that transaction. An account refusal leaves the task
ready with zero attempts and a durable dispatch-blocked incident; subsequent
good preflight recovers that incident explicitly. Exceptions and native stderr
are not copied into the record. No account data/email is passed to the worker.

`record_and_release` commits a trusted run receipt and a releasable slot together.
Failure injection verifies rollback of both sides. Unknown outcomes stay held.
This removes the normal export-between-receipt-and-release window for callers
using the combined path. Standalone record APIs retain their prior behavior.

The high-level `prepare` call acknowledges a committed reservation when retried
with the original request, task, controller, requested task revision and policy.
The original requested revision is bound in its dispatch journal entry. Replay
rechecks the live epoch, lease, role and task-bound approval inside the same
claim/reservation transaction. A plain claim without a matching preflight
registration cannot use this path to skip account inspection. Old registrations
without the revision marker remain conservatively held rather than guessing.

A reserved replay returns `replayed=true` with `account_check=null`; this is NOT
a fresh native-account observation. The actual launcher must recheck before
consuming/sending any prompt. A consumed replay returns `already_consumed` and
cannot reissue launch permission. Held, expired and restored claims fail closed.
A failure recovering the preflight incident after claim commit can be retried
without consuming another attempt. Completed receipt/release retries return the
stored result only for the exact original receipt and claim in the current
epoch. The terminal journal stores a canonical receipt digest; a different
receipt or claim is refused without mutation. This does not make held/unknown
closeouts replayable or confer new execution authority.

Prepared means claimed/reserved, not a native task started. This coordinator has
no scheduler, account collector, process launcher, renewal loop or outside alarm.
The actual launcher must recheck freshness/claim and enforce policy, account,
resources, egress and deadline before consuming and sending the first task.

## Projection design work

Claude's design answer in HC `$djK9MjU0O2BhuVqjHII5D5e4jXfjJ7Ve7SpSIukHpQk`
supports a per-run trusted core/account projection, with identical account and
cwd paths on both sides. He did not verify the source or run the spike.
HOME must be account_home; the corresponding config directory is its `.claude`
child, not the same string. Existing host home/core state must not be mounted.

Pinned source `runtime/files.rs` delegates inode opens to `sync/files.py` under
the agent identity. The Python helper traverses directories with dirfd-relative
O_NOFOLLOW opens and refuses nonregular files. The Rust wrapper canonicalizes
paths first, so this is not by itself proof that an untrusted root/ancestor
cannot be redirected. Run-root anchors must be immutable to the worker, and
symlink/rename races and bounded transcript reads must be tested. A read-only
core mount alone does not prevent changes through the worker's writable view.
These remain concrete adapter checks before activation, not a new user approval.

## Reproduced core compatibility failure and approved fallback

On 30 October, `test/fixtures/hearth2_projection_probe.py` completed the installed
Claude 2.1.280 SDK initialization, then received `Unsupported control request
subtype: bootstrap`. The pinned core requires that request before validating its
native transcript (`runtime/claude.rs::start`). Both the hardened arguments and
an unchanged-core-arguments control reproduce the rejection. Both use fake auth
in network-none disposable containers; no inference or user task was attempted.
The control's permissive arguments are diagnostic-only, never a launch policy.
The fixture intentionally exits nonzero and keeps the failed response privately;
its positive native-transcript checks have NOT passed. Containers/projection
roots were removed with successful host-side absence checks.

A short pinned-source check found `docs/harnesses.md` reporting login checks with
2.1.280 and guarded/context-notice checks with 2.1.278, while explicitly reserving
logged-in Linux acceptance. It did not establish any compatible CLI version.
No CLI or core pin was changed or a protocol response fabricated.

Rad's 15 October decision `drawer_fcb3885641cd4b3a3d8849b269d690d9` explicitly
allows Hearth to launch the CLIs directly if core fails its trial gates. Claude
confirmed this failure is the intended trigger in HC
`$zhE8qBx2q7RG5Ni4uxplCSzT15ZalNYK8IIwQXn0N2M`. Hearth 2 will use that fallback
for BOTH providers, retaining one controller/receipt contract. The installed
core remains untouched and will be unused by Hearth 2. This is a design decision
under the existing approval, not an installed launcher or verified acceptance.

The direct adapters must supply core's former responsibilities: durable one-use
launch consumption BEFORE spawning, unknown-outcome hold on restart, a clean
allowlisted environment/settings/credential projection, bounded untrusted
structured output, native allowance-stop pause without substitution or retry,
explicit unknown usage, and outside observation of whole-workload termination.
Re-derive the subscription-only checklist against the direct CLI's actual
credential/config resolution; core-state checks cannot substitute for that.
Re-run isolation assertions against the exact direct-launch image before
acceptance. No worker transcript file will be read by the direct adapter: only
bounded structured stdout, so core's transcript path race leaves this path.
Core's regex Command Guard and writable transcript reader leave the execution
path; managed native policy and the externally enforced sandbox/egress remain
required. A new direct Claude argument/MCP configuration must be independently
verified; the current `claude_arguments` validates the OLD core-compatible
contract and does not silently authorize an arbitrary direct configuration.

No new purchase or account change is proposed. Inference can consume existing
allowances or authorized paid usage. The decision does not establish provider
allowance mappings, a cost measurement, a live memory route or containment PASS.

## Independent deadline fixture

`test/fixtures/hearth2_deadline_probe.py` creates its own transient systemd guard,
private parent slice and network-none resource-capped disposable container. The
submitting `systemd-run` process exits while a workload with a setsid,
SIGTERM-resistant child remains live. PID 1 then enforces `RuntimeMaxSec=5s` and
runs a whole-container kill. An outside observer reads the retained parent
cgroup before and after termination, before removing it.

Observed on srv2065995: systemd Result=timeout, container exit137, populated=1
then0, 5.156s elapsed, all own container/cgroup cleanup verified. No native client,
login, broker, network access or model was used. Receipt:
`/root/hearth-runner-trial/deadline-fixture-5r0i9wri/receipt.json`.
This proves the independent deadline primitive after the submitter exits. It
does NOT yet prove wiring the absolute claim deadline into activation, stopping
on lease/approval revocation, controller restart reconciliation, native output
handling or an active hosted service. Those remain acceptance work.
