# Option A Climate Central sign-in route candidate

The accepted Option A build keeps the original enrollment stopped. This candidate adds an explicitly disabled host transport for one future, separately authorized sign-in on `srv2065995`. The test substitutes a loopback mock for OpenAI and uses a disposable, network-disabled Docker container and fixture CA. It installs no service, host trust anchor or public listener.

## Allowed and refused traffic

The pinned Codex 0.159.1 device-code flow makes three types of POST at `https://auth.openai.com`:

- `/api/accounts/deviceauth/usercode` with the fixed Codex client ID.
- `/api/accounts/deviceauth/token` with the device ID and user code returned by that attempt.
- `/oauth/token` for the authorization-code grant, with the same client ID, matching code and verifier, and exact device callback.

The host gate checks the method, authority, exact path, media type, fields and attempt state before calling its transport. It forwards canonical bodies and no client headers. It refuses model paths even on the auth hostname, alternate destinations, tunnels, malformed requests, OAuth refresh and API-key token exchange. It never follows redirects.

The live policy closes the Unix listener and removes its socket if there is no valid device-code request within **30 seconds of activation**. A valid request starts the **eight-minute sign-in window**. The independent **180-poll cap** limits upstream attempts even if the client polls too quickly. At a five-second interval the time limit comes first. Either limit closes the route, as do successful token exchange, an upstream error, or operator close. Tests move a fake clock to both expiry boundaries and exercise the poll cap without waiting.

## Host and trial-client boundary

- `live_sign_in_socket` is a context manager with explicit opt-in and an exact trial-root check. There is no launcher or default activation. The host owns the attempt, verdict and state in a mode-0700 directory. It exposes only the per-attempt Unix socket inode. Both directions use bounded frames and connection deadlines.
- The workload stays in `--network=none`. Bind the socket inode into the replacement staging container and feed it to `UnixSignInPort` behind its local TLS listener. The container-only hosts entry maps `auth.openai.com` to `127.0.0.1`. The TLS key and CA belong to this attempt and are given only to the listener and pinned sign-in process that need them. Keep trust out of the host-wide store, status process, other workloads and the original enrollment. Never publish the local listener or bind the containing socket directory.
- The host applies the full sign-in policy even if a worker calls the socket directly. The fixed transport uses only `https://auth.openai.com` and system TLS trust. It disables curl config and proxy fallback, uses a fixed User-Agent and content type and a bounded stdin body, refuses redirects, and imposes connect, total-time and response-size limits. It requires curl 8.4 or newer for streaming size enforcement. Device codes and token bodies never enter arguments, logs or review evidence.
- Supply the expected account email and canonical workspace UUID to the root host from independent evidence. Before releasing a token reply, the host checks whether the ID token from the verified TLS response carries the matching workspace, Business plan and email. This is a controller attestation based on the provider response. The gate does not independently verify the JWT signature or prove the Premium seat tier. A missing or mismatched binding closes the gate without returning the token reply.
- On context exit, the host writes a mode-0600 receipt in the per-attempt directory. It contains only fixed path and HTTP status counts, transport failure counts, and the binding outcome. The receipt contains no account identity, codes or token data. A rejected HTTP response can have both a recorded status and a transport failure. Preserve only this redacted receipt for review.
- Have the trusted operator confirm the canonical Climate Central workspace UUID privately. `login_command` and `login_status_command` force the same workspace and ChatGPT-only auth. Use a fresh mode-0700 ephemeral home and a clean environment. An official sign-in is a separate operator action. Run local login status on the same isolated home after closing both the TLS listener and Unix relay, with network still disabled. Native `account/read` with refresh false is a separate check for the account-status candidate. The fixture's signed-in app-server handshake did not complete within 15 seconds, so the test establishes local CLI login status only. The workspace and Premium seat require independent evidence.

## Trial test and rollback

- Run `python -m unittest discover -s test -p test_option_a*.py` for the fake cases and transport command checks. The trial-only smoke test is `test/manual/option_a_sign_in_acceptance.py`. Bind both sign-in modules alongside the script.
- Use the Option A pinned image and pinned binary at `/opt/codex` with an unprivileged, read-only container, `--network=none`, `--cap-drop=ALL`, no new privileges, and disposable writable `/tmp`. Bind the Python candidate and proof script read-only. Set `HEARTH_OPTION_A_FIXTURE=1` and add a container-only mapping from `auth.openai.com` to `127.0.0.1`. Create a temporary test CA and DNS-matching leaf certificate for the local TLS gate. Bind them under `/fixture/tls` as `ca.pem`, `server.pem`, and `server.key`. Give trust to the pinned test client only. Keep those files out of host-wide trust and the enrolled workload.
- The proof runs the pinned binary through TLS and the Unix relay with fake tokens. It checks the matching host binding and the private redacted receipt, counts only the three allowed requests at the mock, probes the host socket directly with denied inputs, and reads CLI login status after both listeners close. It verifies replay refusal, automatic idle socket removal, the absence of direct network egress and cleanup. Closing the gate and removing the disposable container discard the fake auth cache. Remove the fixture private keys and verify the original CID remains stopped in network mode none.

## Boundary for a later live sign-in

Before live use, have the exact candidate independently reviewed and separately authorize the staging enrollment, private workspace binding, and operator sign-in. Validate the host transport without granting the workload network access. Do not reuse the fixture CA or auth home. If the route fails, close both listeners, remove the exact staging container and its socket and trust state, and preserve or restore the original stopped enrollment and receipt. Do not retry an uncertain OAuth exchange. Live account, provider traffic and model traffic remain untested by this fixture. Keep inference blocked. The supervised turn stays on its own card.

Sources: [Codex authentication](https://learn.chatgpt.com/docs/auth?surface=cli) and the [pinned device-code implementation](https://github.com/openai/codex/blob/rust-v0.159.1/codex-rs/login/src/device_code_auth.rs).
