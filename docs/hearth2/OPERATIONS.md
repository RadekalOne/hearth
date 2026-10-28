# Hearth 2 trial record: operator instructions

This branch is for the approved isolated trial only. Do not activate it on the
production host. Nothing in the worker rules substitutes for these controls.

## Configure the separate trial instance

Use the existing memory-service build with a new private data directory and
fresh trial credentials. Do not mount or import production memory, token files,
browser sessions or Cloudroom's core credential. Bind HTTP to loopback.

Set `HEARTH2_ENABLED=true`, a nonempty `HEARTH_MEMORY_ADMIN_TOKEN`, and explicit,
nonoverlapping principal lists `HEARTH2_HUMAN_IDS`, `HEARTH2_CONTROLLER_IDS`,
`HEARTH2_WORKER_IDS`. The lists contain authenticated principal IDs, not secrets.
The human list identifies the sole approver for the slice. Plans include an
immutable action manifest with the exact handoff and dependency gates per action;
the human decision binds its hash. A controller cannot add or rewrite an action
after approval. Dependencies explicitly select output, independently reviewed or
human-accepted results, so a feasibility review does not require premature human
acceptance. One requested revision can be resubmitted on the original task; a
second changes verdict stays with the human as a disagreement.

The human list identifies the sole approver for the slice. The controller needs
a separate token and can use it only as bearer auth; browser sessions do not
carry controller rights. A reviewer identity cannot mutate or export the store.
Workers have no management, claim, reconcile or export permission; their only
record mutation endpoint is an independently authenticated review. The broker
and worker launch grants are piece 2 and are not implemented by these tokens.

Startup refuses enabled mode without authentication or with conflicting roles.
Disabled mode never opens or creates `hearth2.sqlite3`. Existing Hearth 1 APIs,
knowledge export and stores keep their behavior. Hearth 2 routes are under
`/api/hearth2`; the existing `/api/export` remains drawer NDJSON.

The Docker image copies the `hearth2` package and migrations; npm packaging also
includes the package. All commands below run with the application's Python
runtime and `mcp/memory` on `PYTHONPATH` (or from `/app` in its container).

## Backup

Runner prerequisites (human answers, controller ticks/failures and short test
timings) are documented in [RUNNER-RECORD-INTERFACES.md](RUNNER-RECORD-INTERFACES.md).
They preserve the v1 layout and export all operational journal evidence. They
do not activate a runner or prove native model/billing/containment acceptance.

Authenticate as the configured human and download `GET /api/hearth2/export`, or
run this offline/local operator command:

```bash
PYTHONPATH=mcp/memory python3 -m hearth2 export \
  --database /private/trial-data/hearth2.sqlite3 \
  --bundle /private/backups/hearth2-work-record-v1.json
```

Destination must not exist. The export uses one consistent SQLite snapshot and
contains the whole operational graph, with counts, format/schema versions and a
SHA-256 corruption check. It does not contain authentication credentials, active
broker grants, browser sessions, or reusable claim secrets. Human inputs and
references remain sensitive operational data: store the file privately. A
checksum does not establish authenticity; verify who supplied the backup.

## Clean restore / A11

Stop the trial controller and any workload it launched; independently account
for old workloads. Work-record restoration cannot stop processes on another
host. Restore into a **new absent path**, using a known trusted bundle:

```bash
PYTHONPATH=mcp/memory python3 -m hearth2 restore \
  --database /private/clean-data/hearth2.sqlite3 \
  --bundle /private/backups/hearth2-work-record-v1.json \
  --controller-stopped
```

The switch is an explicit operator attestation, not an automated process check.
Unknown/malformed versions, damaged content, duplicate IDs, bad relationships,
unsafe credential fields and existing targets are refused. Staging validation
finishes before the new path is published. Restore changes the instance epoch;
all active work is held, stale workers are fenced, and pending approvals are
held for reissue against the intended identity/revision. Consumed decisions
stay consumed. Nothing resumes simply because a database exists.

Only the trusted controller can reconcile held work after verifying the original
workload is empty and recording references to that evidence. Workers cannot
self-certify termination. The source cgroup policy is not this independent
proof; piece 2 supplies the containment verifier.

## Migration way back

Version 1 initializes a new separate store. Unknown schema/checksum mismatches
fail closed. Forward/backward rehearsal on an empty disposable trial store:

```bash
PYTHONPATH=mcp/memory python3 -m hearth2 init --database /private/rehearsal.sqlite3
PYTHONPATH=mcp/memory python3 -m hearth2 migrate \
  --database /private/rehearsal.sqlite3 --target 0 \
  --backup /private/rehearsal-before-down.sqlite3
PYTHONPATH=mcp/memory python3 -m hearth2 init --database /private/rehearsal.sqlite3
```

Downgrading populated data to an empty version is refused. Preserve the backup
and, with services stopped, restore the previous known-good database/software
pair to a separate path. Test its contents and select that path explicitly.
Never force a down migration that silently removes work. This slice does not
migrate a production schema or authorize any change to Hearth 1.

## What has and has not been proven

Tests cover real competing processes, stale claim/role/plan checks, evidence
validation, failure histories, trusted human decisions, consistent export and
clean-process restore. A trial verification container exercises those contracts
on the actual host. This is record-level evidence: it is not proof of runtime
containment, subscription billing, phone delivery, an independent Claude PASS,
or seven clean nights. Those remain separate acceptance gates.
