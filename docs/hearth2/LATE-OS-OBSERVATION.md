# Trusted late OS observations

Status: inactive controller library, not an installed OS collector or launcher.
Ordinary record_run/record_native_result still require a live claim and refuse
expired workers. Late worker output must not be smuggled through this path.

DispatchRegistry.observe_termination accepts only an exact current durable
registration snapshot, a current restore epoch and current claim generation
captured by the trusted controller BEFORE its outside OS inspection. The caller
must own the registration/claim and target its current attempt. A changed phase,
owner, generation, epoch, registration or workload is refused without mutation.
Restore increments held claim generations but retains original registration
identity; a new explicit current-epoch/current-generation observation is required.

The observation contains only a bounded logical observation ID, workload/immutable
container ID, observed/end timestamps, actual exit or unknown, containment state
and evidence references. No closeout, usage, role, success or new launch fields
are allowed. Observation age is at most sixty seconds, never future or before
run start; a known exit needs an observed end. Evidence is required for empty
containment. An arbitrary same-UID executable is not considered isolated merely
because the controller accepts this structure.

The first container identity and actual OS proof are TRUSTED COLLECTOR INPUTS.
This library neither proves the root inspection nor binds container identity at
creation. Future launcher must durably seal real container/guard/run/deadline
identity and verify the current epoch/generation before gathering proof. A later
observation cannot replace an already observed immutable container ID.

The method preserves prior known exit/end, closeout, usage and native protocol
history. Conflicting known exits are refused; an unknown exit remains unknown.
A missing native protocol receipt becomes explicit unknown. Active/held work is
held, with one incident/actual attempt history, and no role state changes. Closed
historical claims are refused entirely. This avoids rewriting accepted history
or degrading its export invariants. Closed pre-restore unresolved slots still
need a separate trusted recovery operation.

The OS receipt, held task/claim/incident and audit digest commit atomically. Exact
logical retries within freshness are read-only acknowledgments; conflicting IDs
or proof are refused. An identical retry after sixty seconds fails freshness
even if recorded; that conservative behavior does not refresh old proof. A fresh
observation needs a new ID and real inspection. All changes survive logical
export/restore, while old epochs cannot write. No HTTP/worker authority is added.

OS evidence alone never marks a task successful, closes a claim, resumes a role,
refunds/consumes an attempt or releases the dispatch slot. Explicit reconciliation
classification and current-proof release are separate. The current generic
reconcile method's epoch/freshness contract and restored closed-slot recovery
still need integration; this component does not claim to fix them by association.

Test-first coverage: seven missing-API cases RED then GREEN, closed-history
overwrite and immutable-container replacement regressions separately RED/GREEN.
Eleven tests cover expired receipt refusal versus trusted actual exit retention,
unknown OS state, replay/conflict, authority/registration/workload/epoch/generation
fences, freshness/worker-field rejection, export/restore, preserved known end and
exit, closed history and atomic journal rollback. Independent reviewer ran all
eleven successfully and found no additional Important findings; no real collector,
HTTP exposure or privileged runtime was exercised by that review. Full suite
verification follows in the progress record.

Final offline Python3.12 suite496PASS85.247s, private source/log directory
/root/hearth-runner-trial/hearth2-os-observation-20261031-b199a110. Original
source.tar.gz retained; SHA256
b199a11035ff2d51d0bd5e2e34c9c3c71605632bc8f5f048227e796bd80e1d26.
Only documentation/ledger changed afterwards. This library does not alter or
require rerunning the already verified native/OS fixture primitives.

## OS proof history follow-up

Every newly accepted OS observation now writes its complete bounded proof into
the immutable run_os_observed audit event, with the event actor/time and its
epoch/generation/registration digest. The run row remains the latest view, so a
later unconfirmed observation can conservatively replace current containment
without losing earlier proof references/provenance. Exact retries append nothing.
The same credential screening and payload bounds apply to journaled proof. This
is forward preservation; a digest-only older event cannot reconstruct already
discarded historical evidence. No active runtime was deployed with that version.

Exit status accepts the SQLite signed64 storage range, -2^63 through2^63-1, plus
unknown. Larger positive/negative integers raise RecordError before binding. This
is a storage/type guarantee, not a claim that every such value is a meaningful
Docker/OS exit. The future actual collector must enforce its process contract.
Four follow-up tests observed missing-proof/OverflowError failures RED then GREEN;
fifteen focused tests pass. Independent new-component reviewer ran all fifteen,
found no Important findings and verified the two-line diff/serialization safety.
No real collector or external authority was exercised.

Final follow-up verification: full offline Python500PASS89.933s, private immutable
source/log hearth2-os-proof-history-20261031-a32389a7, original source.tar.gz
SHA256 a32389a7231ff50d26e218d6b8bd3c58dbeadbd8f84b44d224c01a921382388d.
Only documentation changed after this check.
