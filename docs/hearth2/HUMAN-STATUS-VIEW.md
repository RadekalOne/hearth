# Human work status

The read-only page is `/api/hearth2/status/view` on an enabled, authenticated
Hearth 2 instance. It accepts an existing human browser session or a human bearer
token; worker/controller bearer tokens are rejected. JSON is available
at `/api/hearth2/status`; both accept an optional `project_id`. The protected
stylesheet is `/api/hearth2/status/style.css`. Workers and controllers cannot
open these human routes. Reading the view creates no delivery acknowledgement,
poll, failure report, task transition or recovery.

This increment is locally implemented and tested. It does not enable an instance,
deploy a page, start a runner, alter Commons watches or activate the inactive
900-second/full-run policy.

## What the person sees

- **Assigned work:** persisted task state and assignee, including separate
  Running (claim recorded), Awaiting independent review, Awaiting human acceptance
  and Accepted. Running is not worker liveness: the view shows its current-epoch,
  matching-generation claim lease expiry and current/expired/unknown lease state,
  and explicitly leaves worker liveness unverified. Expiry does not diagnose a stop.
- **Notices & delivery:** Recorded / Delivery unconfirmed. Expand Inspect record
  for the notice and task records, recorded sender, acknowledgement state and
  evidence reference. Existing notices have no reliable recording timestamp;
  the page leaves that unknown. Extra metadata claiming delivery is not accepted
  as a delivery receipt, and opening the page does not prove comprehension.
- **Controller polling:** Poll recent, Poll overdue or Poll status unknown.
  Evidence includes the last completed poll, assessment time, cadence/grace,
  age, request, journal sequence, restore period and recorded references.
- **Reported failures:** open and Recovery reported remain separate from poll
  freshness. Reporter=target adds a Self-reported badge. Recovery reports use
  neutral styling and do not establish independently verified health. A new tick
  does not close an open report. Older restore-period reports are historical.

Record fields and reporter-supplied references are presented separately. Free-text
references are explicitly unverified. The unreleased status JSON now names them
`supplied_references` with `reference_provenance=reporter_supplied_unverified`;
failure rows also expose `self_reported`. Existing journal write/control APIs keep
their original `evidence` field. No reference is validated merely by being stored.

The journal still permits a controller to report its own recovery. Before adding
acknowledgements or an outside observer, enforce a distinct observer authority or
a rule prohibiting self-recovery. The badges address the immediate display risk,
not that future authority boundary. A separate controller identity in tests does
not implement a distinct observer principal kind.

Controller health is instance-wide even in a project view. Task and notice cards
are restricted to that project. All records are read in one transaction, and
only status/evidence fields are returned; claim secrets and private run metadata
are not part of this read model.

## Explicit timing expectations

An operator may later configure the optional `HEARTH2_POLL_EXPECTATIONS` value on
the isolated instance. No existing deployment configuration was changed here.
Example for an instance whose configured controller ID is `controller`:

```json
{"controller":{"cadence_seconds":300,"grace_seconds":60}}
```

Only configured controller IDs are allowed. Each entry requires exactly cadence
1–86400 seconds and grace 0–3600 seconds, using JSON integers. Duplicate keys,
booleans, extra fields and malformed values refuse enabled initialization before
database creation. Disabled mode ignores the optional setting.

There is **no default cadence**. Without an expectation or a completed current-
restore-period tick, status is Unknown. A future or unusable tick timestamp is
also Unknown. Otherwise the original server-journal tick time is compared with
the server observation time: age greater than cadence plus grace is Overdue;
at the exact boundary it remains Recent. Replaying a tick retains its original
time. Recent proves only a recent recorded controller poll, not successful work
or delivered notices. Overdue does not diagnose a dead host.

This is an assessment as of a visible timestamp. Refresh reassesses it; a page
left open does not update itself. No independent outage observer or delivery
transport is implemented by this view.

## Verification

Synthetic real-HTTP acceptance creates and assigns a handoff, inspects its
running state and recorded progress, and advances a controlled clock through the
cadence/grace boundary. It also checks replay, access roles, default-off behavior,
project filtering, restore-period history, explicit recovery, missing/invalid
time and configuration, escaping and omission of forged delivery metadata.
Browser inspection of exported actual authenticated responses verified Recent,
Overdue, Unknown and expandable evidence at desktop and 390px mobile viewport;
mobile document width fit its available viewport without horizontal overflow.
The preview used synthetic data only and its loopback server was stopped.

The initial fresh Codex review had no findings. Claude's subsequent independent
review passed the original three commits with one High and three Medium findings;
the author fixes and remaining authority gate are recorded in
`CLAUDE-STATUS-REVIEW-RESPONSE.md`. This follow-up passed the immutable offline
suite: 1,094 tests in 174.434 seconds, actual exit 0, external networking disabled
and loopback only. All 102 checked code/test files (including app wiring) matched
the tested snapshot. Detailed evidence is retained in the plan's private workspace.
Native browser/phone delivery, independent observer authority and broader-slice
verification remain separate future acceptance gates.
