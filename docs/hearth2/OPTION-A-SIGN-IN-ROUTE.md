# Option A sign-in route candidate

The accepted Option A build keeps the original enrollment stopped. This follow-up adds a one-attempt sign-in gate and tests it on `srv2065995` with a disposable Docker container, a fixture certificate authority and a loopback mock. The candidate installs no service, real trust anchor or public listener. It has no transport that contacts OpenAI.

## Allowed and refused traffic

The pinned Codex 0.159.1 device-code flow makes three types of POST at `https://auth.openai.com`:

- `/api/accounts/deviceauth/usercode` with the fixed Codex client ID.
- `/api/accounts/deviceauth/token` with the device ID and user code returned by that attempt.
- `/oauth/token` for the authorization-code grant, with the same client ID, matching code and verifier, and exact device callback.

The gate checks the method, authority, exact path, media type, fields and attempt state before calling its transport. It forwards canonical bodies and no request headers. It refuses model paths even on the auth hostname, alternate destinations, tunnels, malformed requests, OAuth refresh and API-key token exchange. It never follows redirects. It closes after one exchange, an upstream error, 20 polls, or a 60-second time limit. The transport supplied by the fixture is bounded and points only to its own mock server.

## Trial test and rollback

- Run `python -m unittest discover -s test -p test_option_a_sign_in.py` for fake requests. The trial-only smoke test is `test/manual/option_a_sign_in_acceptance.py`.
- Use the Option A pinned image and pinned binary at `/opt/codex` with an unprivileged, read-only container, `--network=none`, `--cap-drop=ALL`, no new privileges, and disposable writable `/tmp`. Bind the Python candidate and proof script read-only. Set `HEARTH_OPTION_A_FIXTURE=1` and add a container-only mapping from `auth.openai.com` to `127.0.0.1`. Create a temporary test CA and DNS-matching leaf certificate for the local TLS gate. Bind them under `/fixture/tls` as `ca.pem`, `server.pem`, and `server.key`. Give trust to the pinned test client only. Keep those files out of host-wide trust and the enrolled workload.
- The proof runs real pinned device-code login and local login status with fake tokens. It counts only the three allowed requests at the local mock, and asserts that refused probes never arrive. It tests replay refusal after closure and the absence of direct network egress. Closing the gate and removing the proof container discard the fake auth cache and both loopback listeners. Remove the fixture private keys and verify that the original CID remains stopped in network mode none.

## Boundary for a later live sign-in

This test proves the gate can distinguish the pinned client’s sign-in traffic from model traffic in the isolated fixture. Live authorization still needs a separately reviewed host transport to the exact OpenAI auth origin, bounded TLS and no redirects, an isolated trust and secret-handling design, and Rad's approved device-code sign-in. Keep the real client without a direct route, do not assume an opaque HTTPS CONNECT proxy can filter paths, and keep the model data plane disabled. Run the independently reviewed account-status and workspace-binding check after shutting down sign-in egress. Nothing here authorizes a model request or the supervised turn.

Sources: [Codex authentication](https://learn.chatgpt.com/docs/auth?surface=cli) and the [pinned device-code implementation](https://github.com/openai/codex/blob/rust-v0.159.1/codex-rs/login/src/device_code_auth.rs).
