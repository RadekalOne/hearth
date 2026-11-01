# Sealed root guard entrypoint (not installed)

`guard_entrypoint.py` implements the existing future ABI: exactly
`--binding-json <canonical full original binding>`, bounded8192 UTF8 bytes.
Duplicate JSON fields, extra flags, noncanonical encoding and nonbinding or
credential-bearing fields refuse. Errors are generic and never echo arguments.
Default module invocation has **no runtime** and fails closed even as root.
A later installed, hashed root wrapper must supply trusted runtime configuration;
neither arguments nor ambient environment select host authentication, seal root,
daemon route, filesystem backend or evidence directory. No wrapper is installed.

`RootGuardBindings` stores a separate root execution seal BEFORE arming. The
original15-field binding, complete immutable layout manifest and original evidence
root are canonical and checksummed. The layout hash must equal binding.policy_sha256;
original host/run/container/guard/logical parent/creation epoch/deadline must match.
The evidence directory must already be private and owned. A new seal requires
binding.at <= trusted now < original deadline. This does not authorize create,
consume or start, and does not replace pre-arm artifact/native-policy validation.

The seal directory is private EUID-owned0700, files0400 regular/no-follow and
bounded16KiB. Nonblocking exclusive writer/shared reader locks serialize access.
Writing uses an invocation-owned exclusive temporary file, file fsync, no-replace
hard link, staging unlink and directory fsync before acknowledgment. A final file
survives a lost sync acknowledgment; only an exact same-content retry can confirm
it. A conflicting container/layout/evidence root cannot overwrite it. Capacity
reserves both staging/final slots; existing exact retries need no new slot. Failed
staging creation never authorizes deleting another invocation's temporary file.
Reads verify full binding, canonical encoding, layout and checksum and sync both
file and directory. Checksums detect corruption, not malicious root.

`RootGuardRuntime` requires numeric effective UID0 before reading a seal and again
before constructing the kernel port. It authenticates the original host through
an explicitly supplied trusted callback. Actual host-root privilege/capability/
namespace and authenticator provenance remain OS acceptance gates; injecting a
UID callback in private tests does not establish real privilege.

Runtime arguments must exactly match the root seal. Execution uses the sealed
layout and evidence location, not current controller DB state, restore-host
discovery, a changed policy repository or runtime-selected evidence path. It
refuses an early invocation without sleeping/rescheduling. At/after the original
deadline it composes `MappedCgroupFiles`, the existing bounded local daemon port,
`GuardEvidenceStore` and `RootKernelGuard`. It does not reread guard/native policy
artifacts before kernel termination: disappearance of that separate repository
must not prevent enforcing a valid already-sealed original binding.

The existing guard freezes and kernel-kills first, durably records original exit
facts before removing the immutable ID, then confirms absence and final empty/
frozen state. Post-kill failure retries kernel kill while retaining the frozen
parent/guard. CLI exit0 emits only `termination_state:observed` plus identities and
receipt references after confirmed guard completion. A never-started raw ExitCode0
is not a successful worker result. Nothing disarms, thaws/deletes the parent,
releases a DB slot, classifies a task, adopts an orphan or retries worker start.
Missing/corrupt seals, wrong host/UID, filesystem/daemon failures yield no proof.

This callable entrypoint and injected runtime are offline components, not a
configured executable/service or full create/arm/start driver. Trusted installed
wrapper/dependency closure, original-host authentication, root/ancestor/mount
authenticity, orphan/reboot/backup inventory, actual OS durability/deadline timing,
independent observer and native profile/credential/mount/egress assembly remain
gates. No partial configuration receipts become full launch authority. Default900s
and inactive full-run lease policy are unchanged. All tests use private regular
files/fake daemon ports; no real cgroup/daemon/service/worker is activated.

Relevant primary Python3.12 interfaces: [no-replace hard linking](https://docs.python.org/3.12/library/os.html#os.link)
and [fsync](https://docs.python.org/3.12/library/os.html#os.fsync). Actual host-filesystem
crash durability and installed wrapper/OS behavior remain separate acceptance.

Verification, laptop1November2026:12 missing-feature cases RED1.578s then
GREEN1.780s, plus4 seal/early-execution safety edges, giving16 new cases.
Implementer121 focused cases PASS19.152s. One fresh reviewer independently passed
121 focused cases78.729s and five additional injected edges5.653s, with no
Critical/Important/Minor findings. No fix pass or rereview was needed. Focused
counts are repeated executions, not additional unique cases. Both reviewer and
coordinator verified RSLABINSKI-PC and Ubuntu-24.04 UID1000/rslabinski; root UID
callbacks/private files are injected fixtures, not real privilege acceptance.

Final Ubuntu-24.04 Python3.12 full suite:710PASS245.916s, actual exit0, immutable
`entry-review-source.tar.gz` SHA256
`009c712f11919f7ddc4c5a687cfda18e79ee7a8183ff01d86b348cc7a3c889aa`.
Both changed code/test files match that source byte-exact; docs alone followed.
Durable WSL source is
`/home/rslabinski/.local/share/hearth2-laptop-verification/entry-20261101/source`.
Existing isolated project dependencies/HOME/official cache were reused; only
loopback was enabled in the full-test network namespace. Private archive, review,
RED/focused and `entry-full-python-offline.log` evidence remain in the plan ledger.
No actual daemon, cgroup, worker/provider, service, global configuration, account
or credential change. Source/injected acceptance does not establish actual OS,
crash/reboot, host authentication, installed wrapper/driver or native acceptance.
