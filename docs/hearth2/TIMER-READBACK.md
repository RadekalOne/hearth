# Original absolute timer readback

Status: inactive, TIMER-ONLY readback. Private fake busctl executables exercise the
protocol; no real system bus, timer, service or workload is activated or queried.

The protocol follows upstream systemd255 primary contracts:

- [D-Bus unit/timer interface](https://www.freedesktop.org/software/systemd/man/255/org.freedesktop.systemd1.html): existing-unit lookup, typed calendar/monotonic timer properties and realtime microseconds.
- [busctl implementation](https://raw.githubusercontent.com/systemd/systemd/v255/src/busctl/busctl.c) and [upstream protocol tests](https://raw.githubusercontent.com/systemd/systemd/v255/test/units/testsuite-74.busctl.sh): method replies wrap output arguments in an array; individual property JSON carries its actual scalar/array value and type. Multiple properties produce separate JSON objects.
- [Timer property implementation](https://raw.githubusercontent.com/systemd/systemd/v255/src/core/dbus-timer.c) and [calendar formatter](https://raw.githubusercontent.com/systemd/systemd/v255/src/shared/calendarspec.c): a calendar entry supplies its base, normalized specification and next epoch-microsecond value; fixed UTC dates retain six fractional digits only when nonzero.

These sources establish the implemented protocol contract, not the version or
behavior of an installed target. Unknown types/shapes/versions fail closed;
actual CLI/systemd compatibility and OS execution remain separate gates.

`SystemdTimerProperties` uses the bounded fixed local busctl transport. It issues
only `Manager.GetUnit` for the exact original guard timer/service and selected
`get-property` reads. It never calls LoadUnit, StartUnit, SetProperties, stop or
any arm method. Names are validated before helper execution; object paths and
property counts/types are exact. The JSON decoder rejects duplicates/nonfinite
values. No Environment, ExecStart or unrelated unit/property dump is requested.

`RootTimerReadback` verifies original host/binding, then checks two stable
snapshots before the sealed deadline. The timer must be loaded, transient,
active/waiting with a nonzero16-byte invocation identity; its original linked
service must be transient, loaded and inactive/dead without a prior invocation.
Aliases, reload/rearm identity changes and conflicting snapshots refuse.

The only trigger is the exact original absolute UTC calendar date/time and exact
integer epoch-microsecond deadline, with no float conversion or tolerance. No
monotonic/clock/timezone trigger, previous firing, persistent catch-up or random
delay is allowed. The expected timer accuracy remains the primitive's1ms setting;
this is not a production grace period or proof of scheduling precision. Time
must remain ordered, within60s wall/monotonic inspection bounds, and strictly
before the original deadline throughout the final check. Host is verified again.

The result says **timer_state**, not guard_state or container_state. It cannot
satisfy `CreationRegistry.consume_armed`'s full exact attestation. Guard executable,
root UID, service policy, cgroup placement, credential projection, resource limits
and actual stopped container still need independent verification by the concrete
driver before consumption/start. A matching timer alone authorizes no launch.

Root parent mapping and authenticated host configuration, service executable/
policy readback, arming/create/start, actual delay/reboot/orphan/old-backup and
outside observer/native acceptance remain open. Existing900s/default full-run
policy stays inactive. Tests prove typed private-helper contracts and refusals,
not actual PID1/daemon/OS containment or full-piece acceptance.

Verification, laptop1November2026:16missing-feature cases observed RED then
GREEN6.894s; an additional injected-snapshot bool/int coercion regression observed
RED before independent type validation fixed it.199focused checks passed34.509s.
One fresh read-only reviewer independently passed109distinct focused cases and
four additional ephemeral checks; no Critical/Important/Minor findings. The
reviewer also verified upstream typed JSON/timer/calendar source contracts.
Repeated timer cases were not counted as distinct checks; a reviewer module-name
typo was corrected separately. No actual daemon/system bus was queried.

Full Python3.12 suite:648PASS193.507s, actual exit0, immutable
`timer-review-source.tar.gz` SHA256
`2513abbd07c8df17d063eaa45b67c32ced583c37340d3a16d3a514c83ed2b210`.
Both changed code/test files were compared byte-exact; documentation alone
followed. Durable WSL source is
`/home/rslabinski/.local/share/hearth2-laptop-verification/timer-20261101/source`,
using the existing project-specific isolated dependency environment/HOME and
official Chroma cache in a network namespace with only loopback up. Private
archive, review, focused and `timer-full-python-offline.log` remain in the plan
ledger. Actual target version/privilege/host/OS/native acceptance remains open.
