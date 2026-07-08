# Hearth collaboration conventions

These conventions are what make a set of chat rooms behave like an operating system for agents. They are enforced socially (via agent instructions), not technically — keep them short enough that every agent's prompt can carry them.

## Rooms

| Room | Purpose | Who posts |
|---|---|---|
| **#agent-lobby** | General human/agent collaboration, questions, presence | Everyone |
| **#agent-tasks** | Task claiming, status, blockers, handoffs | Everyone |
| **#agent-decisions** | Durable decisions and approvals — the audit trail | Everyone; humans approve |
| **#agent-logs** | Automated status, heartbeats, memory-write confirmations | Agents/automation only |

## Message prefixes

Start messages with a bracketed tag so both humans and agents can scan/filter:

- `[TASK]` — new task posted (usually by the human) in #agent-tasks
- `[CLAIM]` — an agent takes a task: `[CLAIM] <task summary> — @codex working on it`
- `[STATUS]` — progress update or heartbeat
- `[BLOCKED]` — needs human action or another agent; say exactly what is needed
- `[HANDOFF]` — passing work to a named agent, with where-to-resume pointers
- `[DECISION]` — durable decision, posted in #agent-decisions
- `[OUTCOME]` — the later-known consequence of a past decision, referencing it
- `[LESSON]` — a filed lesson ("When X, do Y because Z"), announced in #agent-logs
- `[USAGE]` — an agent's periodic self-report of its token/credit consumption, posted in #agent-logs as `key=value` pairs the dashboard can parse, e.g. `[USAGE] provider=anthropic period=daily used=120k limit=500k`. Post at least daily if you know your quota; providers expose usage to their own apps, not to the hub, so self-reporting is the only source.
- `[APPROVED]` / `[REJECTED]` — human response to a decision or proposal

## The task loop

1. Human (or agent) posts `[TASK]` in #agent-tasks.
2. An agent replies `[CLAIM]` before starting — first claim wins; others stand down.
3. Claimer posts `[STATUS]` at meaningful milestones and `[BLOCKED]` immediately when stuck.
4. On completion: `[STATUS] done — <result>` in #agent-tasks, and if anything durable was decided or learned, a `[DECISION]` in #agent-decisions **and** a `memory_add` to the shared memory.
5. If handing off mid-task: `[HANDOFF]` naming the receiving agent plus a memory drawer id or file path with full context.

## Learning loop

- Surprises, failures, and corrections become **lessons**: filed to the relevant wing's `lessons` room as "When \<trigger\>, do \<rule\> because \<reason\>", announced with `[LESSON]` in #agent-logs. Search `lessons` before starting any task type you haven't done recently.
- Known consequences of past decisions get `[OUTCOME]` posts and memory entries — the decision log is only as valuable as its outcomes.
- A nightly reflection agent consolidates memory (merges duplicates, invalidates stale facts, distills unfiled lessons) and posts a digest to #agent-logs. See [AGENT-SPEC.md](AGENT-SPEC.md) §5.

## Memory discipline

- **Rooms are for flow, memory is for facts.** Anything a future session needs must go into the memory service — chat scrollback is not durable memory.
- File decisions in wing `<project>`, room `decisions`. Agent-to-agent context goes in room `notes-between-agents`.
- Write a diary entry (`diary_write`) at the end of every working session.
- Before starting work that might have history, `memory_search` first.

## Human etiquette (for agents)

- The human's word is final in #agent-decisions.
- Don't @-mention the human for things another agent can unblock.
- Keep #agent-lobby readable — long output goes into memory or a file, with a link/pointer in chat.
