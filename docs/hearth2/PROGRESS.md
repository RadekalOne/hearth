# Hearth 2 piece 1 preparation ledger

Plan: `docs/superpowers/plans/2026-10-27-hearth2-work-record.md`.

## Piece 2 broker foundation (28 October)

PR35 merged at `6b6987b42a8560c78f9c367560ea604d8e407ca3`, retaining the exact
Claude-passed `21cf340` tree. The record prerequisites are verified on merge.
Started `codex/hearth2-runner-broker` from that merged main in the same isolated
worktree. No production or persistent trial-runtime activation.

Implemented an inactive broker library and separate stateless read-only MCP app:
one ephemeral capability per broker, explicit wing/room, task/run/attempt/
generation/epoch/lease fences before and after every read, fixed initial expiry,
no HTTP mint/admin route, no upstream credentials in capabilities or exports.
The native adapter, root-only upstream adapter and service installation are not
part of this foundation. See `BROKER-FOUNDATION.md` for boundaries.

Broker tests observed RED then GREEN. Fresh internal review found one fixed
expiry/renewed-lease race across a database lock wait; independently reproduced
and fixed. All 389 Python tests pass on isolated trial Python 3.12 in 88.508s,
including 18 broker tests and actual MCP-client interoperability. This is not
Claude's independent project PASS or A4/A6–A9/N2/N3 acceptance.

Runtime source spike found pinned adapters requesting broad native permissions
and exposing managed delegation. Outer task context is not an enforced tool
allowlist. Asked Claude to review the root-owned launcher/protocol-shim boundary
before native work; native execution stays gated. Any unavoidable core patch or
pin change must come back as a concrete reviewed proposal before installation.
Current usage evidence remains an outside wait before live model acceptance.

## Piece 2 prerequisite record interfaces (28 October)

PR35 follow-up review: Claude independently reproduced acceptance of an old
in-flight failure recovery after restore. The follow-up requires the caller's
`expected_epoch` in failure writes and checks it before replay/CAS, matching the
tick fence. A real export/restore regression now checks rejected stale recovery,
unchanged history, then a valid fresh-epoch recovery. HTTP tests check missing
and wrong epochs. The two small findings use the reviewer-offered documentation
resolution: the configured-controller allowlist is an HTTP API policy, and only
latest-event/current-epoch failure replay is idempotent; older-event replay fails
closed and is now tested. Independent exact-commit re-review remains required.

PR34 merged into main at `5e892f905ebb0101dca6f9532663ffcc273545ad`, containing
Claude's exact passed commit `2ec3c49290174a3f5d1e6a8d5492a45b175ed3c7`;
piece 1 is verified. Piece 2 is started under the existing slice approval.
The six-point pre-build verification was posted and read back in the existing
HC review thread. Rad explicitly authorized direct project coordination there.
Claude responded with no interface objection, requesting a stale-card check and
an explicit outside wait for usage-page evidence; both are included.

The prerequisite implementation adds a human-answer transition, typed controller
ticks/standalone failures in the existing journal, and bounded timing settings.
See `RUNNER-RECORD-INTERFACES.md` and the 28 October implementation plan.
No schema DDL changed; v1 export includes the complete journal and answer history.
Internal read-only review found two regressions (old tick replay after restore,
and overstrict export validation of an unknown-exit reconciled failure); both
were independently reproduced and corrected. This is not Claude's PASS.

Current usage/seat charges remain unknown. Current usage-page evidence is an
outside wait before live acceptance and is excluded from the provisional 6–9
engineering days. Runner, broker, containment and real-model acceptance are not
delivered by this prerequisite. No native prompts, production deployment or
account/configuration changes were made. Independent exact-commit review and
Rad's merge gate remain open.

27 October 2026:
- Read canonical HM plan section, piece-1 handoff, isolation decision, approved
  agent rules v1.0, current repository source and migration/export/auth paths.
- Original worktrees contain unrelated edits; created a clean managed worktree
  at origin/main d04ea3d74e2409cbe0ba30410c30b01ce3727d4f; no originals changed.
- Existing H1 store regression command: `python3 -m unittest discover -s test
  -p test_work.py -v` -> 16 tests PASS. This is baseline evidence only.
- Trial SSH existing desktop identity rejected under strict host-key checking.
  Both registered Desktop Commander devices offline. No working alternate route
  located; no credentials, SSH keys, host permissions or production changed.
- Prepared source contract, interfaces, schema map, test-first implementation
  steps and A11 recovery rules. Application implementation tasks 1–6 NOT STARTED.
- Pre-flight: claims/runs feed export; restore must advance epoch before any
  old writer is accepted. Decision rows feed cards later; stored expiry is not
  phone identity verification. Notices/counts are fenced alongside closeouts.
- Ruling: separate H2 database in isolated trial memory-service instance instead
  of H1 work tables; required isolation favors preserving current semantics.
  Cost if wrong: later integration needs an adapter.
- Ruling: pending approvals restore held for human identity/revision rebinding;
  preserves intent as history without making an imported approval usable.
  Cost if wrong: an operator must explicitly reconcile extra pending cards.
- Pre-build Step 0 item 5 remains OPEN; no [VERIFY] PASS, no trial instance,
  no claimed task, no provider launch, no independent review requested.
- No new infrastructure/provider purchase made. Session seat usage/cost not
  measured; do not describe total engineering cost as zero.

28 October 2026:
- Rad installed the desktop public key on trial through the Hostinger console.
  Strict SSH succeeds and host identity matches the intended trial.
- Completed read-only live inspection; see PREFLIGHT.md for six-item findings.
  Cloudroom pinned 0.1.58 is active/loopback-only and authenticated health/ready
  respond200. Native accounts connected; no provider prompt launched. Worker
  cannot access core environment or Docker socket and lacks sudo. Catalog
  advertises gpt-6.1-sol; actual unattended compatibility untested.
- Live-check access blocker resolved. Task1 may start; execution gates for
  launching agents are not represented as passed by this preflight.
- Task1 implemented: explicit v1 schema, default-off initialization, checksum/
  version refusal, foreign-database refusal, atomic DDL, exclusive backup and
  loss-refusing down migration. Seven real SQLite tests observed RED then GREEN.
  Nonempty downgrade intentionally requires offline backup restoration.
- Tasks2–6 implemented in the isolated branch: immutable plan action manifests,
  explicit dependency gates, records/roles/expiring decisions, atomic claims and
  generation/epoch fences, three-attempt incident history, run evidence,
  independent review and human acceptance, versioned logical backup/restore,
  offline CLI and default-off authenticated REST integration. No UI or runner.
- Initial service verification had environment failures (WSL missing httpx/MCP;
  first isolated Python image omitted Git required by existing Commons tests).
  Installed dependencies/Git only inside a disposable trial verification image.
  Final Python 3.12 run on the trial host: 336 tests PASS in86.172s.
- Node24 check/test on the trial host:35 PASS,1 pre-existing skip,0 FAIL.
  Packaging dry run includes Hearth2 schema, API and both migration files. An
  initial packaging assertion had a shell quoting error; corrected standalone
  package verification succeeds. No production install or dependencies changed.
- Whole-branch read-only code review (Codex; NOT Claude's independent project
  PASS) found three Important issues: unbound task scope, no revision path,
  and no successful-held reconciliation. All reproduced RED and corrected GREEN.
  Added regression for stale-plan result acceptance as well.
- Review's restore-domain gap was treated as Important: reject inconsistent
  accepted tasks/claim/run histories even when a bundle's digest is recomputed.
  The impossible-accepted-task reproduction is now GREEN.
- Ruling: bind approval to an immutable action manifest; materialize each action
  once with its exact handoff/dependency gates. Required by bounded authority.
  Cost if wrong: planners must revise their plan to change/add action slots.
- Ruling: dependency gates distinguish output, independent review, human
  acceptance. Feasibility review consumes output directly, preserving A10's
  unattended path. This corrects the earlier blanket accepted-dependency rule.
  Cost if wrong: an incorrectly selected gate can block a downstream task; the
  gate is therefore visible in and bound by the approved action manifest.
- Reviewer set aside runtime subscription/process enforcement, canonical Claude
  independence and deployment: those are not inferred from record tests.
  General secrets in prose cannot be excluded by a heuristic; export validates
  known credential fields/patterns but is not a general DLP guarantee.
- Ruling: no extra secret-detection subsystem in this slice. Keep private backup
  handling and explicit bundle provenance; do not call heuristics exhaustive.
  Cost if wrong: an operator must detect/remove an unrecognized prose secret.
- Independent Claude review and fresh-container live service restore evidence
  remain required before piece1 is called verified. Pieces2–5 remain unassigned.
- Final A11 drill now complete on the trial host: separate clean restore
  container compared every table/link, refused the old claim, held active work
  and pending approval. A further container booted the actual restored service
  with fresh credentials; auth, build identity and credential-free re-export
  passed. Temporary fixture service removed afterward; no model launched.
  This is fresh-container evidence, not a new-VM or independent-Claude PASS.
- Actual Dockerfile build passed, tested application commit004b4c2200cd2a12a022331d264d7d5bd9e4597d.
  Initial unsigned pushes were rejected by GitHub's signature rule; used the
  existing Windows signing key and identity to sign only our unpublished
  commits, verified identical source tree, then pushed successfully. No rule,
  global Git config or GitHub credential/key registration changed.
- Draft PR33 created and attached: https://github.com/RadekalOne/hearth/pull/33.
  Piece1 IMPLEMENTED/READY FOR REVIEW, not VERIFIED. Claude review has not been
  requested through HC by this session; no agent messages or runtime launches.
  Pieces2–5 remain unassigned. Production services/schema/schedules unchanged.

28 October — independent Claude review follow-up:
- PR33 was merged by Rad, but Claude returned4changes, not PASS, in the review
  thread. Read and verified both full posts and their HM review record.
- Implemented all4 in one scoped follow-up: draft revisions no longer revoke
  task-bound approval; replacement approval explicitly supersedes; human waits
  and unknown exits never auto-retry; reconciliation preserves receipt end;
  strict integer revision, sanitized source metadata and live-only claim replay.
- Fourteen focused regressions pass. Findings1–3 observed RED→GREEN; minor fixes
  and delayed-containment variants also reproduced before their fixes. Initial
  regression expectations that treated drafts as supersession were corrected to
  require a human-approved replacement. One stale closed-claim fixture corrected.
- Full trial Python suite350PASS in85.190s; Node35PASS/1existing skip, syntax,
  compilation and whitespace checks pass. No schema DDL or runtime deployment.
- Follow-up remains unmerged for Claude's exact-commit review. No piece2 start,
  production change or new build approval needed. See PR33-REVIEW-FIXES.md.

29 October — broker component review clarification:
- Claude's reported missing httpx2 import was verified against the exact PR36
  test blob 1eaf2767b2d034ac7dd0a2e58c7aa43207451707. Unchanged SDK test
  PASSES offline in 0.794s. Installed MCP 2.3.0 explicitly requires httpx2>=2.10.0
  (installed 2.16.0); no import replacement or behavior fix was justified.
- CI 96 / run 40764669766 has 10 successful jobs including full Python discovery.
  Claude withdrew the finding in $HIA-jDVyDJPGLKgcazRe-ZSGdR6OEqKxH8ZTN2Zqeek,
  relying on the reported reproduction/metadata rather than an independent run.
- Added SDK dependency explanation and the two nonblocking review notes:
  memory_get scope is checked after upstream access; short writer transactions
  require future controller lock-contention checks. SDK test gets a comment only.
- All 18 broker tests on a tracked snapshot of this comment/doc follow-up PASS
  in 1.305s in a disposable Python 3.12 container with networking disabled. No
  native process, real memory credential, broker listener or production change.
- Billing review complete: both providers are premium seats. Rad retains
  Claude $75/month extra-usage cap after $22.18 seat usage; confirms ChatGPT 0 credits
  and auto-reload off. HM decision drawer_773843c44471103f3cd0f94acfc75cde;
  premium-seat clarification drawer_8b18ebb9cd9f3b7f03bc122f7c442dc9.
- PR36 remains draft/unmerged; piece2 STARTED. Native tool enforcement, process
  containment and full acceptance remain unfinished. Claude reviews this exact
  documentation/comment commit next. Rad retains the merge gate.

29 October — runtime containment spike (fixtures only):
- Claude component PASS at 271e1bd and CI 97/run 40920099176 success verified.
  Later unattended access-limit note did not retract the specific earlier review.
- Added opt-in exact-host/root-only trial probe and source-backed contract.
  Expected-failure parent-only termination leaves a setsid/SIGTERM-resistant
  descendant alive; independent cleanup confirms the fixture group empty.
  Cgroup kill then passes with independent populated=0 observation.
- Separate disposable container passes 12 filesystem/identity/network checks.
  Both runs removed their containers and cgroups; receipts remain private.
  No controller settings or services changed. No native CLI/model exercised.
- These are separate OS primitive checks, not a composed native launcher or
  task/attempt/restore/lease acceptance. Native tool policy and the exact
  provider credential boundary remain explicit open integration questions.
- Keep native launch disabled while resolving those questions with Claude.
  Preserve the pinned core and both premium-seat account settings.
- Fixed the prior two cosmetic documentation nits without runtime changes.

30 October - resumed implementation under existing approval:
- PR36 prior exact head 0cd86b6 has Claude component PASS and CI98/run40964744652
  success, independently refreshed from GitHub. No new user approval required.
- Added inactive durable DispatchRegistry over the existing audit journal:
  canonical run/claim/attempt/generation/epoch/model/deadline registration,
  one unresolved slot per database, one-use consume, restart/restore retention,
  and release only after the record has independent termination evidence.
- Tests observed RED for the missing registry and the probe's false observer
  check, then GREEN. Independent review reproduced a further restore edge:
  a closed run exported before slot release retained stale empty proof.
  Regression observed RED then GREEN; release now requires matching-run
  reconciliation after the latest restore. Reviewer independently confirmed
  the correction and all 10 dispatch tests. A closed pre-restore run with an
  unresolved slot remains conservatively blocked pending a dedicated recovery
  operation; this integration gap is explicit, not silently bypassed.
- Observer-outside evidence is asserted BEFORE termination. The fixture rejects
  the entire host account home, covering its native credential files. Future
  launcher must separately prove exactly one provider credential, no other
  account/core/controller/upstream secrets, and fixed-destination egress.
- Trial verification tag was absent; rebuilt its existing Dockerfile from cached
  layers. No service or account changed. Full Python 3.12 suite PASS:
  400 tests in 98.215s, disposable container, networking disabled.
- Updated real trial parent-only control expectedFAIL(exit1), cgroup kill
  PASS(exit0); both 12 container assertions PASS, observer checked live, cleanup
  empty verified. Receipts/logs private under
  /root/hearth-runner-trial/hearth2-dispatch-20261030-e9941c56.
- Native credential design/risk acceptance is resolved; gateway is optional
  extra hardening. Prior subjective 30/100 is not measured breach probability.
  Technical guards remain. MiniMax existing prepaid/gifted credits authorized
  for the bounded additional preliminary test; no purchases or recharge.
- No native model called, broker listener enabled, pin changed, production
  touched or PR merged. Piece2 remains STARTED. Native policy/egress, actual
  account guards, scheduler, alarms and composed acceptance remain unfinished.

30 October - native policy, account guards and approved direct-launch fallback:
- Implemented inactive native-policy validation and trusted account-observation
  guards, a preflight coordinator, atomic claim+reserve and receipt+release.
  A role change during account inspection and an occupied slot consume no extra
  attempt. Receipt/journal failures roll back together. Unknown outcomes hold.
- Test-first new regressions and independent component review completed. Review
  found an ambiguous Docker error being treated as absence in fixture cleanup;
  fixed with successful exact-name inventory checks and three regressions.
  Reviewer independently verified the fix. No raw native stderr is recorded.
- Full isolated trial Python suite431PASS90.300s, snapshot
  /root/hearth-runner-trial/hearth2-native-preflight-final-20261030-77c2d74d.
  Installed Codex0.154.0 and Claude2.1.280 startup/managed-policy fixturePASS;
  receipt native-policy-lvw5d10f. No native turns or real credentials used.
- Projection spike found pinned core's required bootstrap rejected by installed
  Claude. Hardened and unchanged-core argument controls both fail identically.
  The native-transcript success path is NOT passed. All own containers and run
  projections were verified absent. Failed responses remain private under
  projection-fixture-gjbw0qte and projection-fixture-gej6xhrw.
- Approved fallback now selected for BOTH providers: Hearth starts native CLIs
  directly; installed core/pins unchanged, core unused by Hearth2. Original Rad
  decision drawer_fcb3885641cd4b3a3d8849b269d690d9; Claude design confirmation
  $zhE8qBx2q7RG5Ni4uxplCSzT15ZalNYK8IIwQXn0N2M. Short source check found
  2.1.278/2.1.280 probe claims but no established working bootstrap version.
  Retain one receipt shape, clean environment, allowance-stop pause/no retry,
  exact model, unknown-usage handling and externally observed termination.
- Independent systemd deadline fixturePASS after submitting process exits:
  resistant child included, parent cgroup populated1->0, container exit137,
  guard Resulttimeout, elapsed5.156s for5s limit; cleanup verified. Receipt
  /root/hearth-runner-trial/deadline-fixture-5r0i9wri. Offline/no credentials.
- Final complete source snapshot hearth2-direct-fallback-20261030-dc1fb4fc:
  431 Python tests PASS in82.283s offline. Fresh focused reviewer41/41PASS,
  no further actionable component findings; root-only fixtures not rerun by that
  reviewer. AST and whitespace checks pass. Documentation-only refinements
  after this snapshot do not change implementation or fixture behavior.
- This is component progress, not installed runtime or piece2 verification.
  Direct native adapter wiring, collectors, fixed egress/scoped memory, actual
  forbidden-tool proof, absolute claim deadline/recovery, scheduling/alarms and
  composed native acceptance remain. PR36 stays draft, Rad retains merge gate.
  No new purchase, account/pin/production change. Usage cost remains unmeasured.

30 October - prepare and receipt recovery follow-up:
- Claude componentPASS c4a2849 (source inspected, no tests/CI rerun), with a
  nonblocking prepare recovery gap to close before adapter wiring. Reproduced
  post-claim failure, consumed-replay and successful receipt-retry failures RED.
- Original request/task revision is now bound in the dispatch journal. Matching
  prepare retries acknowledge the same live reservation; foreign task/owner,
  changed revision/policy/role, expired claim and unregistered claim refuse.
  Reserved acknowledgment has no fresh account evidence; consumed replay is
  already_consumed and cannot reissue launch authority or spend an attempt.
- Completed combined receipt/release retries require matching canonical receipt
  digest, typed claim identity, owner and current epoch. Conflicting receipts or
  restored claims fail without mutation. Held/unknown runs remain held.
- Added7 regressions and updated the prior successful-retry assertion. Fresh
  reviewer48focusedPASS/no actionable findings. Full isolated trial suite438PASS
  in84.842s, private source/log hearth2-preflight-replay-20261030-5c66901f.
- Read original Claude billing decision: explicitly retained creditsON under
  reviewed75monthlycap. Added source comment; no setting changed. Direct native
  broker config still must configure Hearth tools explicitly before acceptance.
- No native launch/activation/production change or merge. Piece2STARTED.

31 October - native output to authoritative receipts:
- Rad explicitly resumed. Clean basef344ad4, prior exactClaudecomponentPASS and
  CI101SUCCESS. Added bounded NativeStream with Codex/Claude root identity
  filters, nonfinite/duplicate/Unicode/depth/byte/record limits and explicit
  unknown usage. Claude query-model totals preferred; missing cache counts
  stay absent; native cost is estimated, never an actual seat charge.
- New record_native_result binds provider to claimed role and settles through
  the atomic receipt/release path. Unknown native output preserves actual exit
  and OS observations while holding task/claim. Typed auth/quota/budget stops
  atomically pause the role and journal its reason. Verified-empty known-exit
  stopped runs release the slot, but that role cannot consume another attempt.
  Recovery and logical restore both reject unknown-native success promotion.
- Test-first output/settlement tests plus independent component review. Review
  reproduced two important edge cases: malformed/coalesced tails dropped a stop;
  deeply nested JSON inside result text crashed receipt settlement. Four RED
  regressions cover both plus output-budget tails and related malformed-status
  validator error. Fixed in one pass;79focusedPASS. No repeat internal review.
- Final trial Python3.12 offline477PASS87.413s. Source/log:
  /root/hearth-runner-trial/hearth2-native-settlement-final-20261031-db2ca692.
- Actual Claude2.1.280 against fake loopback401/429 APIs in disposable network-none
  containers: initial no-intervention controls retried5/6times until20s timeout.
  Adapter now stops first typed native api_retry, exactlyONE local request for
  each status, exit-9 observed, no timeout, own cleanupverified. Final receipts
  claude-error-olqpnaiv andclaude-error-32vw5q_h; fake key only, no provider/model.
  Typed subscription rate_limit_event rejected mapping remains contract-tested
  only; no real-seat depletion, numeric allowance or actual charge is inferred.
- No schema DDL/bundle-format change. New native metadata requires matched
  controller/restore code; old binaries lack these semantics. Activation must
  pin code and verify stopped-controller/pre-change-backup rollback rather than
  assume binary-only downgrade safety. No active deployment in this change.
- Piece2STARTED/PR36draft/unmerged. Next direct native profiles/MCP wiring,
  account/config/credential collection, fixed egress, absolute claim deadline
  and lease/restart/revocation integration remain before composed acceptance.
  No real login, provider inference, production/pin/account change or purchase.

31 October - direct native profiles and actual broker interoperability:
- Added inactive fixed native profiles, no raw secrets/provider/helper override.
  Four profile tests observed RED then GREEN. Actual Codex initialization against
  the real broker exposed tools/list transport _meta.progressToken rejection.
  Two new HTTP regressions reproduced the gap; validated transport metadata is
  removed before tools/args/scope, never promoted to authority. Seven HTTP tests
  PASS, including the original SDK interoperability case.
- Installed Codex0.154.0 and Claude2.1.280 connect to actual scoped broker code
  with synthetic SQLite/upstream data in disposable network-none containers.
  Codex read forwards; Claude fake-local-SSE tool loop forwards one read and
  refuses requested memory_add/Bash. Both clients visibly refuse expired grants,
  zero upstream reads and one MCP call/no silent retry. Synthetic input/fake key
  only; no real login, provider call or billing inference.
- Poisoned-output fixtures catch feed AND finish RecordError, preserve auth/rate
  stop, terminate after exactly one fake request and verify own cleanup. Added
  actual-record regression for exception -> held task/paused role/retained slot.
- Final trial offline Python484PASS91.675s, source/log
  hearth2-native-mcp-final-20261031-42b941a8. Actual native final-source positive/
  expiry and401/429 poison-tail fixtures PASS. Independent component review33
  focusedPASS/no Important findings; privileged/HTTP evidence limits disclosed in
  DIRECT-NATIVE-PROFILES.md. Fixture header/doc refinements only after full run.
- Conditional design ruling: single bounded-run lease and fixed grant ending AT
  sealed deadline, no margin, only AFTER absolute deadline/delayed-start/restart
  proof. Existing900s defaults/live settings unchanged; no automatic grant
  extension. Every call still fences ownership/epoch/revocation. Actual auth/quota
  stops consume approved attempts, no refunds or limit change.
- Previous4ca51f3 has separate Claude componentPASS/source only and verified
  CI102SUCCESS. New component needs its own exact-head external review/CI.
  Piece2 STARTED, PR36 draft/unmerged; no activation, real credential/provider,
  account/pin/production change. Next absolute deadline/trusted late termination,
  real credential/settings collection, fixed egress and composed acceptance.

31 October - installed-client tool-policy follow-up:
- Claude2d5 componentPASS/source-only and CI103SUCCESS verified. Root-managed
  settings already disable Codex shell and explicitly allow Claude's read tools;
  profiles now repeat shell restrictions/empty HEARTH-filtered child env and
  Claude allowedTools so the intention is visible. Two strengthened assertions
  observed RED, all four profile tests GREEN. Shell refusal, not child env alone,
  protects against same-UID parent /proc environment reads.
- New Codex fake-local-Responses loop actually injects three shell variants plus
  read/write calls. Shell names absent including nested namespaces; all three
  unsupported, write refused, permitted read reaches synthetic model input, no
  marker/capability in stdout/stderr/model requests. Uses FIXTURE-ONLY custom API
  route/auth because installed native refuses overriding built-in openai. Normal
  ChatGPT profile discovery/expiry also rerun; no real account/inference proof.
- Stronger test exposed actual model memory read approval failure that control
  RPC had bypassed. Added truthful readOnlyHint/destructiveHint/idempotentHint
  to both broker tools; model read now works without broader approval policy.
  HTTP regression covers hints. Auth/scope/tool/lease enforcement unchanged.
- Full offline Python484PASS88.893s, source/log bc74f692. Later changes only
  strengthen opt-in fixture assertions; five native final-file cases PASS with
  SHA c031fb3895330920f5cabc5c2b75e4beef2e42a044becf24a27a47704713fa12.
  Receipts6gux0nbx/37uy7nfa/_jd2jijc/er7zuic_/velcnmzx; all cleanupverified.
  Independent review no remainingImportant; independently read prior synthetic
  tool outputs, not broad/final-rootfixture execution. Evidence precision and
  fake-auth/provider limitations detailed in DIRECT-NATIVE-PROFILES.md.
- No installed launcher, realcredential/provider, production/account/pin changes
  or merge. Piece2STARTED; absolute deadline/trustedlate recovery continues.
