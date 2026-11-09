# Named-session delivery acknowledgements implementation plan

> Execute inline with superpowers:executing-plans and TDD; one fresh final review.

**Goal:** Record receipt of an exact notice by its intended authenticated named session without inferring understanding or task completion.
**Architecture:** Optional explicit session enrollment maps each session ID to one distinct bearer principal and logical recipient. Controller notices explicitly target a session; server pins that enrollment and canonical notice digest in a separate audit event. Receive returns the body plus server-generated delivery ID; acknowledgement echoes that ID/digest. Journal receipt is separate from all task/run/claim/control state. No client deployment or real credential provisioning.
**Tech:** Existing Python/SQLite/FastAPI, immutable audit events and isolated authenticated application acceptance.

## Binding design
- HEARTH2_NOTICE_SESSIONS optional strict JSON: session ID -> {principal_id,recipient}; max128 entries, bounded canonical IDs, unique principals disjoint from human/controller/worker/observer roles; recipient is a configured human/controller/worker. Session bearer identity is narrow, not an agent-wide worker token; cookies rejected. Disabled runtime does not parse/create DB.
- POST /notices retains legacy notices. Optional notice.recipient_session requires configured recipient match; transport supplies a trusted frozen enrollment to Store.append_notice. Pin exact session/principal/recipient/body digest in server notice_addressed journal event. Payload delivery metadata cannot create addressing or receipt.
- GET /session/notices lists bounded pending notices for own pinned session only. It does not mark delivered. POST /notices/{id}/receive accepts request_id/expected_epoch, checks pinned/current enrollment, issues a server delivery ID and immutable notice body+digest. Receive alone is not acknowledgement. Identical request replays the original offer/time; no task mutation.
- POST /notices/{id}/acknowledge accepts delivery_id/notice_digest/expected_epoch. Only pinned session principal may acknowledge an existing current-period offer for exact body/session. No offer, other session (including same logical agent), wrong digest/ID, forged state or stale epoch rejects atomically. First valid notice receipt is durable/idempotent; repeated offers/acks never refresh its original timestamp.
- Historical receipts remain historical facts after restore; old in-flight receive/ack requests refuse. A new current-period offer may be issued under unchanged pinned enrollment. Session rebinding cannot inherit old intended-session authority. Legacy untargeted notices stay unconfirmed.
- Human status uses server address/receipt events only: Received by named session / receipt recorded; understanding unknown. Show intended session, actual receipt principal/time/digest/delivery ID/sequence and historical restore period. Reads do not acknowledge. Receipt never advances task/run/claim/review/acceptance state.
- This proves authenticated protocol receipt, not model ingestion, understanding, OS process identity, worker liveness or task completion. No actual credentials, provider/client/service, schedule or deployment changes; preserve inactive900s policy.

## Task 1: deliver and prove the increment
- [x] RED unit and real HTTP acceptance: target session discovers/receives/acks exact notice, same-agent other session denied, receipt alone leaves work running and understanding unknown.
- [x] Implement strict enrollment, addressing/offer/receipt journal, role/HTTP wiring and human status evidence.
- [x] Verify replay, atomic denial, restore, enrollment rebinding, forged metadata, content mismatch, bearer-only auth, no task changes and legacy compatibility.
- [x] One fresh final review, one fix pass if required, immutable offline full suite, signed local commit and search/write/readback remote HM outcome/checkpoint. Preserve private evidence; no push/deploy.


Verification:8 focused delivery tests PASS1.910s;3 authenticated HTTP/config
acceptance tests PASS7.428s. One fresh static read-only review found no actionable
findings (did not rerun tests). Full immutable Ubuntu24.04/Python3.12 offline suite:
1,119 tests PASS164.988s, actual exit0, external networking disabled/loopback only.
All109 checked code/test files matched the snapshot. SHA256:
71320feacb6f043fa4ba75f9ed1580d6e57d1a893e2a301ce9ee4c576b832378.
Local synthetic protocol acceptance only; no live session/client provisioning,
deployment or browser visual inspection claimed. Existing card styling reused;
actual HTTP human JSON/HTML assertions verify receipt semantics and evidence.
