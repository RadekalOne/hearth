# Implementation ledger

Approval: Agent Decisions $LJ9ZaK8yDQukhwz9A3NFZk-J0ZxSakFLaNQSO-qEk7U and $fdrNpNYGlDobY_8DySG4y1ypUV2LOOBT6aQGwlL0sbk. Base fd8d51b. Scope: signed branch/draft only, no actual account or credential provisioning.

Store tests failed for missing module, then passed: typed isolated identity, full scope only, hashed credentials/sessions, exact 24h TTL, generation revocation across stores/restarts and privacy-safe bounded audit.
API tests failed for absent store, then passed: enumerated default-deny mutations/unknown REST and MCP actions, human-session account administration, namespace separation and read access. Modern/legacy MCP exposed relay inbox own-agent read restriction; fixed only the full-scope reviewer read path, retaining write ownership checks.
Browser fixture found reviewer identity hidden at 400px; made typed role visible at that width, hid inbox mutation actions. 400/1280 browser fixture checks pass.

Fresh whole-branch review found invalid MCP bearer borrowing a reviewer cookie, revoked credentials falling back to legacy principals, and expired audit records visible without another write. Reproduced auth failures RED, fixed bearer-only selection and credential ownership tombstones (also login bodies and existing legacy sessions), added audit read expiry and cap/boundary tests. Reviewer independently ran 19 focused tests and direct fallback probes: PASS. Additional configured-human test RED then GREEN; review rechecked and PASS.

Validation: 164 Python tests PASS; 18 Node tests PASS; dashboard browser fixtures PASS; syntax and package dry run PASS, reviewers.py included. Dockerfile includes the module. Exact-head CI and Claude review are separate subsequent gates. No production auth changes or real reviewer provisioning.

Ruling: account creation is an operator-only provisioning seam rather than a new HTTP mint route, because credential delivery needs a separately approved protected env-file operation. Account listing/audit/revoke enforce configured human dashboard sessions; no admin bearer shortcut.
