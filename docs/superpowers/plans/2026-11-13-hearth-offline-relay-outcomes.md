# Relay recovery outcomes and renamed-host local safety

Base 1eda058, runtime bcdffb3. User asks to check Claude review and address findings; relay_c5e87bf0e5744dae deduplicates that work. Keep relay/control disabled, no activation/paid/merge/deploy/production.

1. TDD: renamed-host main still latches/stops local work/disables exact owned task; SSH alone refuses on mismatch; unknown arguments never become a pre-latch exit; malformed/ambiguous identity preserves latch_confirmed=true with pending cleanup.
2. TDD: default shortcut visibly reports paused/pending/refused; fixed timestamped outcome persists outside staged code, and independent read-only --status works with damaged stage. --json is explicit automated integration mode. No false success for UI/storage/state/stop failures. All unit OS/scheduler/UI effects mocked.
3. Explicit harmless Windows integration for renamed-host simulation (mocked hostname function only; OS name unchanged), and visible result dialog observation. Retain existing three integrity regressions; physical trial SSH only on the real approved host. No worker/model. Disabled-only profile refresh and prior history retained.
4. Full canonical-source network-none cached Linux suite; focused tests; one fresh-context whole-increment review as executing-plans requires. Important findings get one RED/GREEN fix pass. No implementation delegation.
5. Push feature branch, exact source/evidence review request in existing thread, search/write/readback HM outcome/checkpoints and resolve follow-up relay. Review, capability and activation/paid gates remain distinct.

Notes dispositions: SSH user config/known-hosts stay within declared owner-trust model and will be documented, not changed. Synthetic audit rows remain historical evidence; any clean-live-state choice belongs to enablement, no automatic purge. Ambiguous/malformed active records request pause/disable but require manual follow-up; no generic reconcile/adoption/retry feature added.
