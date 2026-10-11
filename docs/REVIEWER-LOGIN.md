# Reviewer login v2

This branch implements the approved full-read-only first slice. It does not provision
an account, deliver a credential, change production authentication, or authorize deployment.
Limited wing/room scopes are unsupported and rejected before an account is created.

Reviewer credentials and sessions live in a separate `reviewers.sqlite3`. Their identifiers
are `reviewer:<name>`; their role comes from an authenticated typed context, never a name
or the agent roster. Credentials and cookies are stored as SHA-256 hashes of random secrets.
Operator provisioning must use `provision_reviewer(name, credential, scope='full')`, which
rejects configured human/agent names and existing credentials. Credential delivery through
an approved protected env file remains a separate operator action. Use an independently
generated high-entropy credential; no HTTP account-creation route exists in this slice.

The dashboard accepts the credential in its existing token login. Reviewer sessions expire
after exactly 24 hours. Every request checks the persistent account enabled state and
credential generation. Revocation disables the account, increments its generation, deletes
its sessions, and retains credential ownership so it cannot fall back to a legacy principal.
This works across workers and restarts. MCP remains bearer-only.

REST access is an enumerated GET allowlist in `reviewers.py`, with narrowly scoped login
and logout exceptions. Unknown reads, every mutation, account/token/audit administration,
Matrix actions, work/relay claims, coordination transitions and Acknowledge/Reopen deny
before their handlers run. MCP has separate tool/resource and protocol-method allowlists;
discovery advertises only permitted reads. Both modern and legacy protocols are tested.
Existing human and agent authentication remain covered by regression tests.

The full scope includes all current corpus, dashboard counts, evidence/source inspectors,
Matrix observer reads, checkpoints, relays and bootstrap reads. Partial filtering must not
be added until all these paths consistently enforce a reviewed scope.

Human dashboard sessions can GET `/api/reviewers/accounts` and `/api/reviewers/audit`, and
POST `/api/reviewers/{name}/revoke`. These routes enforce configured human identity,
session validity and same-origin checks; a bare admin bearer is insufficient.
Audit records contain principal, normalized route and timestamp only. They exclude query
strings, bodies, credentials, record IDs and evidence. Writes prune entries older than
30 days and cap the store at 100,000 rows; reads also prune expired records transactionally.
No scheduler is installed. The audit and session stores use lazy request-time maintenance.

The UI explicitly shows the reviewer role at 400px and 1280px and hides inbox mutation
actions. Server enforcement is the authority. Fixtures and screenshots use synthetic
identities and credentials only.

Integration note: B continuation polls can mutate outbox state. If that branch is composed
with this one, reviewer bootstrap/relay reads must remain projections and must not drain
or deliver continuations. This branch is based on the flag-off A/C plus v1.6 release.

Validation covers namespace/scope rejection, all registered REST mutations, unknown routes,
all registered MCP writes, resource denial, protocol reads, exact TTL, cross-worker/restart
revocation, legacy-credential tombstones, invalid-bearer cookies, normalized audit retention,
configured human administration, packaging and browser layout.
