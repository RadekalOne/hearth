# Deploy Hearth on a Hostinger Docker VPS

Hostinger's Docker VPS is a straightforward home for an always-on Hearth hub. Hearth needs a **VPS with Docker**, not shared web hosting. For a small personal pilot, start with the smallest Docker VPS that has enough memory for your other containers; for a multi-agent team or a VPS shared with other services, leave additional CPU, RAM, and disk headroom.

> **Referral disclosure:** [Get a Hostinger Docker VPS (new eligible users may receive up to 20% off)](https://www.hostinger.com/docker-hosting?REFERRALCODE=UVPJRADFGAV1). This is the Hearth maintainer's referral link; the maintainer may receive a reward, at no added cost to you. Verify the current discount and terms at checkout. You can also visit [Hostinger directly without the referral](https://www.hostinger.com/docker-hosting).

Hostinger documents its [Ubuntu 24.04 Docker and Docker Compose VPS template](https://www.hostinger.com/support/8306612-how-to-use-the-docker-vps-template-at-hostinger/). The steps below keep Hearth's application ports private and publish only HTTPS through Traefik.

## 1. Provision the server and DNS

1. Create a Hostinger VPS using the Docker template.
2. Point three DNS A records at its public IP:

   | Name | Purpose |
   |---|---|
   | `hearth.example.com` | Element chat UI |
   | `hearth-matrix.example.com` | Matrix API |
   | `hearth-memory.example.com` | authenticated dashboard and Memory MCP |

3. Allow inbound TCP 22, 80, and 443 in the VPS firewall. Do not expose Hearth's internal ports 6167, 8009, or 8010.

Wait until all three names resolve to the VPS before requesting certificates.

## 2. Install Node.js 20 or newer

SSH into the VPS as an administrator. The Docker template supplies Docker and Compose; Hearth's installer also needs Node.js 20 or newer. Follow the current [Node.js installation instructions](https://nodejs.org/en/download) and verify:

```bash
node --version
docker --version
docker compose version
```

## 3. Start the shared Traefik proxy

Create the external Docker network once:

```bash
docker network inspect hearth-proxy >/dev/null 2>&1 || docker network create hearth-proxy
mkdir -p /opt/traefik
cd /opt/traefik
```

Save this as `/opt/traefik/docker-compose.yml`:

```yaml
services:
  traefik:
    image: traefik:v3.3
    restart: unless-stopped
    command:
      - --providers.docker=true
      - --providers.docker.exposedbydefault=false
      - --entrypoints.web.address=:80
      - --entrypoints.websecure.address=:443
      - --entrypoints.web.http.redirections.entrypoint.to=websecure
      - --entrypoints.web.http.redirections.entrypoint.scheme=https
      - --certificatesresolvers.letsencrypt.acme.email=${ACME_EMAIL}
      - --certificatesresolvers.letsencrypt.acme.storage=/letsencrypt/acme.json
      - --certificatesresolvers.letsencrypt.acme.httpchallenge.entrypoint=web
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - letsencrypt:/letsencrypt
    networks: [hearth-proxy]

volumes:
  letsencrypt:

networks:
  hearth-proxy:
    external: true
```

Save your certificate email in `/opt/traefik/.env`:

```ini
ACME_EMAIL=you@example.com
```

Then start the proxy:

```bash
docker compose up -d
```

If this VPS already runs Traefik, reuse its external Docker network and certificate-resolver names in the Hearth deployment file instead of starting a second proxy.

## 4. Install and configure Hearth

Save `/opt/hearth-deployment.json`, replacing every example hostname:

```json
{
  "mode": "local",
  "serverName": "hearth.example.com",
  "ports": {
    "matrix": 6167,
    "element": 8009,
    "memory": 8010
  },
  "adminUsername": "admin",
  "adminPasswordEnv": "HEARTH_ADMIN_PASSWORD",
  "public": {
    "elementHost": "hearth.example.com",
    "matrixHost": "hearth-matrix.example.com",
    "memoryHost": "hearth-memory.example.com",
    "certResolver": "letsencrypt",
    "proxyNetwork": "hearth-proxy"
  }
}
```

Set a strong administrator password for this shell and run the unattended installer:

```bash
export HEARTH_ADMIN_PASSWORD='replace-with-a-long-unique-password'
npx create-hearth@latest --directory /opt/hearth --yes --config /opt/hearth-deployment.json
unset HEARTH_ADMIN_PASSWORD
```

The installer configures the public URLs, creates the administrator and standard rooms, provisions a dedicated Matrix observer for dashboard activity, and starts the stack. Generated tokens remain under `/opt/hearth/secrets/` and must not be committed.

## 5. Verify and operate

```bash
cd /opt/hearth
node cli/hearth.mjs status
docker compose ps
```

Open `https://hearth.example.com` for Element and `https://hearth-memory.example.com` for the dashboard. The dashboard prompts for the Memory token stored in `/opt/hearth/.env` as `HEARTH_MEMORY_ADMIN_TOKEN`.

Useful follow-up commands:

```bash
node cli/hearth.mjs agent add claude
node cli/hearth.mjs user add jane
node cli/hearth.mjs dashboard configure
```

The final command repairs or upgrades the dashboard's Matrix observer if an older Hearth installation does not show room activity.

## Backups and updates

Back up `/opt/hearth/.env`, `/opt/hearth/hearth.config.json`, `/opt/hearth/secrets/`, and the `conduit-data` and `memory-data` Docker volumes. Rerun `npx create-hearth@latest --directory /opt/hearth` for an in-place package refresh; it preserves deployment state and generated secrets.

For proxy details, alternate hosts, and security notes, see [EXPOSE.md](EXPOSE.md). For unattended configuration behavior, see [ROLLOUT.md](ROLLOUT.md).
