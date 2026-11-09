# Human work status

The read-only page is `/api/hearth2/status/view` on an enabled, authenticated
Hearth 2 instance. It uses the existing human browser session. JSON is available
at `/api/hearth2/status`; both accept an optional `project_id`. The protected
stylesheet is `/api/hearth2/status/style.css`. Workers and controllers cannot
open these human routes. Reading the view creates no delivery acknowledgement,
poll, failure report, task transition or recovery.

This increment is locally implemented and tested. It does not enable an instance,
deploy a page, start a runner, alter Commons watches or activate the inactive
900-second/full-run policy.

## What the person sees

- **Assigned work:** persisted task state and assignee, including separate
  Running, Awaiting independent review, Awaiting human acceptance and Accepted.
- **Notices & delivery:** Recorded / Delivery unconfirmed. Expand View evidence
  for the notice and task records, recorded sender, acknowledgement state and
  evidence reference. Existing notices have no reliable recording timestamp;
  the page leaves that unknown. Extra metadata claiming delivery is not accepted
  as a delivery receipt, and opening the page does not prove comprehension.
- **Controller polling:** Poll recent, Poll overdue or Poll status unknown.
  Evidence includes the last completed poll, assessment time, cadence/grace,
  age, request, journal sequence, restore period and recorded references.
- **Reported failures:** open and recovered reports remain separate from poll
  freshness. A new tick does not close an open report. Reports from an earlier
  restore period are explicitly historical.

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

Independent review found no new issues. The immutable offline full suite passed
1,087 tests in 152.654 seconds, actual exit 0, with external networking disabled
and loopback only. All 102 checked code/test files (including app wiring) matched
the tested snapshot. Detailed evidence is retained in the plan's private
workspace. The native browser/phone delivery and off-host observer tests
remain independent future acceptance gates.
