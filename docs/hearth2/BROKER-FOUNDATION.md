# Piece 2 broker foundation — inactive

This component supplies the memory capability boundary only. It does not start
a server, launch an agent, enforce native tools, deliver an outside alarm, or
establish subscription allowance. Piece 2 remains started and incomplete.

## Trusted controller API

`Broker(store, controller, upstream)` takes the trial work record, a trusted
controller principal, and a root-held callback `upstream(tool, arguments)` for
the isolated trial memory instance. The callback must return plain JSON, use a
fixed trusted destination with redirects disabled, and keep upstream credentials
outside the workload. This change does not supply or install that adapter.

`mint(controller, claim, wing=..., room=...)` returns a random 256-bit bearer
capability. Only the configured controller can mint or revoke, and neither
operation has an HTTP endpoint. The broker stores hashes of capabilities in
memory; nothing is persisted/exported. One active capability is allowed per
broker instance. The future controller must enforce one workload across process
restarts as well; this in-memory rule is not that durable process lock.

Each grant binds the claim's task, run, attempt, generation, restore epoch and
controller identity, plus an explicit memory wing and room. Reads consult the
authoritative claim/plan/role and time before upstream access and again before
releasing the response. Revocation or expiry during a read withholds its result.
Fixed grant expiry is the lease/deadline at issue: extending a claim lease does
not extend the grant. Rotate the capability explicitly after renewal. Expiry is
checked after database lock acquisition as well, so a lock wait cannot extend a
grant while its underlying claim has been renewed. Broker restart revokes every
capability; record restore or claim reconciliation also invalidates old grants.

## Worker read interface

`create_app(broker)` exposes a separate stateless MCP HTTP `/mcp` endpoint.
It supports initialize, tool listing and two read tools, with bounded request
size and strict JSON envelopes. The installed MCP client library is exercised
by the integration tests. An operator still must bind it to the workload's
private interface; the library does not open a listener. Do not expose it on
public HTTP. No browser/cookie authentication, admin, mint, restore, write,
arbitrary resource URI or destination proxy is exposed.

- `memory_search`: query and limit (1–10) only. Server injects wing and room.
- `memory_get`: one drawer ID; returned drawer must match the requested ID and
  authorized wing/room.

Responses are copied to a plain JSON snapshot, checked for scope and structured
credential fields, and bounded by the existing payload limit. Search releases
only matching result rows, never upstream global counts. Transport errors and
denials return fixed messages, not exception text or credential diagnostics.
Memory content and provenance remain untrusted evidence, not instructions.

## Verification boundaries

Fixtures cover scope/tool spoofing, no fictitious persisted secrets, one active
grant, revoke/restart/restore/lease/claim fences, revocation and expiry during an
upstream read, upstream bad scope/secrets, fixed-expiry database-wait regression,
HTTP authentication/no admin routes, malformed JSON/origin refusal, and actual
MCP client initialize/list/read interoperability. Native harness tool denial,
secret-file permissions, external network access, process containment, live
account allowance and A4/A6–A9/N2/N3 remain separate unpassed runtime checks.

## Runtime spike still open

The pinned core's Codex adapter requests `danger-full-access` and never-approve;
its Claude adapter skips permission prompts and exposes managed delegation.
Its generated command guard is not a root-owned fail-closed task allowlist.
Do not infer an enforced tool list from a prompt or an outer request. The next
spike must prove a root-owned launcher/protocol boundary with adversarial
fixtures while keeping the core pinned. If no supported boundary exists, return
a concrete minimal patch/pin-change proposal before installing it. No such
runtime change or native prompt is part of this component.

## Observed verification

Full Python suite on the isolated trial host, Python 3.12: **389 PASS in
88.508 seconds**. This includes 13 broker-core and five broker-HTTP tests,
including an actual installed MCP-client initialize/list/read exchange. No model
or real upstream memory credential is used by these fixtures. A fresh internal
review reproduced the fixed-expiry/database-wait race RED before the fix and
GREEN afterwards, then independently verified all 13 core tests and response
snapshot isolation. This is internal evidence, not Claude's independent PASS,
not an installed broker, and not piece 2's runtime acceptance.

Commands: `python -m unittest discover -s test -p 'test_*.py'`; focused
`python -m unittest discover -s test -p 'test_hearth2_broker*.py'`.
