# Named-session client implementation plan

> Execute inline using superpowers:executing-plans and TDD; one fresh final review.

**Goal:** A real reusable client retrieves, validates, durably stores and acknowledges notices for its named session; receipt does not mean understanding or task completion.
**Architecture:** One-pass async HTTP client with fixed HTTPS origin, separate explicit session bearer, no environment credentials/proxy/cookies/redirects. Server protocol remains unchanged. A supplied private SQLite inbox is pinned to origin+session/principal/recipient; it stores allowlisted body/offer/receipt only, never credentials. Session code can read this inbox independently; no model execution or understanding flag.
**Tech:** Existing httpx/Python/SQLite and actual temporary authenticated app through ASGI HTTP transport.

## Binding design
- NamedSessionClient(origin,target,token,inbox,transport=None,max_notices=10); explicit poll_once, no daemon/CLI/service startup or native Claude/Codex integration. Fixed HTTPS origin only, no URL credentials/path/query/fragment; no redirects, ambient proxies/auth/cookies. Default TLS verification. Token only in Authorization, never local DB/errors/results.
- One bounded inbox fetch; process max1..50 unique notices, local uncertain receipts before new remote summaries. At most50 server summaries, bounded response bytes, request timeout and async cycle timeout. No recursive drain/retry loop.
- Validate inbox, exact intended session/recipient, notice ID/path, body fields, offer epoch/delivery ID/timestamps/sequences; independently compute canonical public body SHA before local storage. Invalid/mismatched response cannot be acknowledged.
- Store validated notice+offer atomically in client inbox BEFORE ack. Same notice+digest is deduplicated, different body refuses overwrite. Local failures never cause ack. Read APIs have no acknowledgement/understanding/completion side effects.
- Stable receive request ID from origin+session+notice+epoch; interrupted receive replays original server offer. Ack lost-response leaves local stored-but-unconfirmed record. Next invocation retries local pending notices even if server inbox omitted them after committed ack, then records original server receipt. Restore uses current inbox epoch; never silently rotate identity/rebind local store.
- Validate server receipt against notice/digest/session/principal; accept server's retained first receipt (possibly original delivery ID/epoch), never invent new time. Local receipt conflict refuses overwrite. Credentials and unrelated task state never enter client persistence.
- Poll result reports stored/receipt counts and more_pending, understanding_state unknown. Stored receipt means authenticated protocol receipt and durable local inbox, not model ingestion, comprehension, task progress/completion, worker health or live process identity.

## Task1: deliver and prove increment
- [x] RED client/local-inbox tests plus end-to-end actual app: controller targets A; B sees nothing; A client persists exact body before ack; human receipt visible; task unchanged/understanding unknown.
- [x] Implement focused client and private session inbox; fail closed on tampered response, identity/digest/origin, storage failure and HTTP/auth error.
- [x] Verify lost receive/ack responses + restart/deduplication, no credential persistence, bounded batch/response/redirect and scope conflicts.
- [x] One final static fresh review, one fix pass if required; immutable offline suite, signed local commit and remote HM outcome/checkpoint. No live enrollment/provider/native/client/service/automation/deploy/push changes; preserve900s inactive and private history.


Verification:9 focused client/inbox tests PASS0.557s and3 actual authenticated
app client end-to-end tests PASS9.259s. One fresh static review found no actionable
findings (reviewer did not execute tests). Full immutable Ubuntu24.04/Python3.12
suite:1,131 tests PASS164.826s, actual exit0; external networking disabled/loopback
only. All113 checked code/test files matched the snapshot. SHA256:
fb46533bed3c2fcf48550478935760aa94c86dae9cbd92b7d95086ffb6ebf096.
This is local ASGI HTTP protocol/client acceptance, not live native session,
TCP/TLS/OS acceptance or deployment. No provider/client/service/automation started.
