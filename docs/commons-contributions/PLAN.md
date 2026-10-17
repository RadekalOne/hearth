# Commons Contributions Implementation Plan

> For agentic workers: use superpowers:executing-plans to implement task-by-task. Native execution by Codex under Rad's October 17 work authorization.

Goal: bounded, authenticated shared-file contributions for all five Commons projects, without deploying or broadening ambient conversation authority.

Architecture: a standard-library Python store uses exclusive file creation and a serialized bare git repository with a fixed working tree. Existing authenticated MCP/REST handlers call the store. A reusable Node adapter supplies read tools and enables create only for a trusted authorized project mode.

Tech stack: Python 3.11+, git, existing FastAPI/MCP service, Node 20+, node:test and unittest. No new production Python dependencies, database or service.

Spec: G:/My Drive/AI Projects/Wishlist/docs/superpowers/specs/2026-10-17-shared-contributions-design.md. Rad approved the presented design by reauthorizing W0 and saying "I authorized work" on October17. Source base: 2c2788c, matching deployed hub.

## Global constraints

- New feature disabled by default; per-principal participant allowlist empty by default.
- No deployments, restarts, new credentials, paid model probes, runner changes or automatic agent wakes.
- Never overwrite an existing contribution. Corrections/results link to prior entries.
- Model cannot supply author, server time, filesystem paths or git commands.
- Preserve existing dirty runtime worktrees. Integrate via a separately testable adapter and activation guide, not by replacing their files.

## Review focus

- Concurrent/replayed requests: one committed entry and stable receipt.
- Interrupted git commit: no successful receipt or visible uncommitted entry; safe retry.
- Path/symlink and malformed IDs: no filesystem escape or reading arbitrary git objects.
- Reviewer/anonymous/unlisted caller: default deny even if a handler is invoked directly.
- Runtime claimed save: require real server receipt and deny writes in ambient mode.

## Task 1: File store

Create mcp/memory/commons_files.py and test/test_commons_files.py.

Interfaces: CommonsStore(root).create(author, collection, kind, content, source_refs, links, request_id), list(collection, cursor=''), read(entry_id, offset=0). Structured record envelope contains ID, trusted author, created_at, source_refs, links, content and sha256. Collection/kind pairs are explicit; content stays plain UTF-8 text so the five projects retain independent formats. Project-specific semantics remain W1-W4 work.

- [ ] Tests first: stable retries/conflicting retry, original+linked result, concurrent threads and processes, failed commit retry, stable paginated list, bounded read, invalid collection/ID/offset/link, byte limits, symlink refusal.
- [ ] Watch tests fail on missing behavior.
- [ ] Implement cross-platform process lock, fixed internal paths and serialized git publication. Reads use committed blobs only. Bare repository reflog explicitly enabled.
- [ ] Run store tests; verify real commit history and a failed transaction recovery.
- [ ] Commit tested store.

Limits: content 64KiB UTF-8; read pages 4000 characters; list pages 25; request ID 1-120 safe ASCII chars; 1-10 nonblank source references <=512 chars each; <=10 valid existing linked IDs. ID derives from authenticated author and request ID. Cursor pins a commit and last entry ID; reject foreign/unreachable commits.

## Task 2: Existing service integration

Modify mcp/memory/app.py, Dockerfile and package.json; create test/test_commons_api.py.

Interfaces: commons_files_list(collection,cursor=''), commons_files_read(entry_id,offset=0), commons_entry_create(collection,kind,content,source_refs,links,request_id). REST mirrors these under /api/commons. Existing principal supplies author. HEARTH_COMMONS_ENABLED false and HEARTH_COMMONS_PARTICIPANTS empty by default; human project managers may read after enabling, but create also requires explicit participant enrollment. Reviewer role denied for every new tool/route, including direct calls.

- [ ] Add failing tests for disabled feature, authenticated author, spoofed fields, anonymous/reviewer/unlisted calls, cross-site mutation, retry, read/list.
- [ ] Add handlers and bootstrap capability metadata; retain reviewer allowlists unchanged.
- [ ] Include module in Docker COPY and npm package files.
- [ ] Run store, HTTP/auth and existing reviewer tests.
- [ ] Commit service integration.

## Task 3: Reusable runtime adapter

Create integrations/commons/client.mjs and test/commons-client.test.mjs.

Interfaces: createCommonsAdapter({callTool, authorizedProject=false}) returns tools and call(name,args). Trusted launcher chooses mode; model never controls it. Advertise two reads in ambient mode and create only in authorized mode. Treat isError/malformed responses as failures, require canonical server author/time/hash/ID before claiming a save. Never turn conversational text into an operation automatically.

- [ ] Write and run failing behavioral tests for all five runtime identities using a local authenticated fixture endpoint, ambient denial, failed/malformed receipts and identity enforcement.
- [ ] Implement adapter using injected existing MCP callTool transport; no direct provider dependency or credentials in module.
- [ ] Add integration instructions for current Hy4/Kimi/GLM/Mavis/Codex surfaces; mark live adapter installation and model authored contributions unverified until activated.
- [ ] Run node adapter and full existing Node suite.
- [ ] Commit adapter and docs.

## Task 4: Verification and review

- [ ] Run all Python and Node tests, syntax/package checks. Report actual environment failures.
- [ ] Review the full branch for correctness/access/recovery defects; fix important defects with regressions.
- [ ] Prepare draft PR/release evidence and a disabled-feature rollout proposal. Do not claim W0 accepted or deployed until each real runtime's access and Rad's result/deployment gates pass.

## Execution ledger

Ruling: use a separate Hearth git worktree after native creation selected the enclosing AI-Projects repo; the unrelated managed worktree was archived unchanged.

Ruling: W0 provides validated typed envelopes and explicit collection/kind pairs, while W1-W4 own semantic field validation and ledger accounting. A common mandatory ledger schema would erase the separate wishes.

Ruling: proceed natively under Rad's explicit work authorization; no additional execution-method question is needed.
