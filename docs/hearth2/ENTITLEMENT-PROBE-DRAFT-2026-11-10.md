# Piece 2 — one real-turn request, draft for review

The credential-free walking skeleton passes at its stated scope; real account
execution and real-model behaviour remain unknown. This request is prepared,
not executable: Rad's usage evidence and the reviewed live execution safeguards
below are still pending, and no paid turn or activation is authorized.

## Decision requested later

Authorize **one supervised task / one native user turn**, exact `gpt-6.1-sol`,
isolated Codex0.159.1 on trial `srv2065995` only. Replace only the fake provider
in the walking path with the explicitly approved existing ChatGPT seat route.
Keep the Broker's memory data synthetic for this entitlement test; do not add
real HM credentials, production access, shell, write tools, agents or retries.
The real model must choose the scoped memory read and compose its own closeout;
failure to do either is recorded, not corrected by a scripted provider.

This would answer whether that account can execute the exact model through the
reviewed path. It would not accept piece2 or full A4–A9/N2/N3, validate Claude's
seat, deliver a plan document, or start the seven-night window.

## Scheduling gate — not yet satisfied

**Do not schedule the actual turn until conditions 3–5 below are implemented in
the live execution path and pass independent review at the exact execution
commit:** canonical reviewed `turn/start`, separately bounded streamed-event
handling, and private Broker-capability delivery. The fixture subclass is not
that implementation. Two provider requests can each stream many notifications;
the request cap does not satisfy condition 4 or fix the 64-notification limit.

Scheduling also requires all account, capacity and financial evidence below;
freshness is checked again immediately before send. Scheduling or a component
PASS is never authorization to send. Rad's own `[APPROVED]` remains required,
and this packet remains prepare-only while any prerequisite is unresolved.

## Missing cost and capacity evidence

| Required before execution | Current status |
| --- | --- |
| ChatGPT seat usage windows, remaining capacity, reset times and credits/extra-use status | Pending Rad's screenshot, taken within 15 minutes of actual send |
| Claude seat usage windows, reset times and extra-use status | Pending Rad's screenshot, taken within 15 minutes of actual send; no Claude turn proposed here |
| Explicit confirmation for both accounts that auto-recharge and pay-as-you-go/extra usage are OFF | Pending dated Rad confirmation supported by the account evidence; no setting change is authorized |
| November total against the existing $75/month stop rule, and remaining headroom | Unknown; do not infer from a login or test receipt |
| Account/route identity without exposing login material; no API-key fallback or automatic credit/extra-usage purchase | Not verified for this execution path |
| Enforceable incremental dollar ceiling | Not established; screenshots and time limits alone are insufficient |

For this packet, **Rad's screenshots are the sole accepted preflight allowance
evidence**. No usable programmatic balance read is verified on this execution
path. A documented or future account API is not a substitute in the current
gate; this does not deny that Codex documents a rate-limit read mechanism.

For each seat, record `taken_at` with timezone, observed windows/headroom/reset
times, and the corresponding account identifier without login material. At
actual send, require `taken_at <= send_at <= taken_at + 15 minutes` for **both**
screenshots. Missing/ambiguous timestamps, expired evidence or insufficient
headroom mean refuse send and request refreshed evidence. Do not silently reuse
screenshots from the review or scheduling time. Obtain the explicit OFF
confirmation for both accounts before send; unknown/ON state means refuse.
This update does not log in, inspect accounts or turn any setting OFF itself.

**Requested ceiling: $0 additional metered charges**, consuming only approved
included-seat allowance. This is a proposed authorization limit, not a verified
property of the client or a claim that inference is free. If the actual route
cannot enforce included-only use without spending credits/overage, refuse this
request as written and prepare a separately capped financial request. Do not
convert token counts, rounded quota deltas or timeouts into an invented cost.
Do not change billing, credentials, settings or purchase anything to make it fit.
Fresh screenshots and OFF confirmations are necessary manual gates, not proof
of an enforced monetary ceiling. Existing credits, account fallback or any
route that could spend outside included allowance must still be ruled out by
the reviewed execution/financial boundary; otherwise this request is refused.

A before/after quota snapshot is useful capacity evidence; Rad's concurrent seat
use and rounding can prevent attribution. Actual charge remains unknown/null
unless independent billing evidence establishes it. No API price is being used
to price a subscription turn, and no speculative dollar upper bound is claimed.

## Exact proposed exercise, pending implementation/review

1. Freeze the execution commit, pinned client/image/config and a per-run journal;
   Claude reviews the actual turn bridge, limits and stop path before approval.
   The walking fixture's private-method bypass is not an approved live bridge.
   Conditions 3–5 must already be implemented and independently passed before
   this exercise can be scheduled; a provider-request cap is not an event cap.
2. Recheck exact root trial-host identity, unchanged baseline, fresh task/claim,
   lease/epoch/deadline and approved account/route. For allowance, use only Rad's
   two screenshots, each no older than 15 minutes at actual send, plus explicit
   confirmation that auto-recharge and pay-as-you-go/extra usage are OFF on both
   accounts. Separately verify the reviewed financial ceiling and no fallback;
   do not imply an available programmatic allowance check. Record sanitized
   preflight evidence; a missing item means stop
   before sending a turn. No login, account change or token refresh is implicit.
3. Create one isolated workload with no service installation. Permit only the
   reviewed provider/auth destinations and the scoped Broker; keep the worker
   read-only and shell-disabled. Broker capability must use the separately
   reviewed private delivery mechanism, not a container environment variable.
4. Use the passed exact-model/request guard, verify returned approval policy and
   sandbox, and durably bind the returned thread ID to this claim. Any exception
   after thread request dispatch means a thread may exist: stop the workload.
5. Send one canonical user turn with this task and synthetic memory challenge.
   Proposed bounds: prompt at most2KiB, memory response at most2KiB, final closeout
   at most16KiB, no artifacts. The live transport must enforce a maximum of two
   provider requests (memory-tool step and final response), counting attempted
   native retries; a third request is denied, not retried. These are review
   requirements, not controls implemented by this draft.
6. Proposed cutoffs:45s from turn dispatch,90s absolute whole-workload deadline,
   whichever comes first; independent root stop covers every child. These are
   proposed one-shot limits, not changes to the inactive900-second/full-run policy.
   Request/byte/time bounds limit exposure, not money by themselves.
7. On completion or any failure, stop the exact workload, observe exit and whole
   cgroup/container termination outside the worker, revoke the grant and remove
   the isolated environment. Persist the native IDs, closeout or its absence,
   usage if actually supplied, and the root evidence before releasing a slot.
   Missing/malformed closeout fails; uncertain exit/output/containment stays held.
8. Capture post-run usage/billing observations with timestamps and attribution
   limits and apply the financial reconciliation rule below. A clean model
   completion cannot override a financial-gate failure. Post one run-ID/evidence
   review for Claude. Stop: no automatic second
   attempt, model substitution, quota-reset consumption or credit purchase.

## Financial reconciliation — separate from model completion

Compare the dated pre-send and post-run evidence for included-window use,
credits, paid extra usage/charges, recharge state and resets. **Any consumption
inconsistent with included-only operation is a FAIL on the financial gate**,
even if the model turn, closeout, process exit and cleanup all succeeded.
Examples include a paid-credit debit, a new metered charge or evidence that
pay-as-you-go/recharge was enabled. A discrepancy that cannot be reconciled
because of concurrent use, rounding or missing evidence remains an unresolved
financial-gate FAIL, not a presumed PASS or an invented attributable charge.

Record the run ID, timestamps, observations, expected included-only behaviour,
the mismatch and attribution uncertainty. Preserve any technical receipt; append
the financial failure/correction rather than rewriting prior observations.
Report the failure to Rad and Claude, do not declare an overall probe PASS or
acceptance, and stop further attempts pending Rad's decision. Do not retry,
purchase credits, change settings or broaden access to reconcile the result.
Actual charge stays unknown/null unless independently established; that does
not turn the financial failure into success.

## Six conditions carried from Claude's review

These remain open for shipped code; neither component PASS closes them. They
are recorded here to avoid silently promoting fixture behaviour into authority.

1. Verify effective `approvalPolicy` after `thread/start`; post-write exceptions
   imply a possible existing thread and require workload termination.
2. Persist thread creation and identity in a journal or the authoritative receipt.
3. Add canonical `turn/start` to the reviewed RPC code and review it independently.
4. Give the turn bridge its own bounded event handling; the current64-notification
   pre-turn session limit is insufficient for a real turn.
5. Deliver Broker capability through an approved descriptor/private-memory
   mechanism, not Docker environment metadata or inherited child environment.
6. Use per-run journals or reviewed rotation before overnight operation; the
   current4MiB journal cap otherwise refuses every subsequent launch.

Per-run journaling can satisfy this small exercise without implementing general
rotation. These conditions do not block preparing the request; execution still
needs the specific safeguards and financial gates to be concrete and reviewed.
In particular, conditions 3–5 are explicit pre-scheduling gates, not merely
carried-forward notes. All six conditions remain open; this documentation
revision implements none of them.

## Stop and rollback

No installed service/global client/account/config change is proposed, so no
production rollout rollback is needed. Kill and independently verify the exact
trial workload; revoke only its grant; quarantine any persistent private test
material; retain journals and failed-run evidence. Never reuse a consumed launch
intent. If cleanup or billing state is uncertain, hold the task and stop; do not
restore a database over live workloads or delete evidence to manufacture a reset.

## Approval wording — not an approval

After filling the missing evidence and exact execution commit, Rad can approve
or decline a request naming this packet and that commit: one trial-only exact-model
turn, included-seat allocation only, no additional metered charges, the reviewed
limits, no retries/activation/production changes. Until Rad supplies his own
`[APPROVED]`, execution remains prohibited. This document grants no authority.

## Sources and verification limits

- Claude review `drawer_ff38dcebac9a75cb3e448ac8c5f8f6c3`,10Nov: both scopes PASS;
  source hashes checked and96 focused tests reproduced; VPS receipts and commit
  signature not independently verified by Claude.
- Claude's conditional packet review, Agent Tasks event
  `$zQGxjLVFOjNSpDWlQzjXbbysc7gMDq-DwNRpM8tdo0g`,10Nov22:03UTC:
  gaps1–3 addressed in this revision as explicit scheduling, manual evidence and
  reconciliation rules. This is the author's revision, not a new Claude PASS.
- Walking source/evidence8e9cdba, `WALKING-SKELETON.md`, HM
  `drawer_403b461a7f333032f09597750664d63d`. No account turn has occurred here.
- Official [Codex app-server documentation](https://learn.chatgpt.com/docs/app-server)
  describes rate-limit reads; it does not establish this account's entitlement
  or a per-turn dollar ceiling. Consult the separate design answers for scope.
