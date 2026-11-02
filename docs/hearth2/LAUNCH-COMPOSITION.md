# Root launch composition and conservative crash handling

Status: inactive Python coordinator with an injected trusted driver. There is no
concrete Docker/systemd driver, worker process, provider prompt or service wiring
in this component. All existing native/account/containment activation gates stand.

`LaunchCoordinator.launch(registration, claim, host_id=...)` composes:

1. `CreationRegistry.begin` commits a one-use creation intent before any external
   create. It seals the original host/run/epoch, deterministic guard/parent,
   deadline and policy. Replay never authorizes another create, even if no
   container was actually created or the intent acknowledgment was lost.
2. The injected root driver creates a stopped immutable ID and independently
   inspects original host, created state, parent, labels/policy and fixed deadline.
   Bounded exact identity and fresh observations are checked before binding.
3. The existing immutable binding commits, preserving the original intent. The
   driver arms that original fixed guard and independently inspects it.
4. Armed attestation and one-use dispatch consumption commit atomically through
   `CreationRegistry.consume_armed`. A final live claim/role/lease/epoch/deadline
   and exact registration/binding fence runs before calling driver start.
5. Start receives only the sealed root descriptor and immutable container ID.
   The method returns controller status, not workload completion or OS proof.

Descriptors carry no command, prompt, credential or worker-chosen policy path.
The driver must come from trusted root configuration. These Python interfaces
do not sandbox a driver or authenticate its observations. Fresh means no older
than60s, not future or before the corresponding journal commit.

SQLite cannot transact with the OS. Every ambiguous create/inspect/bind/arm/
consume/start failure propagates and retains the unresolved slot and any armed
guard. No finally block disarms, deletes an ID, adopts a same-name container or
retries start. A lost consume acknowledgment leaves launching held; a lost start
acknowledgment cannot duplicate work. An intent before any actual create may
therefore leave an intentionally held slot. Unbound orphan-intent inventory and
recovery are still an external acceptance/design gate; no safe automatic retry
is asserted. Backups predating intent/binding also require outside inventory.

The final DB fence is not an atomic OS start. The concrete driver and independent
root guard must enforce the original deadline at the actual OS boundary. A delay
after the final check must not allow a start after expiry: original immutable-ID
removal and retained frozen parent must prevent that race. Timer extension,
arbitrary current-host adoption, automatic rearming after restart and prompt
delivery without independent policy/account/egress/resource proof are prohibited.

`LaunchCoordinator.recover` captures exact current registration, restore epoch
and claim generation **before** asking the injected driver for independent
original-host termination and immutable-ID-removal observations. It calls only
`RecoveryCoordinator`, requiring an existing unresolved binding. No generic
reconcile/release or disarm fallback is present. Missing/unknown actual exit
remains held under existing strict rules. A new inspection after release is
refused; exact recorded-packet acknowledgment remains available through the
trusted strict coordinator or ordinary read status, never another launch.

No concrete root cleanup implementation is added. Before activation, the guard
must retry kernel kill after post-kill failure while retaining the frozen parent;
never disarm until independent empty AND immutable-ID removal on the original
host. Driver identity/privilege separation, partial OS-operation/reboot drills,
unbound intent inventory, matched-version backup/rollback, account projection,
fixed egress and native full-piece acceptance remain open.900s defaults and
conditional full-run lease policy remain unchanged/inactive.

Tests use real SQLite plus a synthetic stateful external inventory and injected
crashes, not Docker/systemd or native workers. They check intent visible before
create, guard/consume visible before start, once-only independent-process race,
lost intent/consume/start acknowledgments, partial create/inspect/bind/arm errors,
deadline/role changes after consumption, restore fencing, original-host removal
and strict recovery. Synthetic driver evidence is not OS containment acceptance.

Verification, laptop1November2026:18new missing-composition tests observed RED,
then GREEN3.105s;108focused implementer tests passed16.390s. One fresh read-only
review found no Critical/Important/Minor issues and independently passed72focused
tests57.309s, including the actual two-process one-create/one-start race. Three
additional ephemeral SQLite checks passed2.558s: epoch/generation changes during
recovery inspection refuse, and released recovery refuses before reinspection.
Older branch components received surrounding integration review, not another
exhaustive audit.

Full Python3.12 offline suite:557PASS238.027s, actual exit0, on immutable
`launch-review-source.tar.gz` SHA256
`f898097d32af4a54bbb461b8bfa67ddf3d334f965a594c796ddbaf141068d8c8`.
All three changed code/test files were compared byte-for-byte to that passed
source; documentation alone followed. Durable source remains in WSL
`/home/rslabinski/.local/share/hearth2-laptop-verification/launch-20261101/source`;
it reused the previous project-specific isolated dependency environment and
preloaded official Chroma cache, with only loopback enabled in an isolated network
namespace. Private archive, review, focused log and `launch-full-python-offline.log`
remain in the plan ledger directory. No real OS/worker/provider acceptance follows.
