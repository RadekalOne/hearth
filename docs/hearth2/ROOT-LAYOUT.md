# Immutable root layout policy (inactive)

This component resolves an original logical parent into explicit filesystem,
Docker and PID1 expectations. It installs nothing and grants no launch authority.
`RootLayoutPolicy` reads a private content-addressed policy artifact. Its exact
canonical JSON bytes plus newline hash to the existing binding's `policy_sha256`.
The artifact contains version1, original host ID, explicit backend, cgroup root,
PID1 control-group prefix, and hashes of the full native policy and guard artifact.
Those hashes pin expectations; verifying the referenced artifacts and enforcing
their policy remain separate driver gates.

The loader requires an EUID-owned0700 repository and0400 regular file, refuses
symlinks, bounds reads to8192 bytes, verifies SHA256 and exact canonical encoding,
and rejects unknown fields/versions/backends. The immutable Python value also
checks its content digest on construction. Production requires a provisioned
root-owned repository and independently authenticated original-host callback;
the library does not infer host identity from this artifact or a restored DB.

The binding's logical `hearth2-<hash>` parent and original creation epoch never
change. `direct` projects the filesystem basename below the explicit cgroup root; its
declared control-group prefix must separately be verified against the real mount.
The Docker parent must be the absolute declared control-group path: a relative
Docker parent depends on the daemon cgroup. See the primary
[Docker cgroup-parent contract](https://docs.docker.com/reference/cli/dockerd/#default-cgroup-parent).
`systemd-root-slice` supports only prefix `/` and projects to
`hearth2<hash>.slice`, with no dash. Systemd slice names encode hierarchy, so
blindly appending `.slice` to the old dashed logical identity would select a
different hierarchy. Nested systemd layouts and automatic discovery are refused.
See the primary [systemd255 slice specification](https://www.freedesktop.org/software/systemd/man/255/systemd.slice.html).

Projection accepts the original pre-create intent as well as the sealed binding,
allowing the policy to be selected before external creation. It cannot rebind an
existing record or authorize adopting a different restore-host mapping.
`MappedCgroupFiles` requires a sealed binding, retains an immutable copy, checks
the exact original context and host before operations, and translates only that
logical parent. Existing descriptor-relative no-follow file confinement remains.
The default `CgroupFiles` remains a direct backend. Guard inventory compares the
Docker parent with the mapped expected parent; release and termination collection
also check the mapped binding before their observations.

`verify_observation` validates a fresh (at most60s, no future time), typed
independent original-host Docker-parent/PID1-path observation and references.
Its `layout_state` result proves only a matching supplied observation. It is
neither full guard attestation nor proof of actual cgroup mount type, root UID,
service executable, policy enforcement, observer privilege separation, CLI
compatibility, stopped container or resource limits. Timer-only evidence likewise
remains insufficient. Actual OS, orphan/reboot/old-backup and native acceptance
remain open; no service or worker was activated. Default900s/full-run policy stays
inactive.

Verification uses only private regular files and injected daemon/host ports.
Tests cover pre-create/restore identity, explicit systemd and direct mappings,
policy/host/context mismatch, immutable constructor and artifact checks,
no-follow confinement, fresh layout observations, mapped guard success and
wrong-parent refusal with repeated kernel stop and no container removal.

Verification, laptop1November2026:14 missing-feature cases RED then GREEN2.119s;
constructor digest bypass separately reproduced RED and fixed; checksum/encoding
coverage added. Fresh review found one Important direct-Docker relative-parent
mapping defect, independently reproduced. Two implementer regressions then failed
before the single fix pass separated absolute Docker path from filesystem basename.
Final144 focused cases PASS38.539s. Reviewer109 distinct focused cases and four
new integration edges passed; the fifth independently reproduced the fixed defect.
Initial module-name loader errors were corrected and are not product failures.
No rereview is claimed. Actual host/OS/native acceptance was declined explicitly.

Final Python3.12 full suite:665PASS156.827s, actual exit0, immutable
`layout-fixed-review-source.tar.gz` SHA256
`014c09e9a24cd611c314d57913c39c60b5122404ebd6eb2dcc13bd249215d470`.
All four changed executable/test files match that source byte-exact; documentation
alone followed. Durable WSL source is
`/home/rslabinski/.local/share/hearth2-laptop-verification/layout-fixed-20261101/source`.
Existing isolated project dependencies/HOME/official cache were reused; the test
network namespace enabled only loopback. Private review, RED/focused logs, archive
and `layout-fixed-full-python-offline.log` remain in the plan ledger. Historical
pre-fix664PASS315.203s (31be27f6...) is not the final gate. No actual daemon/cgroup,
worker/provider/service, global configuration, account or credential changes.
