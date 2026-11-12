# D/E and interruption cleanup — 12 November 2026

Candidate response to Claude review `drawer_6aa3493f61c23d6f9d823b3cecfd1123`.
Prior A/C PASS and B-partial acceptance remain distinct from this changed source.
This is inactive piece2 code and synthetic tests; no live setup or paid turn.

D: denied private requests now return JSON-RPC2.0 errors with bounded parsed
string/integer IDs. Unparseable requests get a parse error and null ID. Errors
have fixed text/code; no raw envelope, grant state, credential or upstream error
is reflected. Unix and HTTP loopback checks cover expiry and malformed envelopes.
The pinned0.159.1 client also runs an actual synthetic refused-read control:
scripted provider requires seeing the matching tool error in its next request,
then ends the turn. The fixture gives this case a5-second turn budget, below
the old15-second tool timeout. Its actual native result is preserved; since no
memory read succeeded, trusted settlement deliberately records unknown/held,
not successful task completion. Positive and missing-closeout controls remain.

E: Broker reserves a finite read attempt atomically under its existing grant
lock, then performs upstream work outside that lock. Default8 attempts per
grant; root configuration accepts1–64 exact integers. Failed or forbidden read
attempts are not refunded. Metadata/live-authority checks do not consume the
read budget. Expiry/revocation still withhold a response after upstream returns.
Revoke/prune removes accounting; a worker cannot mint/reset a grant. This is
an ephemeral per-grant limit, not persistent cross-grant accounting, connection
rate limiting or a dollar cap. Trusted root could mint a fresh grant deliberately.
A concurrent12-caller/3-attempt test proves only3 upstream calls occur.

Cleanup: turn KeyboardInterrupt/SystemExit now invokes stop once, records fixed
interrupted cause and conservative send evidence, clears turn context and
re-raises the original control exception. Stop confirmation stays explicit;
a secondary interruption of cleanup cannot invent successful termination.
Thread/start is consumed before its first possible transport write; repeated
calls are refused, including after a failed first write, preserving owned thread
identity. Missing/uncertain thread response still needs external driver cleanup.

The live driver MUST provide an independent root cutoff covering the entire
workload and every child, including silence and interruptions. Event-driven
checks are not idle-period revocation polling. Callbacks remain trusted and
must be bounded. No new driver composition, service, monitor or timer is
installed by these components. Real-provider timing/live cutoff policy remains
unverified (B partial);45s ceiling and the inactive900-second policy unchanged.

TDD initially reproduced2failures/4errors across48tests. Final test counts,
source hashes, native run receipts and baseline/cleanup checks are recorded in
`evidence/broker-denials-budget-2026-11-12.json`. Independent review of this
exact candidate is required before treating D/E/cleanup as accepted. Paid packet
remains prepare-only: no scheduling, provider/account probe, account changes,
financial clearance or production activation is implied. Frozen inventory work
is untouched.

One fresh-context source review found an Important interruption gap during turn
lock acquisition. A regression reproduced absent stop/audit; one fix pass now
covers lock entry and exit, avoids duplicate cleanup, and uses conservative
possibly-sent/unknown-byte evidence if outer cleanup cannot reconstruct progress.
Tests also cover an interruption inside stop itself. The original exception is
preserved and uncertain stop remains false.105 final focused checks pass; prior
HTTP-inclusive isolated checks passed109 before this cleanup refinement. No
second review or new independent Claude PASS is claimed. Full/native final
results and exact-source hashes are in the evidence JSON.

Final network-disabled repository suite:1,240 tests PASS127.696s, exit0.
Final pinned-client synthetic controls:
`/root/hearth-runner-trial/walking-8bfca5f36e064c6299f4d9b81eefe836`.
Positive run_f9278038123c468fbb35c8132e7bdba7 enters review; missing-closeout
run_71c4e5c0c3c9452897e557263a515d46 returns ready with an incident; refused read
run_b0fcede7bf34403eb92c786d1ceddf5c completes its native error handling, while
trusted task settlement remains held with no successful memory read. All3exit0,
external root empty/removal verified, bearer absent, understanding unknown and
human acceptance false. Synthetic task-state changes only. The initial refusal
control took0.177s; the evidence JSON records the final exact-source measurement.

Canonical GitLF source b8d8fc12ee84c53c19b3d238904f37b8f8dda135 was checked
byte-for-byte against all15 runtime/test pins, then rerun: full1,240PASS134.006s,
exit0/networknone. Two CRLF checkout differences were the reason for this repeat;
no semantic change was hidden. The canonical native controls are in
`/root/hearth-runner-trial/walking-64a63e9aea924272a9e1cb730eec0e8c`:
positive run_66ca76a7dc134708af2ba1a2c1196046 review;
missing-closeout run_2e0cc124b35441c589b112c8483cb13f ready;
refused-read run_3f7cb36881b24d1a90334299b700e3ca held.
The refusal completed native error handling in0.242s under an explicit5s fixture
limit, with no successful read. All3exit0/outside-root-observer empty/removed;
309scoped baseline files unchanged, walking containers and private sockets absent.
These canonical receipts supersede earlier measurements for exact-source review.
No independently verified commit-signature or new Claude PASS is claimed.
