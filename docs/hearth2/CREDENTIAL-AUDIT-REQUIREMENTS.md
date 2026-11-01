# Inactive credential audit requirements

`CredentialAuditRequirements` defines a private immutable policy artifact for the
future complete credential inventory. It is requirements only: no scanner,
consumer parser, inventory backend, absence receipt or start authority is added.
The assembly collector still requires actual independent complete inventory and
refuses when its credential backend is absent. This type has no `observe`/`scan`
method and does not implement that backend.

Version 1 pins exact image and native-assembly digest, separately audited complete
rootfs and consumer manifest digests, approved parser dependency closure digest,
audit authority reference and bounded source/byte/consumer/time budgets. These
references must come from independent enrollment/auditing; naming a hash or
reference does not establish actual completeness, parser support, credential
absence or physical provenance. No native provider/version semantics are guessed.

The JSON artifact has exactly the supported fields, canonical encoding, its own
content digest, private EUID-owned 0700 repository and 0400 no-follow regular file.
The frozen object validates the digest again, including deeply immutable limits.
Unknown fields, missing manifests, noncanonical JSON, booleans as numbers, zero
budgets, unsupported versions and scope-exemption switches refuse.

`require_scope` binds the original image/assembly and independently enrolled
inventory-policy hash. A nullable container requires image rootfs, environment and
native-consumer coverage. An exact immutable container ID adds container rootfs,
configuration, native consumers and mount sources. None can be omitted because
selected metadata showed no mounts or environment looked safe. Returning these
required family names is not evidence that they were inspected.

Budget maxima are 65,536 sources, 1 GiB, 64 consumers and 10 seconds. Reaching a
limit must make a future scanner incomplete/refused, never truncate to success.
Every actual source must be enumerated and classified by independently audited
supported consumer semantics. Unknown/unreadable/unscanned sources remain unknown.
The scanner must derive credential counts from actual measurements and provide
fresh complete bound evidence in both collector rounds; no empty counts/flags are
produced here. Audited manifests, parser implementations and their provenance,
full source acquisition and bounded scanner remain unimplemented/unconfigured.

Ruling: implement the policy contract as a bounded final pre-cutoff slice; leave
the full producer explicitly absent. The policy must not acquire the collector's
successful inventory schema or promote partial configuration into credentials:none.
Full independent credential/native/OS acceptance and the existing default inactive
900-second/full-run lease gates remain unchanged. Tests use private artifacts only.

Verification: eight missing-feature tests first failed (0.023s), then 29 focused
tests passed (3.346s), with eight direct tests passing (1.967s). One fresh final
review found no Critical/Important/Minor issues; its 29 focused and 10 additional
adversarial checks passed. No fix pass or rereview was needed. Full Ubuntu-24.04
Python 3.12 suite passed 790 tests (265.089s), actual exit 0. Immutable
`inventory-policy-review-source.tar.gz` SHA256
`3caf30a0af1bdcf7a185e33622f0b21990df4acb38758c12c2f580b446499a90`
matches new code/test files byte-exact; documentation alone follows. Durable
source is
`/home/rslabinski/.local/share/hearth2-laptop-verification/inventory-policy-20261101/source`.
Full tests reused existing dependencies/HOME/cache with only loopback enabled in
their network namespace. This is policy/source validation, not complete inventory,
consumer semantics, credential absence, physical provenance or OS/native proof.
