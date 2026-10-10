# Coordination waiting store: A/C draft

This branch implements explicit responsibility state and transition tests only.
It does not merge, deploy, change AGENT-SPEC 1.5, create continuation relays,
activate notifications, provision reviewers, or change machine schedules.

`HEARTH_COORDINATION_ENABLED` defaults to false. Disabled startup does not
create, open or migrate `coordination.sqlite3`; mutations return 409, reads
return empty state, and bootstrap advertises the capability as false. The
existing work store and its prerequisite semantics remain unchanged.

For local/staging verification only, set the flag to `true` and configure
`HEARTH_HUMAN_IDS` with the human approvers. Application lifespan explicitly
initializes the versioned additive SQLite store under `HEARTH_DATA_DIR`.
Initialization is idempotent. Production activation needs a separate approval
and a backup of both operational stores. Disabling the flag retains the file
without reading or writing it; it does not remove historical records.

## Interfaces

MCP: `coordination_state`, `coordination_wait_set`, `coordination_answer`.
REST: `GET /api/coordination`, `POST /api/coordination/wait`,
`POST /api/coordination/answer`. Existing authentication applies; writes also
reject cross-site browser requests and anonymous principals. Credentials are
never passed inside coordination payloads.

The identity is `(work_kind, work_id, room_id, thread_id)`. `work_kind` is
`task`, `relay`, or `thread_plan`; room/thread IDs are mandatory. Task and relay
IDs must exist. Task owners are assigned agents; running task owners supply
their current live `claim_id`. Relay owners are their target agents. A thread
plan is owned by its authenticated creator. Human management principals can
manage task/relay waiting state. After a task reassignment, old answers are
refused until a human explicitly sets a new waiting generation, transferring
coordination to the task's verified current assignee. Former owners cannot
transfer it themselves. Previous owner/generation history is retained.
Task claim/owner validation holds the work SQLite write lock until the
coordination commit (lock order: work then coordination), preventing a
concurrent release/reclaim or reassignment. A coordination record does not
change work state or claims.

Every mutation supplies `expected_generation`, `source_event`, and `since`
(a timezone-aware ISO timestamp). Source event IDs and timestamps are
**caller-supplied provenance**, not verified Matrix evidence. There is no
automatic tag/text parser. A future event-ingestion adapter must verify
sender, addressed obligation and event relations before submitting answers.

Waiting parties have `kind` (`agent` or `human`), `id`, `required_surface`
(`interactive`, `background`, `either`), optional `expected_deadline`, and
optional `acknowledged_delay_until`. Agents must be registered; humans must
be explicitly configured and cannot also be agents. Stored rows include
`generation`, `source_event`, `since` and `state` (`pending`, `resolved`,
`cancelled`). The active `coordination_waiting_on` list contains only pending
rows from the current generation. `history=true` includes closed rows.

`coordination_wait_set` is owner/human-only. It atomically closes the previous
generation and creates the next one. Multiple parties remain separate.
Answer authorization matches the authenticated party, not a supplied sender.
Only the addressed human (or the existing admin management principal) can
answer a human obligation. Owner cancellation can close the entire cycle.

Typed answers require a nonempty summary and evidence references:

| `answer_kind` | Transition |
| --- | --- |
| `change_list` | Resolve the reviewer and return responsibility to the executor on an interactive surface. |
| `pass_needing_human` | Resolve the reviewer and wait on the configured `approval_party`. |
| `handoff` | Resolve the answerer and add explicit `next_parties`. |
| `final_completion` | Resolve only the addressed obligation. |
| `approved` | Human-only resolution of the addressed human obligation. Does not authorize deployment or execution. |
| `cancel` | Cancel the addressed obligation, or all parties when the owner/human supplies an empty `party_id`. |
| `ack`, `progress`, `reaction`, `unrelated` | No transition. |

New responsibility cycles advance the generation, fencing late old replies.
Other pending parties are carried forward with their original source, age,
deadline and acknowledged delay. Closed generation rows remain historical.
Replaying an identical already-recorded answer is a no-op; changing the
recorded answer under the same source event is a conflict. State and audit
records commit together under SQLite transactions. Every response reports
`grants_authority: false`.

Enabled work board/context reads expose `dependency_waiting_on` (an alias
of the existing prerequisite ID list) and `coordination_waiting_on` (party
objects) separately. The legacy `waiting_on` field is untouched. Bootstrap
projects the authenticated agent's pending obligations; relay inbox entries
include their pending coordination parties. UI labels and inbox separation
are the later D slice; no UI or spec activation happens in A/C.

## Verification

Real SQLite tests cover disabled file-system behavior, additive/idempotent
initialization, persistence, identity separation, multiple parties, scoped
answers, reviewer changes, human approval, cancellation, replay, generation
fencing and competing writers. ASGI/MCP tests cover auth/CSRF, claim fencing,
unknown/spoofed parties, malformed payloads, and prerequisite-only,
coordination-only and both-present projections. Existing Python, Node and
browser suites remain required before the draft is ready for human review.
# Continuation follow-up (B / spec v1.6)

The original A/C receipt below is historical. B adds continuations in the same
default-off SQLite store, created transactionally with waiting generations.
Typed substantive answers or explicit follow-up deadlines promote one deterministic
relay per work/thread/generation/poster through a persisted outbox. Bootstrap and
relay-inbox polls reconcile external delivery after crashes; cancellation and
supersession fence unclaimed relays. A delivered deadline relay receives updated
reply evidence when a later change list advances responsibility, without duplicating
the relay. Interactive claim is required and grants no authority. Continuation-origin
work cannot recursively create further continuations.

Spec/onboarding version is1.6. Notifications and the dashboard party split remain
separate follow-ups, advertised as unavailable. No scheduler is created by B.

