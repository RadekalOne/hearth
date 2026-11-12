# Native turn and private Broker implementation plan

> Use superpowers:executing-plans inline, test-driven-development per task and
> one fresh-context whole-increment review at the end.

Goal: implement Claude conditions3–5 as inactive Python components and exercise
them with the existing credential-free, network-none walking fixture.
Spec: Claude drawer_ff38dcebac9a75cb3e448ac8c5f8f6c3 and revised entitlement
packet; Rad explicitly chose Build the three prerequisites11Nov.

Architecture: extend the serial RPC port with exactly one canonical turn bound
to its own safe thread, required root fence/audit/stop callbacks, bounded stream
handling reusing CodexTurn. Keep the Broker capability entirely in trusted root
memory: a per-run private Unix socket exposes scoped reads; the worker receives
only that socket, no bearer in environment/argv/config. Native loopback HTTP
bridge is a fixed protocol adapter, not an arbitrary credential/URL proxy.
Tech: Python3.12/Linux, existing Store/Broker/stdlib sockets and native0.159.1.

Constraints: exactgpt-6.1-sol, no provider/account/paid run, no service activation,
production contact, merge or frozen-inventory work. No billing/credential change.
No financial ceiling or fullRootLifecycleDriver/liveacceptance claim. Existing
v1 mount/stdio policy remains unchanged. Read-only model workload stays UID1000.

Ruling: continue the existing clean dedicated checkout on a new feature branch,
retaining ignored evidence and source history; no extra worktree/host handoff.
Ruling: a root-held token behind a private scoped socket avoids moving bearer
material into worker memory at all. This satisfies the purpose of private token
handoff without teaching the native client an unsupported token-file mechanism.
Only worker socket access for the one grant is exposed; trusted host root remains
trusted. Source directory0700/root-owned, only socket inode mounted into worker.

Review focus: bypass/override request fields; foreign/replayed native IDs;
pre-ack events and streaming floods; expiry/audit errors after dispatch;
socket permissions/lifecycle/revocation and no secret in public metadata.

- [x] Task1: tests RED then canonical one-use turn API, native IDs and bounded
  event reduction (>64 normal events passes, configured event/byte/time bounds
  fail; wrong fields/IDs, audit/fence failure, replay stop safely). Existing
  pre-turn control64 bound remains; no automatic retries. Files native_rpc.py,
  native_turn.py, test_hearth2_native_turn.py; targeted trial tests GREEN.
- [x] Task2: tests RED then root-private per-run Broker socket, exact MCP reads,
  fixed grant and safe cleanup/revocation. Shared tool descriptors, private Codex
  profile; worker bridge never handles a bearer. Files private_broker.py,
  broker_protocol.py, native_profiles.py, broker_http.py and private tests.
- [x] Task3: adapt walking fixture to production turn/socket components, remove
  private RPC bypass/token env, preserve explicit provider/upstream/OS stubs.
  Positive+missingcloseout and >64-event controls; exact thread/run/turn usage
  binding; prove Docker metadata/worker environment/token absence and real root
  stop/empty/removal. All synthetic counters labelled, charge unknown.
- [x] Task4: targeted suite and broader Hearth2 suite with isolated test-only
  dependencies; fresh source review, one RED→GREEN fix pass; exact-source native
  rerun when fixes justify it. Preserve source/evidence remotely and request
  Claude exact-commit independent review. Paid packet stays prepare-only.

Preflight: task1 stream result must match existing registry.native_result shape;
task2 MCP tools must retain readOnly annotations under never policy; task3 uses
only public turn API and fixed socket, not old capability environment builders.
Callbacks operate at dispatch under the same RPC lock. Root driver still owns
independent absolute deadline and cleanup; protocol completion is not OS exit.

Ledger: baseline55095c76c7023705f813be9aaa7356f68d5d419c; checkoutclean beforestart.
