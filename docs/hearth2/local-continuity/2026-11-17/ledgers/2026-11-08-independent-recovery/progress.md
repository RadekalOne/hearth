# SDD ledger — plan: docs/plans/2026-11-08-independent-recovery.md
BASE: 239b6b9f57706f55f2b1a11457b974f9a41891dc
Pre-flight: single task, journal API and existing legacy UI fixtures share recovery semantics. Historical fixtures must bypass only the public write path, never the authority guard.
Task 1: in progress. Direct RED observed: 10 tests, three expected subtest failures (both openers and legacy replay accepted).
Ruling: preserve all private evidence/workspaces per existing user preference. New workspace belongs only to this increment.
Task 1: HTTP RED observed: expected 409, actual 200 self-recovery. Guard added after epoch check and before lookup/replay. Existing UI legacy fixture now explicitly inserts historical audit data; permitted recovery uses supervisor.
Task 1: focused GREEN control10/2.181s API8/10.842s status17/11.410s delivery2/9.372s, exit0. One fresh reviewer PASS/no actionable findings; source review only, no fullsuite rerun. Principal independence does not verify references or actual health.
Task 1: full immutable offline1097 PASS179.164s actualexit0; SHA1cc6d812e441fd88782753b02d6ad1cbab1af882de30ad3428d76a37c6cbc573,102code/testfiles byteEXACT. Docs-only verification note after run. One fresh review PASS/no findings/no fix pass.
Task 1: complete. Signed LOCAL1b7cbd815b98401749cc8a8b7bd219ed3761dce2, clean/unpushed existing branch. Postcommit102code/testbytesEXACT. No activation/deployment; private evidence retained.
