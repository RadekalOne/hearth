# Delivery and health: first user workflow acceptance

8 November 2026. This is an isolated acceptance exercise through the actual
authenticated Hearth 2 HTTP application and temporary database. It is not a
deployed browser/phone demonstration, real agent execution or Matrix delivery
test. Synthetic controller observations and a controlled server clock keep the
exercise repeatable; no production settings or background jobs change.

## Assign work, follow progress, inspect the result

Scenario: **“Draft the onboarding handoff so a new teammate knows the next step.”**

| Human action or observation | Exercised result |
|---|---|
| Approve the scoped plan and assign the handoff | Task is ready, bound to the approved action. |
| Controller claims the task | Human task view shows running. |
| Controller records a progress notice | Human view retains its sender, recipient and evidence reference. |
| Open the task again | Reading does not create or change delivery/acknowledgement evidence. |
| Controller submits the draft result with synthetic stop evidence | Result is awaiting independent review, not accepted. |
| Independent reviewer passes it | Result is reviewed, still awaiting human acceptance. |
| Human accepts it and reopens the project | Accepted state and run history remain; unmeasured usage stays unknown. |

The existing API can demonstrate those task/result states. Its notices currently
record posting, not transport delivery to a named agent session, acknowledgement
or comprehension. No notice acknowledgement endpoint is supplied by this
increment. A passing record test must not be labeled successful message delivery.

## A quiet controller must not look freshly active

| Controlled situation | Exercised result |
|---|---|
| Controller records a completed poll at 12:00 UTC | Server journal retains that observation. |
| Ten simulated minutes pass; the same request is retried | Original timestamp remains 12:00; retry does not refresh liveness. |
| Human opens control status at 12:10 | View contains server observation time and old poll time. Time passage alone currently creates no stale incident. |
| Separate synthetic supervisor controller reports staleness | Human view exposes the open failure and its supplied references. |
| Controller completes a new poll | Existing failure remains open pending explicit recovery evidence. |
| Supervisor controller supplies a recovery reference | Journal records recovered; the human view qualifies this as a recovery report. |

The supervisor has a separate fixture identity but is still a controller
principal. There is no distinct observer principal kind. The earlier version of
this test used the target controller itself for these reports; Claude's review
identified that qualification, and the fixture now uses a separate identity.
Neither version proves an enforced independent observer authority.

This verifies the journal behavior under a controlled clock. It does not verify
an independent running observer, configured cadence/grace policy, host outage
detection or cross-host clock authority. Those are still separate requirements.

## What this tells us to build next

The smallest next product step is a read-only human status view that clearly
labels **notice recorded / delivery unconfirmed** and **last completed poll /
stale or unknown**, with evidence behind each state. Then verify a named session's
delivery acknowledgement and an outside stale observer. Do not invent delivered,
read, understood, dead, or recovered states from a task record or a green tick.

These are implementation candidates informed by the exercise, not a new launch,
notification transport or production activation decision. The approved inactive
900-second/full-run policy and existing Commons watches remain unchanged.

## Reproduce offline

Run `test/test_hearth2_delivery_health_acceptance.py` with the existing project
environment. The two scenarios use the real API routes and store, fixture-only
identities, an in-process ASGI transport and temporary data. Native workers,
external providers and real room posts are not involved. Their first observed
run passed both scenarios; this characterized existing behavior, so no fabricated
RED run is claimed. The source-map/enrollment production changes separately used
RED-to-GREEN contract tests.
