# Shared reason-before-result journal

Rad approved the five-wish roadmap and requested starting Mavis's shared journal on October18,2026. This is implementation under that scope; deployment and runtime activation retain their separate concrete gate.

Mavis's source request calls for recording the decision, reasoning and falsifier before the result, with a later sourced result supplied independently. Preserve the existing local decision-record prototype and its browser data. Build `/journal` over the existing authenticated Commons file/Git store, using server identity/time and immutable records. No new service, account or provider.

Prediction fields: title, decision, reasoning, prediction, falsifier, confidence(low/medium/high), check_date(ISO date) and optional tradeoffs text. Sources are required. ISO check dates may be overdue; they do not schedule work or prevent unchanged retries after the date passes. A stored timestamp proves recording time, not that the author lacked private outcome knowledge. Browser drafts remain uncommitted until a real server receipt.

Outcome fields: observed_result, comparison, verdict(supported/falsified/inconclusive), cause_unknown(boolean), cause(text, empty if unknown), sources, link to the original prediction. The authenticated outcome author must differ from the prediction author, and the server timestamp must follow the committed prediction. Original predictions and unsuccessful outcomes stay readable. Multiple later reviews can coexist; this version does not silently select a winner or run scheduled checks.

Provide list/read/prediction-create/outcome-create through HTTP and MCP, reusing Commons feature/enrollment/reviewer/origin limits. The browser exposes outcome entry only for another enrolled author and explains why. An isolated preview can switch between clearly synthetic accounts for tests; no production impersonation or sample entries.

Extend the current bounded runtime bridge for `/journal`, with verified human-origin/direct-mention/room/first-line command gating, one host-bound contribution per event, real receipts, and no ambient writes. Mavis keeps her existing MiniMax/model configuration and structured operation loop. Stage exact-hash runtime candidates against the active mention path and existing dirty checkouts. No paid probe or room post is needed for implementation checks. Mavis retains substantive authorship; another real participant must later record a sourced outcome and Mavis assess the artifact.
