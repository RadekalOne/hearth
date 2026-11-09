# Named-session notice receipts

A receipt records that the enrolled authenticated session acknowledged an exact
notice through the receive/acknowledge protocol. It does not establish model
context ingestion, comprehension, agreement, worker health, progress or completion.
Task, run, claim, incident, review and human acceptance authority stay unchanged.

## Optional enrollment (not installed)

HEARTH2_NOTICE_SESSIONS is strict JSON mapping a session ID to principal_id and
recipient. Example shape with noncredential labels:

```json
{"claude-laptop-review":{"principal_id":"claude-laptop-review-session","recipient":"claude"}}
```

Each principal must be unique and disjoint from human, controller, worker and
observer roles. Recipients must be configured humans/controllers/workers. IDs are
bounded canonical ASCII labels, maximum128 sessions. Invalid enabled configuration
fails before database creation; disabled instances do not parse it. Configuration
does not provision a credential. A distinct bearer credential must identify each
session; an agent-wide worker token or a caller-supplied name cannot prove which
session received a notice. Session credentials cannot create tasks/notices, tick,
observe, review, accept work or read other sessions' inboxes. Cookies are refused.
The enrollment is operator authority, not measured OS/native session identity;
changing or reusing labels/credentials does not prove process continuity.

## Address, receive, acknowledge

1. A controller with a live claim posts a notice with recipient and explicit
   recipient_session. The service checks configured recipient agreement and pins
   the frozen session/principal/recipient and exact allowlisted body digest in a
   separate notice_addressed audit event. Unaddressed legacy notices stay
   unconfirmed; no session is inferred from payload delivery metadata.
2. The session bearer calls GET /api/hearth2/session/notices. It returns at most50
   pending summaries plus more_pending and current restore_epoch. Reads do not
   mark delivery. Receiving/acknowledging pending notices allows subsequent batches
   to surface. Internal history scanning is not a high-volume performance claim.
3. POST /api/hearth2/notices/{id}/receive accepts request_id and expected_epoch.
   Only the pinned session under unchanged current enrollment can receive. The
   response contains the notice body, notice_digest, server-generated delivery_id,
   named session, offered_at, offered_sequence and restore_epoch. The digest is
   SHA256 of the exact response notice object encoded as UTF8 JSON with sorted
   keys, compact comma/colon separators, ASCII escaping and finite JSON values.
   The session can recompute it from the received body; target binding is pinned
   separately in the journal. The offer is
   journalled atomically, but delivery remains unconfirmed. Retrying the same
   request ID within that period returns the original offer/body/time.
4. After receiving that response, the same session posts delivery_id,
   notice_digest and expected_epoch to /notices/{id}/acknowledge. The journal
   verifies an issued current-period offer, authenticated session, pinned intent
   and exact content. A blind acknowledgement, wrong session (even for the same
   agent), other notice, changed body, wrong digest/ID or old epoch is refused.
   The first valid notice_receipt is durable; retries and additional valid offers
   return the original receipt/time. No payload understood/completed/state/time
   fields are accepted, and no task tables are updated.

Delivery IDs are protocol identifiers, not credentials; possession never replaces
session bearer authentication. Receipt is the session's authenticated assertion
that it received the body and echoed its bound identifiers, not a proof of human
reading, model understanding or an honest/bug-free client. If the server issues
an offer but the response is lost, there is still no receipt until explicit ack.

After restore, old in-flight epoch-bound requests fail. Under unchanged enrollment,
a new current-period receive may be issued; an existing receipt remains its
original historical fact/time, not a fresh delivery. Rebinding a session name,
principal or recipient cannot inherit authority over previously addressed notices.
No schema migration, client process, real token, schedule or service is installed.

## Human view and small acceptance

The read-only status page distinguishes Delivery unconfirmed from Receipt recorded,
and shows intended session, actual authenticated receipt principal, server time,
content digest, delivery ID, journal sequence and restore period. Historical
receipts are labelled; forged notice payload metadata is ignored. Understanding
remains unknown. A receipt does not complete the task.

The acceptance uses two fixture sessions belonging to Claude and the actual
authenticated temporary HTTP app. A controller creates a targeted notice. Only
session A discovers it; B cannot receive or acknowledge A's notice. A receives
and checks the body, observes that delivery is still unconfirmed, then explicitly
acknowledges its issued ID/digest. The human JSON/HTML shows the receipt, while
the task stays running and all task/run/claim/notice/attempt tables remain unchanged.
Repeated acknowledgement retains the original result; inbox/status reads do not
write. Additional tests cover bearer-only/narrow authority, payload spoofing,
content/notice mismatch, rollback, restart, restore and enrollment rebinding.

This is local synthetic protocol acceptance, not a live Claude/Codex session or
physical delivery demonstration. No live credentials/session enrollment, client
integration, push transport or production deployment is included. The existing
900s/full-run inactive policy, observer and Commons automation are unchanged.


The subsequent [named-session client integration](NAMED-SESSION-CLIENT.md)
adds a reusable one-pass client and durable local inbox, including lost-response
and restart acceptance. The preceding server-only acceptance remains historical;
no live native session or credential enrollment has been installed.
