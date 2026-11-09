# Named-session client integration

The reusable Python client connects the named-session inbox/receive/acknowledge
protocol to a durable local session inbox. An embedding session invokes one pass
explicitly. It stores exact validated notices before acknowledging them. Stored
content remains untrusted text; this integration never executes it, sends it to
a model, changes task state or labels it understood.

## Embedding contract

```python
from hearth2.delivery import NoticeSession
from hearth2.session_inbox import SessionInbox
from hearth2.session_client import NamedSessionClient

target = NoticeSession("claude-laptop-review", "claude-review-session", "claude")
# origin, private_inbox_path and session_bearer are supplied by the caller.
inbox = SessionInbox(private_inbox_path, origin, target)
client = NamedSessionClient(origin=origin, target=target,
    token=session_bearer, inbox=inbox)
result = await client.poll_once()
records = inbox.records()  # Read only; understanding_state remains "unknown".
```

The operator must enroll this exact session/principal/recipient separately and
supply its own bearer credential. No real credential is read, created or installed
by this increment. The library does not infer an endpoint, inspect environment
credentials, launch a native client or start a recurring poll. A distinct bearer
subject remains the server's session authority; this is not measured OS process
identity or native Claude/Codex context ingestion.

The client permits a fixed HTTPS origin with default certificate verification,
no URL credentials/path/query/fragment, no proxy environment, redirects or browser
cookies. Responses cannot redirect its bearer elsewhere. A custom httpx transport
is an explicit trusted test/embedding hook; acceptance uses ASGI transport to the
actual temporary authenticated app, not a live remote/native session.

One call fetches one bounded inbox response and processes at most max_notices
(default10, range1..50). Responses are capped at256KiB; requests have5s timeouts
and the asynchronous network cycle has a30s cancellation budget. This is not an
OS-level hard kill guarantee for filesystem operations. more_pending reports an
unprocessed batch; the library does not recursively drain or automatically retry.

## Durable receipt boundary

The client checks intended session/recipient, requested notice ID, public body
fields and independently recomputed canonical SHA256, offer epoch/ID/time/sequence
before local persistence. It validates server receipt actor, session, recipient,
notice, digest and journal metadata before recording confirmed receipt. Invalid
responses are errors, not acknowledgements or inferred success.

The private SQLite inbox is bound to the exact canonical origin plus frozen
session/principal/recipient. Every operation rechecks that scope. It requests
private directory/file modes where supported; the caller must supply and protect
the private path and its ancestors. It is not physical filesystem provenance,
Windows ACL validation or encryption. SQLite uses full synchronous transactions.
No bearer credential is included in stored offers, bodies, receipt metadata or
client errors/results. Notice content itself can be sensitive and remains local.

A body is committed before sending ack. The same notice+digest is deduplicated;
changed content or conflicting local receipt refuses overwrite. The local states
are stored_unconfirmed and receipt_recorded; understanding is always unknown.
Neither state causes a task/run/claim/review/acceptance transition.

Receive request IDs are stable across restart, derived from origin/session/notice/
restore epoch. If the receive response is lost, the next pass reuses the original
server offer. If an acknowledgement commits but its response is lost, the local
notice stays unconfirmed. The next pass retries local uncertain notices before
new server summaries, even when the server pending inbox is already empty. The
original server receipt/time is then recorded. Server-retained first receipts
from an earlier offer/restore period are preserved, not relabelled fresh delivery.
A new epoch comes from a fresh inbox response; stale in-flight requests fail.
Authentication failures do not rotate credentials/rebind sessions or discard data.

## End-to-end acceptance

An authenticated controller posts a notice for fixture session A. Another session
B of the same agent finds no notice. A's new reusable client polls the actual
isolated HTTP app; the test inspects the local inbox at the acknowledgement boundary
and proves the exact body is durably stored while the server is still unconfirmed.
After ack, the human view shows receipt, the client inbox retains its body/receipt,
understanding remains unknown and work stays running. Task/run/claim/notice/attempt
tables do not change. Restart deduplicates the confirmed notice.

Two more app tests deliberately lose receive and ack responses, recreate the
client/inbox and verify one original offer and one original server receipt remain.
Focused defenses cover digest/identity mismatch, local storage failure, bad
receipt, response size/redirect/batch limits, response cookies and replaced local
scope. This is end-to-end local protocol/client acceptance through ASGI HTTP;
there is no TCP/TLS/native-session/production delivery proof or live deployment.

Native session invocation, real credential enrollment/lifecycle, OS availability,
large-inbox history scaling and model/context consumption remain separate work.
Existing observer/Commons jobs and900s/full-run inactive policy are unchanged.
