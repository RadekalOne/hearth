# Option A setup candidate

This candidate is for review and disposable tests on trial host `srv2065995`. The enrolled run `entitlement-20261116-01` stays stopped. Its receipt, configuration, and package provenance stay in place. There is no live deployment, scheduler, account login, provider egress, or model dispatch entry point.

## Private memory and rollback

- `DockerEnrollment` creates a disposable container with a unique proof label. It verifies the pinned image and the file hashes, mounts the exact private socket and loopback bridge, and retains the original read-only configuration and containment. The bridge listens only on loopback and the container has no network.
- The root controller uses `PrivateBrokerChannel` with `fixture_upstream`. The upstream reads only the pinned synthetic fixture and has no shared Memory access or credentials. The grant stays in the controller. The test verifies the exact search and get results, denial of writes, unrelated reads and scope overrides, and failed reads after revocation.
- The watchdog records the exact staging CID and arms before startup. Normal and failed-start cleanup revoke the grant first, remove only the owned staging CID, and confirm its absence before disarming the watchdog. If the controller exits, the independent watchdog attempts removal at 90 seconds and observes whether the CID is gone. A dead controller's in-memory grant is gone, and the watchdog can unlink the original socket inode after confirmed removal.
- Rollback keeps the original stopped CID and receipt. On an uncertain creation or cleanup outcome, inspect the exact staging label from the private receipt, verify ownership, and resolve it before another attempt. A Docker error or missing cutoff receipt is an unresolved cleanup. Do not change the original selector or start a staged CID with an uncertain outcome.

## Account-status boundary

- The staged transport uses the pinned native binary and a fresh, empty home in the same network-disabled container. Its only application request is `account/read` with `refreshToken=false`. The transport sends only the required local initialization handshake before that read. The test confirms signed-out status without using real credentials.
- `account_status` accepts a fixed, trusted transport and compares the expected binding with independently supplied controller evidence for the same session. It requires ChatGPT authentication, the pinned OpenAI provider, exact identity and workspace binding, and the Business Premium seat. It returns only verification flags. Fake cases reject absent or different workspace evidence, mismatched sessions, API keys, alternate or fallback providers, refresh, and model or thread methods before the transport is touched.
- A signed-in live binding is pending. The pinned native status gives auth type, identity and plan, so a later authorized task needs the privately confirmed Climate Central workspace ID and seat, Rad's approved ChatGPT sign-in, and an independently verified session-to-workspace binding. The binding objects cannot come from the worker or a request body. If the live sign-in needs networking, review an auth-only route with inference blocked, and close that egress before probing status. This candidate provides no egress policy for a signed-in provider, and its offline checks cannot establish the live seat, route or one-request financial boundary.

## Verification

Run `python -m unittest discover -s test -p test_option_a_setup.py` for fake cases. The opt-in `test/manual/option_a_setup_acceptance.py` is trial-root-only. Its inputs are the pinned bridge and the staged fixture and binary paths. `--outside-cutoff` adds the abrupt-controller-exit case and waits for the independent cutoff. It leaves the original stopped enrollment in place and sends no model requests.
