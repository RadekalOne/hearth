# Atomic root recovery and slot release

Status: inactive in-process coordinator. No HTTP authority, OS collector or
launcher is installed. Existing approvals cover this isolated trial build.

RecoveryCoordinator requires an exact durable registration, current restore epoch
and claim generation captured by the trusted root controller before inspection.
Its packet contains an exact typed OS observation, a separately matching immutable
container absence observation, a bounded recovery ID and classification evidence.
Both observations must be no older than60s and not future. An empty cgroup alone
is insufficient: the container ID/workload and successful absence references must
match. OS proof must show verified empty and a known actual exit/end; unknown
exits cannot silently become retryable failures. No late worker closeout/usage
fields are accepted. First actual container identity and proof remain TRUSTED
COLLECTOR inputs; creation binding/OS validation still need implementation.

For active/held claims, one SQLite writer transaction records the trusted OS
observation, explicitly classifies failed/completed under the existing record
rules and releases the slot. Unknown native protocol cannot become completed.
A zero exit can be classified failed only with recorded native_state=failed.
Completed/observed/interrupted/unknown alone are not positive failure evidence;
a valid success cannot be turned into an automatic retry. Use OS-only observation to retain that
proof while held. A known nonzero process failure can be explicitly classified.
A previously valid native success can reach review; needs-decision stays a human
wait. Failure keeps attempt history/one incident and escalates at three attempts.
Role pause is not reset. Prior known end/exit and evidence history are preserved.
The Store and Dispatch helpers now have transaction-local implementations so
there is no unlock between proof check, receipt, reconciliation and release.

For a closed unresolved registration, in the same epoch or after restore,
recovery accepts ONLY preserve.
Fresh current-epoch OS/removal evidence goes into a new immutable recovery audit,
and the slot is released without changing historical task/run/claim/incident/role
rows. It cannot reinterpret an old task result. A changed task attempt or another
owner is refused. Cross-epoch release recognizes only matching current-epoch
recovery audit digest, registration sequence and actor from this transaction.

Exact committed recovery retries are read-only acknowledgments, even after the
original proof ages past60s; they do not create fresh evidence or launch anything.
A different packet/outcome/epoch is refused. Restore fences earlier requests.
An older OS observation superseded by later uncertainty cannot be replayed to
release. Recovery and release-journal failures roll back observation, task, claim,
incident and dispatch changes together.

This is the strict path intended for the future native controller. Generic legacy
Store.reconcile and ordinary dispatch release retain their earlier trusted-root
contracts for compatibility. This component does not claim every possible root
database call is now constrained by removal proof. Native activation still needs
actual controller wiring to the strict coordinator, durable immutable container/
guard/run/deadline identity, safe arm/consume/start crash/restart composition, real
account/settings/credential collectors/projection and fixed provider/broker egress.
Full-run lease policy remains inactive; existing900s defaults are unchanged.

Nine missing-coordinator tests observed RED before implementation. Eighteen
recovery cases now pass locally, including both restore modes, unknown exit, stale/
mismatched absence, wrong owner/context, no unknown-protocol success promotion,
success/human-wait preservation, three-attempt cap/role pause, superseded proof,
exact replay and failure rollback at recovery/release journal boundaries. Existing
observation/claim/dispatch/native-settlement focused suites also pass. Full source
verification and review results follow in the progress record.

Review coverage: a fresh reviewer read the complete recovery implementation,
Store/Dispatch integration and tests, plus surrounding branch/plan/spec context.
Ninety focused tests independently passed; no Important/Critical or new Minor
findings. This was deepest on recovery, not an exhaustive second audit of every
earlier branch component, and did not exercise real OS collectors or activation.
After review the implementer found unknown-protocol/zero-exit could be classified
as failure. Its new regression observed RED then GREEN; the single safety fix
keeps this uncertain instead of retryable. Eighteen recovery tests pass. No
repeat internal review is claimed; final full-suite evidence follows below.

Final offline Python3.12 verification:518PASS80.154s, immutable source/log
/root/hearth-runner-trial/hearth2-recovery-final-20261031-0d1a284a. Original
source.tar.gz SHA256
0d1a284a407420dd750b6af3d3426e7902a3bfc7851b58d5ad2febc21b921596.
Only documentation/ledger changed after this check. Exact-commit Claude review
and CI are separate from this implementation evidence. No prior native/OS
fixtures were gratuitously rerun: their executable paths were unchanged; new
coordinator behavior is covered by real SQLite integration/restore/fault tests.

## Successful-result protection follow-up

Claude's source-only b1d6b30 component PASS identified that completed/observed
zero-exit results could still be labelled failed and retried. The strict
coordinator now requires positive recorded native_state=failed for a zero-exit
failure classification. A valid successful closeout cannot be overwritten by a
failed classification. Its regression observed RED then GREEN; separate coverage
retains zero-exit positive-native-failure recovery. Legacy reconcile is unchanged.
The same-epoch closed-preserve behavior is documented and tested alongside restore.

Twenty-one recovery cases pass. Full offline Python521PASS84.236s, immutable
source/log hearth2-recovery-success-20261031-a0bb4c26, original source.tar.gz
SHA256 a0bb4c265a05b04039e932fef03775d34f1fa39b002e49e1ff239ad95fee5da1.
Only documentation/ledger corrections followed this full check. Prior b1d6b30
separately has source-only Claude componentPASS and CI108/run41219397183SUCCESS;
new exact-commit review/CI are separate. No activation or actual collector proof.
