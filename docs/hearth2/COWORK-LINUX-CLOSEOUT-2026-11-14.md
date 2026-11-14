# Cowork Linux review closeout — 14 November 2026

**Cowork's independent Linux recheck is complete and passed the intake/capacity-only scope.** Nothing is waiting on Rad or Claude for that gate. The non-blocking clock-dependent test finding is fixed in test-only commit `08e88c1b6e4bf22061d8fac4ebae022d4d537183`. Installed runtime `f13de43` and reviewed manifest `17ff37f50dcc2dffe0d8b33b933a68aefa679356c8de79930cb5464fb86aa8c8` are unchanged; the relay stays enabled and intake-only, with model/paid execution blocked and production unchanged.

## Confirmed source chronology

Claude @ Cowork's fresh Linux/Python3.13.17 run was05:57:35–05:58:53Z. The review was posted at05:59:39Z (**12:59a.m. ET**) in `$LIMRSPCz77TQ9rUNMDf5TiT3RI53wp-AaXMpHXVOZWY` and retained as HM `drawer_ab50e51c2398c8fa3a5e17a34870576a`. It verified the published manifest and configuration against the reviewed pins. The Codex monitor acknowledged it at11:01:18Z (**6:01a.m. ET**) in `$gnj0LkBr-ApLtcNTBghUc3z9Hg8JMXjz34HDHgyc4Tw`.

Cowork collected90 relay tests:89 passed and one clock-dependent assertion failed. It collected1330 full-suite tests:1275 passed,54 known Hearth1 environment/ProxyError errors and the same one test failure. There were no errors in Hearth2/relay modules. This is the independent scoped PASS; it is not represented as a completely green Cowork full-suite run.

The interactive statement that this review was still pending was wrong: it relied on stale state instead of refreshing the source thread/checkpoint. The source events and current checkpoints have now been reconciled. Historical pending records remain history, not the current verdict.

## Clock finding and fix

`test_fixture_allowance_cannot_pass_production_even_with_server_work_proof` constructed a Dispatcher without a clock. Outside the permitted07:00–23:59 ET window, it returned `outside_window` before reaching the allowance refusal that the test intended to check. Production behavior was correct.

The audit found another real-clock constructor in `test_live_mode_rejects_fixture_attestation_even_if_it_says_included`. That assertion could silently pass outside the window without exercising source refusal. Both constructors now reuse the fixture's fixed in-window clock; the neighbour also asserts the intended `idle` result. Every other unit-test Dispatcher constructor already supplies a clock. No production operating hours, operating-system clock or runtime implementation changed.

Before the fix, both assertions failed under a forced default clock of00:57ET. After it, both pass. All90 relay tests pass with default host clocks forced to overnight and daytime (12.350s and12.658s respectively). A fresh immutable credential-free, network-none Linux run with the default relay clock forced to00:57ET passed **1330/1330** tests (140.311s unittest, actualDockerexit0). Actual outside-controller timestamps:14:58:13.776840Z–15:00:39.018663Z. Source tree `4a8e3ac49334faf7be605b17db0f0a8273ca8b94`, archive SHA256 `d99dd9b528f9efe121773bc46eba84d05fbe74c31fa2e689657d4def2d9d7495`.

Post-fix reruns are Codex's tests, separate from Cowork's original independent result; no claim is made that Cowork reran the modified test commit. All309 trial baseline files remain unchanged and no test container remains. [Structured evidence](evidence/cowork-linux-clock-fix-2026-11-14.json).

## Scope retained

The existing intake-only installation, source/configuration pins, schedule, pause action and financial guards are unchanged. No reinstall, activation change, service rollout, merge, model turn, paid run or account/credential setting change occurred; application production remained unchanged. Understanding remains unknown and task completion is not inferred from receipt. Any proposal to let the relay do more than read requires Rad's separate approval; this closeout requests none.


## Follow-up review and operating-hours coverage

Claude's source-only follow-up `$qQCoNIC8hRSBsjDL2IdioNlgq-s4xJXkWPAZPii8brE` confirmed that `08e88c1` closes the clock finding. It identified one non-blocking coverage gap: no test directly exercised the operating-hours gate. This follow-up was requested formally as `[REVIEW]` after the earlier `[STATUS]` closeout had been seen but was not treated as a review candidate.

A new test injects UTC instants corresponding to06:59,07:00,23:59 and00:00 ET, in both standard and daylight time. It checks `outside_window` and no polling/claim outside the window, and polling inside. Existing correct runtime behavior passes all eight cases. Controlled always-open and always-closed guard mutations each fail four cases, confirming the coverage detects both failures; no production source or OS clock was mutated.

All **91 relay tests pass on Windows (13.894s) and network-none Linux (2.187s), actualexit0**. [Coverage evidence](evidence/relay-hours-coverage-2026-11-14.json) identifies the test commit and canonical source archive. This focused run does not relabel the prior1330-test full run as a new1331-test result.

Wording is now precise: the operating-hours guard permits07:00–23:59ET, while the existing17 hourly triggers are scheduled07:00–23:00ET. No schedule, installation, runtime, account, paid/model or production change is involved. The original Cowork intake-only PASS remains valid; this is test coverage, not a new activation or human-approval gate.


## Reproduce the overnight clock check

Follow-up source review `$0U7Kj8PYZRrzyl-EUHdUg1uxvk9DVamcsjsDPr0fT3k` also requested the clock-forcing mechanism. From the repository root in the test environment, run the Python code below (for example save it to a private temporary file and execute `python <file>`). Only the test process's `offline_relay.datetime.now` is patched to05:57UTC =00:57ET; fixture clocks remain explicit. The negative control removes the two explicit constructor clocks in memory while retaining the stronger assertions; it should report exactly two expected failures. No source file, installed runtime or OS clock is edited.

```python
import sys,unittest
from datetime import datetime,timezone
from unittest.mock import patch
sys.path[:0]=['test','ops/hearth2']
import offline_relay as relay
import test_offline_relay as tests
class Overnight(datetime):
 @classmethod
 def now(cls,tz=None):return datetime(2026,11,14,5,57,tzinfo=timezone.utc)
original=relay.Dispatcher
class MissingClock(original):
 def __init__(self,*args,**kwargs):
  if kwargs.get('acceptance') is False:kwargs.pop('clock',None)
  super().__init__(*args,**kwargs)
names=['test_fixture_allowance_cannot_pass_production_even_with_server_work_proof','test_live_mode_rejects_fixture_attestation_even_if_it_says_included']
for label,kind in [('fixed',original),('missing-clock negative control',MissingClock)]:
 with patch.object(relay,'datetime',Overnight),patch.object(relay,'Dispatcher',kind):
  result=unittest.TextTestRunner(verbosity=1).run(unittest.TestSuite(tests.RelayTests(name) for name in names))
 assert (result.wasSuccessful() if label=='fixed' else len(result.failures)==2 and not result.errors)
 print(label+': expected outcome verified')
```

### Final source-review closure and timezone prerequisite

Claude desktop and laptop closed the boundary coverage, trigger/guard wording and reproduction notes at `7847c4a` (HC events `$qif57BnU6EUFrUwfdLTxqkI_DbR8gZ_5Qi-kO3U7aHM` and `$ev1R2ubCZEubUArs6LhX3YmhBRxgFIvQ7esNEPsN_60`). Both were source-only reviews; neither claimed an independent test run.

Their remaining nonblocking portability note is addressed by requiring `ZoneInfo('America/New_York')` to load before the boundary test runs. Missing zone data now produces an explicit test-environment failure instead of silently exercising Windows host-local fallback. No runtime dependency or installed relay change. Windows module rerun: 20 passed; mocked missing-zone control: one expected prerequisite failure, zero errors. These checks supplement the earlier 91-test Windows/Linux evidence; no new full-suite or Linux rerun is claimed for this test-only prerequisite.
