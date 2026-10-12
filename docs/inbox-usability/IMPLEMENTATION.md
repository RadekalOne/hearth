# Inbox usability slice

Human obligations now show a **What to do** block above their evidence: one to three everyday steps, what happens next, and who can explain it. Reassign moves waiting responsibility without transferring an execution claim. Dispatch gives work high priority and tells the human which session to open when an interactive agent is needed.

## Scope and compatibility

- This branch is for review only. It does not merge, deploy, provision reviewer accounts, alter machine schedulers, enable a notification consumer, or bump AGENT-SPEC 1.6.
- Typed coordination and browser responsibility actions use the existing default-off `HEARTH_COORDINATION_ENABLED` switch. Initialization adds `attention_actions` and `attention_audit` tables inside the existing explicit migration, retaining coordination schema version 1 and existing data.
- Existing source acknowledgement keys remain compatible until the item changes. Acknowledge never cancels work.
- Human `human_action` shape is `{steps: [one to three strings], after: string, ask: string}`. New human waits, handoffs and PASS/change-list transitions to a person require authored instructions. Legacy tag-derived items receive generic steps; their evidence is preserved.
- Expired claims retain their last lifecycle state. Failed continuation delivery remains available in `/api/relays` and also appears in the human inbox.
- Explicit current coordination obligations appear under the human inbox or collapsed per-agent sections. Reassigning a legacy attention item records its waiting party in the same coordination store; dispatch cannot erase that responsibility.

## Dispatch behavior

Dispatches are audited, bound to source revisions, and reported as **queued**. They never claim that execution started. Agents receive `attention_requests` at bootstrap; matching queued relays gain high priority in their inbox projection. An agent must inspect the source and existing authority before acting.

Interactive-only work cannot be sent to a background runner through Dispatch. A human can deliberately change the required surface with Reassign, with an audit reason. Where a recurring runner is declared, background work can wait for its next bootstrap poll. Without a declared runtime, the dashboard gives session-opening steps.

An operator may declare an **already existing** mention-driven runtime in its watcher registry with `dispatch_via_mentions: true`, `dispatch_room_id: "!…"`, and `matrix_user_id: "@agent:…"`. This branch enables none by default. The room must be observed and must match the item's source room when present. The human must supply a connected Matrix session whose `/whoami` identity matches their dashboard identity. The service posts a deterministic, structured mention as that human; no shell command, new runner or credential is introduced. Missing sign-in and failed wakes remain visible with recovery instructions. A posted mention is not proof that a runner began work.

## Sign-in recovery

Runner JSON checkpoint ingestion records `reason: "auth_expired"` for recognized authentication-expiry failures, preserving other receipt fields. Older stored text is classified on reads. The dashboard exposes the classification and process-result fields, not raw failure output. Multiple failed monitors for the same agent and physical machine fold into one sign-back-in item with all evidence links.

## Validation and review

Tests cover instruction validation, transactional reassignment and stale generations, peer-party preservation, human session/CSRF boundaries, current-source checks, dispatch priority and notifier identity, missing-runtime recovery, failed delivery, claim expiry, acknowledgement compatibility, and bootstrap inbox drain.

Browser fixtures cover Now, Work and Memory at 400px and 1280px, keyboard controls, stale-action feedback and WCAG AA axe checks. Screenshots here are **local branch fixtures**, not a deployed release. Knowledge metrics, lower-bound duplicate coverage, source links, light-theme colours and responsive layout are retained.

The independent whole-branch review found two P2 transitions: dispatch forgetting an earlier reassignment, and change lists failing for a human-owned plan. Both were reproduced with failing tests and fixed. The review was not a blanket PASS; these fixes are evidenced by their regression tests and the final suite. Claude's diff review and GitHub CI remain separate review gates.
