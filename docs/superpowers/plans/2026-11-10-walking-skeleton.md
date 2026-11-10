# Piece 2: credential-free walking skeleton (A4/A8/A9 shapes)

Authority: Rad's 10 Nov request. Trial srv2065995 only; no activation, paid
turn, production contact or merge. Prior work preserved at 0056dc2 on remote
codex/hearth2-minimax-consumer-parser; receipt pilot at remote 5ce9ffe.

1. Preserve current source and verify remote refs. COMPLETE.
2. Test-first fixture composition: real Store/DispatchRegistry/Broker, bounded
   one-shot poll, actual reviewed model/thread boundary, synthetic turn output.
3. Run actual 0.159.1 against a fake Responses provider on container loopback;
   real scoped Broker stays on root host. Return closeout on native stdio,
   settle only after independently observed workload termination.
4. Verify positive and missing-closeout controls; record source hashes, run IDs,
   real/stub map, cleanup, remaining replacement work; review and preserve remotely.

Ruling: this is an explicit fixture policy, not RootLifecycleDriver v1. The
unchanged v1 rejects interactive bind-mounted workloads. Docker network none,
bounded mounts, no real credentials; no service installation. A private Unix
socket carries only scoped MCP reads between a container HTTP bridge and root
Broker. Provider/login configuration is fixture-only; exact senior model remains
gpt-6.1-sol. Actual provider egress and account entitlement remain unproven.

Ruling: broker currently exposes memory reads only. Do not grant worker writes.
Root consumes bounded closeout over existing stdio and calls existing registry
settlement; identify this as a fixture output bridge, not a shipped broker-write API.

Ledger:
- Source preservation: verified remote 0056dc251639282b43639cc03c0ec2a2f4b6fe23
  and 5ce9ffefe09834fef763f22a9883adf97fe5380d. Existing runner branch 7e13418
  already remote. No merge.
- Composition: initial4RED →4GREEN. Native diagnostics isolated missing MCP
  readOnly annotations (client's never-approval restriction held); metadata
  regression RED→GREEN. Native positive and missing-closeout pair then passed.
- Whole-increment source review: Important setup/cleanup exception persistence
  and assert-based host authorization. RED regressions → fixes; unknown output
  stays held, cleanup attempts independent, host check explicit under -O.
  Expired receipt fallback RED→GREEN through unknown reconciliation. No second
  independent review claimed.
- Final:106focusedPASS3.306s;10 optimized controlsPASS0.528s; exact final native
  pair PASS in walking-cf1fb4d1c726419c9908e5b18f7275a0. Positive review, missing
  closeout ready+incident; actualexit0 and root empty/removal proof for both.
- Initial6failed diagnostic records reconciled unknown/held after fresh root
  container/cgroup absence checks; original receipts preserved. Broad suite
  attempted853tests/99errors (missingfastapi/httpx/yaml), no full PASS.
- All309 scoped baseline hashes unchanged; no walking containers remain. No
  activation, production contact or paid run. Detailed real/stub replacement map
  in docs/hearth2/WALKING-SKELETON.md; raw hashes in portable evidence summary.
