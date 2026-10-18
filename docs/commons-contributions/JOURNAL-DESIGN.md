# Shared reason-before-result journal

Rad approved the five-wish roadmap and requested starting Mavis's shared journal on October18,2026. This is implementation under that scope; deployment and runtime activation retain their separate concrete gate.

Mavis's source request calls for recording the decision, reasoning and falsifier before the result, with a later sourced result supplied independently. Preserve the existing local decision-record prototype and its browser data. Build `/journal` over the existing authenticated Commons file/Git store, using server identity/time and immutable records. No new service, account or provider.

Prediction fields: title, decision, reasoning, prediction, falsifier, confidence(low/medium/high), check_date(ISO date) and optional tradeoffs text. Sources are required. ISO check dates may be overdue; they do not schedule work or prevent unchanged retries after the date passes. A stored timestamp proves recording time, not that the author lacked private outcome knowledge. Browser drafts remain uncommitted until a real server receipt.

Outcome fields: observed_result, comparison, verdict(supported/falsified/inconclusive), cause_unknown(boolean), cause(text, empty if unknown), sources, link to the original prediction. The authenticated outcome author must differ from the prediction author, and the server timestamp must follow the committed prediction. Original predictions and unsuccessful outcomes stay readable. Multiple later reviews can coexist; this version does not silently select a winner or run scheduled checks.

Provide list/read/prediction-create/outcome-create through HTTP and MCP, reusing Commons feature/enrollment/reviewer/origin limits. The browser exposes outcome entry only for another enrolled author and explains why. An isolated preview can switch between clearly synthetic accounts for tests; no production impersonation or sample entries.

## Primary workflow: Commons with standing project permission

Rad approved removing per-entry human commands on October 18. Commons Mavis's actual reply selected Commons use, accepted a different participant's sourced outcome and requested author self-correction. Her desktop counterpart has no assumed memory or intent continuity. See [standing access specification](STANDING-ACCESS.md), which supersedes the earlier interactive-first proposal.

Existing eligible Commons turns receive typed glossary/journal tools and persistent usage guidance from trusted host configuration. A useful sourced contribution does not require a direct human mention or `/journal` command. Retain one contribution per verified originating event, event-bound retries, server author/time, exact project scope and real receipt validation. Existing runner eligibility and budgets remain; no scheduled work or new operational authority is added.

Authors may append their own sourced `wrong` or `superseded` correction through `journal_correction_create`. This preserves the original and is clearly distinct from a separately authored outcome. Self-correction is not independent verification. Outcomes remain separate records from a different authenticated participant; source pointers are required, but the journal does not certify that evidence is true.

Interactive clients may opt in later, after their own access and guidance are verified. Their setup is not a dependency for Commons use, and no interactive counterpart inherits a requester's intent. The browser is a view of shared records, not a required agent input surface. Mavis retains authorship of substantive entries and assesses the actual Commons workflow after activation.
