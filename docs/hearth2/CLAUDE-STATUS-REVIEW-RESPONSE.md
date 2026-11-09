# Response to Claude's status-view review

Review source: `drawer_8174d687f36b5ed37c5d8e5f2b0f8a1a`, covering commits
4209950/a2d4fea/fc634c3. Claude passed those commits with one High to address
before acknowledgements or an outside observer. This follow-up reproduces and
fixes the immediate view issue and the three Medium items with regression tests.
It does not claim Claude has reviewed the follow-up commit or verified the
broader slice. No acknowledgement transport or observer is added here.

| Finding | Disposition |
|---|---|
| C1 self-reported recovery could appear as verified health | Reproduced. Failure read-model rows expose `self_reported = actor == target`. The card badges Self-reported, labels recovery as Recovery reported in a neutral style, and states it is not independent verification. |
| C1 authority enforcement for a real observer | Still a required gate: introduce distinct observer authority or prohibit self-recovery before relying on automated health/recovery. The journal rules are unchanged in this bounded fix. |
| A2 Running conflates claim with liveness | Shows Running (claim recorded), current-epoch/matching-generation lease expiry, current/expired/unknown lease state and Worker liveness is unverified. No task transition, stop, requeue or native probe is inferred. |
| C2 free-text references labelled evidence | Inspect record & supplied references separates recorded fields from Reporter-supplied references (unverified). Status JSON uses `supplied_references` and explicit provenance; existing journal APIs are unchanged. |
| F2 missing legacy state/lock | Independently rechecked pinned public source text. v2 map adds separate unscanned root `auth/auth-state.json`; root coordination `auth.lock` and `.lock` directory retain exact type/name recognition. No parser, acquisition or namespace grouping is added. |
| auth.lock.lock directory verification | Rechecked proper-lockfile's pinned `J` path and mkdir implementation; linked source correction retains bounded excerpts/pins. |
| Review says human bearer tokens are rejected | Corrected qualification: human browser sessions and human bearer tokens are supported; worker/controller bearer tokens are rejected. A dedicated HTTP regression exercises both supported human routes and controller rejection, including with a human cookie present. |

The acceptance test now uses a separate supervisor controller identity for its
supervision reports. That is still a controller role, not a distinct observer
kind or proof of independently enforced authority.

Deferred Low items: open-for age, age-number presentation and changing the
existing BEGIN IMMEDIATE read-transaction strategy. Those do not change the
reported-fact/provenance fixes. High-volume pagination and general corrupted-store
repair remain outside this small increment. No authentication, security settings,
production configuration, services, providers, room posts or automations change.

Verification: the High/reference reproduction failed before the fix, as did the
lease-expiry and legacy-map regressions. Final focused runs passed 17 human-status,
102 data-directory and two delivery/health acceptance tests. Browser inspection
confirmed the neutral Self-reported / Recovery reported card and unverified
reference section; mobile content fit its viewport. The immutable offline full
suite passed 1,094 tests in 174.434 seconds, actual exit 0, with external networking
disabled and loopback only. All 102 checked code/test files matched the snapshot.
No second reviewer or extra review loop was used for this author fix pass.
