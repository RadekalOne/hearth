# Native thread-launch integration, trial-only

Authority: Rad's 10 November continuation of concrete launcher integration;
Claude PASS drawer_8d3ca359b7f0b2504d8bd5a05f294ea5. Activation and paid turns
remain gated. Existing client-install/network-none exercise approval applies.

Ruling: preserve RootLifecycleDriver v1's no-mount/noninteractive policy. The
current candidate fixtures cannot be declared v1 OS lifecycle acceptance.
Implement the concrete root-side native stdio/thread adapter first, test it
against the real isolated client, and keep OS-driver composition explicitly open.
Cost if wrong: an additional reviewed policy/assembly step remains before a live
runner. Do not silently enable mounts, credentials, networking or provider turns.

1. Reproduce unexpected checker exceptions skipping audit; make them recorded
   guard_error refusals before transport without catching downstream exceptions.
2. Add a bounded serial stdio RPC client for initialize/model-list/thread-start
   only. Root generates request/session IDs; replies are canonical immutable
   bytes with receipt clock/monotonic stamp. No turn API or process factory.
3. Add the thread adapter: one attempt per instance; always acquire model/list
   through the live port; attach canonical response SHA256/RPC ID/session/time
   to each decision; refuse stale metadata; require a final trusted claim fence
   and recheck freshness immediately before native thread creation. No retry.
4. Add a root-only, bounded, no-follow, fsynced JSONL decision journal. An audit
   failure blocks transport. Corrupt tails/unsafe ownership refuse, never repair
   automatically. Human decision/card records remain separate.
5. Use tests first on trial Python3.12: protocol frames/IDs/bounds/timeouts,
   guard-error audit, metadata provenance/freshness, audit failure, final fence,
   single-use and separate setup/runtime failures. Run relevant existing tests.
6. Replace custom RPC/guard glue in a fresh credential-free network-none fixture
   with these actual components. Verify both catalogs, request refusals before
   thread creation, one exact positive idle thread, audit ordering and hashes,
   no turns, independent cleanup and unchanged scoped baseline.
7. One fresh-context source review of the completed active increment, resolve
   important findings, then send exact source/tests/evidence to Claude. Preserve
   all remaining real-broker/tool/expiry/settlement/bubblewrap/live gates.

Verification runs on srv2065995 only. New sources and synthetic fixture data may
be staged there, with no persistent service, account/credential change, provider
inference, production contact, merge or push. The credential inventory track is
frozen. No broad full-suite claim without a corresponding run.

Execution ledger: tasks1–6 completed for the native thread boundary;38 focused
trial tests passed, actual exit0. One fresh-context review completed, both P2
findings reproduced/fixed with regressions. Native fixture passed after one
disclosed harness-finalization failure/recovery and fresh rerun. Exact evidence
and remaining OS lifecycle limits: docs/hearth2/NATIVE-THREAD-LAUNCHER.md.
Claude's exact-source review is the next external gate; no merge/activation.
