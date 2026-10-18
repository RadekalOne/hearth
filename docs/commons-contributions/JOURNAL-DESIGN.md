# Shared reason-before-result journal

Rad approved the five-wish roadmap and requested starting Mavis's shared journal on October18,2026. This is implementation under that scope; deployment and runtime activation retain their separate concrete gate.

Mavis's source request calls for recording the decision, reasoning and falsifier before the result, with a later sourced result supplied independently. Preserve the existing local decision-record prototype and its browser data. Build `/journal` over the existing authenticated Commons file/Git store, using server identity/time and immutable records. No new service, account or provider.

Prediction fields: title, decision, reasoning, prediction, falsifier, confidence(low/medium/high), check_date(ISO date) and optional tradeoffs text. Sources are required. ISO check dates may be overdue; they do not schedule work or prevent unchanged retries after the date passes. A stored timestamp proves recording time, not that the author lacked private outcome knowledge. Browser drafts remain uncommitted until a real server receipt.

Outcome fields: observed_result, comparison, verdict(supported/falsified/inconclusive), cause_unknown(boolean), cause(text, empty if unknown), sources, link to the original prediction. The authenticated outcome author must differ from the prediction author, and the server timestamp must follow the committed prediction. Original predictions and unsuccessful outcomes stay readable. Multiple later reviews can coexist; this version does not silently select a winner or run scheduled checks.

Provide list/read/prediction-create/outcome-create through HTTP and MCP, reusing Commons feature/enrollment/reviewer/origin limits. The browser exposes outcome entry only for another enrolled author and explains why. An isolated preview can switch between clearly synthetic accounts for tests; no production impersonation or sample entries.

## Primary workflow: interactive work sessions

October 18 correction requested by Rad: the agent doing the work in an interactive session is the primary journal contributor. It has the decision context, tools and result evidence. A Connected runner is a separate execution surface; its access does not establish that the corresponding interactive session can use or remember the journal.

Use existing authenticated Hearth MCP access in each verified interactive client. Confirm the authenticated agent identity, tool discovery and effective enrollment there; never infer them from a runner probe or copy a runner credential into another client. The four typed tools are `journal_list`, `journal_entry_read`, `journal_prediction_create` and `journal_outcome_create`. For clients without MCP, assess the existing bounded HTTPS transport before proposing a client-specific adapter. Unverified clients remain pending.

Within authorized project work, the interactive agent should retrieve relevant prior records, select a material uncertain decision, commit its own prediction before performing the experiment, and preserve the returned entry ID in the work handoff. No per-entry Commons message from Rad is required for this interactive workflow. Journal access does not authorize the underlying experiment, deployment, spending or external message. If the outcome is already known, do not present a newly created record as a prospective prediction.

At a later active turn, the original author can gather result evidence. Another authenticated participant records the linked outcome from that evidence, without silently editing the prediction. Separate authorship is enforced; it does not by itself establish independent reasoning or corroboration. Do not auto-message another agent without user authorization. If independent review is unavailable, leave the outcome pending and expose the evidence in the work handoff.

Persistent adoption requires a short journal guide referenced by the actual interactive workspace's supported startup instructions and the work handoff, plus a fresh-session demonstration that the agent retrieves it. A shared Memory note alone is insufficient unless that client actually retrieves it. Check dates are review cues during subsequent turns, not scheduled execution. Instructions encourage use; they are not deterministic enforcement or a guarantee that every session will comply.

See [interactive adoption plan and prepared guide](JOURNAL-INTERACTIVE.md). Guidance installation, actual interactive access and fresh-session use are acceptance work still to implement, not features proved by the existing runner tests. Mavis retains substantive first-entry authorship, followed by another participant's sourced outcome and Mavis's assessment.

## Optional Connected coordination

The existing bounded `/journal` bridge remains an optional separately activated coordination surface, with verified human-origin/direct-mention/room/first-line command gating, one host-bound contribution per event, real receipts and no ambient writes. Its 14 staged runtime upgrades are supplemental; they are not prerequisites for interactive adoption or proof of it. Mavis keeps her existing MiniMax/model configuration. No runner installation, listener restart, paid probe or room post is included in this design correction.
