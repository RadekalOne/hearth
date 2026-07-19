# Rolling out Hearth

This guide covers the shortest supported installation path and repeatable configuration for teams.

For a complete always-on VPS walkthrough, including DNS, Traefik, TLS, and backups, see [HOSTINGER.md](HOSTINGER.md).

## Guided rollout

Install Docker Desktop (or Docker Engine with Compose v2) and Node.js 20 or newer, then run:

```bash
npx create-hearth@latest
```

The launcher creates `./hearth`, checks Node, Docker, Compose, the Docker daemon, and the bundled files, then configures and starts Hearth. Choose another durable location with:

```bash
npx create-hearth@latest --directory /path/to/hearth
```

It refuses to overwrite an unrelated nonempty directory. Rerunning it against a directory it created refreshes packaged application files while preserving `.env`, `hearth.config.json`, `secrets/`, and Docker volumes.

After installation, run lifecycle commands from the deployment directory:

```bash
cd hearth
node cli/hearth.mjs doctor
node cli/hearth.mjs status
node cli/hearth.mjs agent add claude
node cli/hearth.mjs user add jane
```

## Unattended rollout

Keep secrets out of the deployment file. Save non-secret defaults as `deployment.json`:

```json
{
  "mode": "local",
  "serverName": "hearth.localhost",
  "ports": {
    "matrix": 6167,
    "element": 8009,
    "memory": 8010
  },
  "adminUsername": "admin",
  "adminPasswordEnv": "HEARTH_ADMIN_PASSWORD"
}
```

Supply the administrator password through the named environment variable and run:

```bash
npx create-hearth@latest --directory hearth --yes --config deployment.json
```

On PowerShell, set the secret only for the current process with `$env:HEARTH_ADMIN_PASSWORD = "..."`. Use your secret manager in CI or fleet tooling; do not commit the password or generated `.env` and `secrets/` files.

For `byo` mode, set `homeserverUrl` to an HTTPS Matrix homeserver and set `serverName` to the domain used in Matrix user IDs. Closed-registration homeservers still require accounts to be provisioned by their administrator.

For a public bundled deployment behind Traefik, add a non-secret `public` object. The proxy network must already exist before the installer starts Docker:

```json
"public": {
  "elementHost": "hearth.example.com",
  "matrixHost": "hearth-matrix.example.com",
  "memoryHost": "hearth-memory.example.com",
  "certResolver": "letsencrypt",
  "proxyNetwork": "hearth-proxy"
}
```

`elementHost` and `matrixHost` are required when `public` is present; `memoryHost` is optional. The installer validates hostnames, configures Element and the public Matrix URL, selects the Traefik overlays, and writes the public Memory URL automatically.

## Repeatability and recovery

- `hearth install` and `create-hearth` reuse a complete administrator identity and the four standard rooms instead of recreating them.
- `hearth doctor --json` returns structured prerequisite results for automation.
- `hearth status` checks the configured Matrix and Memory endpoints.
- `hearth down` stops containers without deleting volumes. Do not use `docker compose down -v` unless permanent data deletion is intended.
- Back up `secrets/`, `.env`, `hearth.config.json`, and the Matrix and Memory Docker volumes.

The npm launcher automates installation of the hub. Agent-specific MCP configuration is intentionally a separate onboarding step because each agent runtime stores its configuration differently; `hearth agent add <name>` prints the correct snippets without embedding tokens.
