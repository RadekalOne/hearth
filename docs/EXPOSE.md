# Exposing Hearth to your team (reverse proxy + TLS)

By default Hearth binds to loopback: only the machine running it can reach anything. To let teammates use the hub from anywhere, publish **Element** and the **Matrix API** through a TLS reverse proxy. The overlay in `docker-compose.expose.yml` does this for [Traefik](https://traefik.io) (docker provider + Let's Encrypt), the most common self-host setup.

**What gets exposed:** Element (web UI) and Conduit (Matrix API — token-authenticated). Optionally the **memory service** too — it is bearer-token-authenticated (`hearth init` generates the admin token; `agent add` mints per-agent tokens), so remote agents can share memory. Set `HEARTH_PUBLIC_MEMORY_HOST=hearth-memory.example.com` in `.env` (plus a third DNS A record) and `hearth up` layers `docker-compose.expose-memory.yml`; the CLI refuses to expose memory if no admin token is configured. The dashboard (same host) prompts for a token.

## Prerequisites

- A server running Docker with Traefik already routing (entrypoint `websecure` on 443, a Let's Encrypt certresolver, `providers.docker` enabled).
- Two DNS A records pointing at the server (next section).

## DNS setup

In your registrar's DNS panel (e.g. Hostinger hPanel → Domains → your domain → DNS Zone), add two A records pointing at your server's public IP:

| Type | Name | Points to | TTL |
|---|---|---|---|
| A | `hearth` | `<your server IP>` | default |
| A | `hearth-matrix` | `<your server IP>` | default |

This gives you `hearth.example.com` (Element, the address teammates open) and `hearth-matrix.example.com` (the Matrix API that Element and remote agents talk to). Any two names work — just use them consistently in the steps below.

Notes:
- Propagation is usually minutes but can take up to an hour. Check with `nslookup hearth.example.com` (or `getent hosts` on Linux).
- **Add DNS records BEFORE starting the exposed stack.** If a Traefik router comes up while its hostname is still NXDOMAIN, the failed ACME attempt is not reliably retried — recreating the backend container sometimes works, but the dependable fix is restarting the Traefik container itself (it re-attempts issuance for every router missing a certificate on boot; expect a few seconds of downtime for everything behind it).
- If your provider offers a wildcard (`*.example.com`), that also works and no per-name records are needed.

## Steps

1. **Pick the server name before first boot.** It becomes the domain part of every user ID (`@jane:hearth.example.com`) and cannot be changed later without wiping the homeserver data. Answer the `hearth init` server-name prompt with your public domain (e.g. `hearth.example.com`).

2. **Add to `.env`:**

   ```ini
   HEARTH_EXPOSE=1
   HEARTH_PUBLIC_ELEMENT_HOST=hearth.example.com
   HEARTH_PUBLIC_MATRIX_HOST=hearth-matrix.example.com
   HEARTH_CERTRESOLVER=letsencrypt        # your Traefik certresolver name
   HEARTH_HOMESERVER_URL=https://hearth-matrix.example.com
   ```

   Also set `homeserverUrl` in `hearth.config.json` to the same public Matrix URL so agent/user onboarding prints public addresses.

3. **Point Element at the public API** in `config/element-config.json`:

   ```json
   "m.homeserver": { "base_url": "https://hearth-matrix.example.com", "server_name": "hearth.example.com" }
   ```

4. **Start:** `node cli/hearth.mjs up` — with `HEARTH_EXPOSE=1` it layers the overlay automatically. Traefik requests certificates on first hit; give it a minute after DNS propagates.

5. **Verify:** `https://hearth-matrix.example.com/_matrix/client/versions` returns JSON; `https://hearth.example.com` shows Element. Then `hearth setup` and onboard people with `hearth user add`.

## Security notes

- Port bindings stay on 127.0.0.1 even when exposed — Traefik reaches containers over the Docker network, so nothing bypasses TLS.
- Registration is token-gated (`HEARTH_REGISTRATION_TOKEN`); only the CLI (which knows the token) can create accounts. Don't share the token.
- Federation is disabled by default; your hub is not reachable by other Matrix servers.
- If you use a different proxy (Caddy, nginx), replicate the two routes: public host → `conduit:6167` and public host → `element:80`; the overlay file shows exactly what's needed.
