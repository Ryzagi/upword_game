# Deploying Word Describer

This stack is two containers behind a single nginx that fronts both the SPA
and the FastAPI backend (REST + WebSocket). For public deployments a third
container — Caddy — sits in front and terminates TLS.

```
            ┌──────────────────────────────┐
            │  frontend (nginx :80)        │
            │   • SPA at /                 │
            │   • proxy /api/ → backend    │
            │   • proxy /ws/  → backend    │
   :8080 ───┤                              │
            └──────────────┬───────────────┘
                           │ docker network
            ┌──────────────┴───────────────┐
            │  backend (uvicorn :8000)     │
            └──────────────────────────────┘
```

## Run locally with Docker Compose

Requires Docker 24+ with Compose v2.

```bash
docker compose up --build
# open http://localhost:8080
```

Override the public port:

```bash
PUBLIC_PORT=80 docker compose up --build
```

Override the log level:

```bash
APP_LOG_LEVEL=DEBUG docker compose up --build
```

Stop and remove containers:

```bash
docker compose down
```

## Environment variables

| Var                       | Where      | Default                       | Purpose                                                |
| ------------------------- | ---------- | ----------------------------- | ------------------------------------------------------ |
| `APP_LOG_LEVEL`           | backend    | `INFO`                        | Standard log levels (`DEBUG`/`INFO`/`WARNING`/`ERROR`) |
| `APP_CORS_ORIGINS`        | backend    | `["http://localhost:8080"]`   | JSON list of allowed browser origins                   |
| `APP_TRANSLATION_EMAIL`   | backend    | `""`                          | MyMemory contact email — raises free quota 1k → 10k    |
| `APP_TRANSLATOR_DISABLED` | backend    | `false`                       | Set `true` to short-circuit the translator (tests)     |
| `APP_CORPUS_DIR`          | backend    | `/data` (set in Dockerfile)   | Where to load the `words.*.json` packs                 |
| `PUBLIC_PORT`             | compose    | `8080`                        | Host port the frontend container publishes             |

## Building individual images

```bash
docker build -f backend/Dockerfile  -t word-describer-backend  .
docker build -f frontend/Dockerfile -t word-describer-frontend .
```

Both Dockerfiles expect to be built **from the repo root** — they reach into
`backend/`, `frontend/`, and `data/` siblings.

## Deploying to a public domain (upword.live on Vultr)

End-to-end recipe to put the stack behind `https://upword.live`.

### 1. Point DNS at the server

At **GoDaddy → My Products → upword.live → DNS**, set:

| Type | Name | Value                          | TTL   |
| ---- | ---- | ------------------------------ | ----- |
| A    | `@`  | your Vultr server's IPv4       | 600   |
| A    | `www`| your Vultr server's IPv4       | 600   |

(Optional: add matching `AAAA` records if your Vultr instance has IPv6.)

Verify propagation from any machine:

```bash
dig +short upword.live
dig +short www.upword.live
```

Both should return the Vultr IP. DNS can take a few minutes; Let's Encrypt
will fail to issue if records aren't resolving yet, so don't move on until
they do.

### 2. Open the ports on the server

Vultr's edge firewall is permissive by default, but Ubuntu's `ufw` is often
enabled. On the server:

```bash
sudo ufw allow 22/tcp        # don't lock yourself out
sudo ufw allow 80/tcp        # ACME HTTP-01 challenge + redirect
sudo ufw allow 443/tcp       # HTTPS
sudo ufw allow 443/udp       # HTTP/3 (optional but Caddy enables it)
sudo ufw status
```

If you also configured a Vultr-side firewall group, mirror the same rules
in the Vultr control panel.

### 3. Pull the repo and bring the stack up

```bash
# Install docker + compose once (Ubuntu / Debian):
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER && newgrp docker

# Clone and start:
git clone <your-repo-url> upword && cd upword
docker compose --profile prod up -d --build

# Watch the logs to confirm Caddy got a cert:
docker compose logs -f caddy
# Look for: "certificate obtained successfully" or "served key authentication"
```

The first start takes a minute or two — Caddy is talking to Let's Encrypt
to obtain a certificate. Subsequent starts are instant; the cert is cached
in the `caddy_data` named volume and renewed automatically ~30 days before
expiry.

### 4. Verify

```bash
curl -fsS https://upword.live/healthz
# → {"ok":true}
```

Then open `https://upword.live` in two browsers, share the room code, and
play. WebSockets ride the same TLS connection (Caddy upgrades transparently
— no extra config needed).

### 5. Updating to a new version

```bash
cd upword
git pull
docker compose --profile prod up -d --build
```

The cert volume persists, so the new images come up with the same TLS state.

## Alternative: bare-metal (no Docker)

If you don't want Docker on the box:

1. Run `uvicorn app.main:app --host 127.0.0.1 --port 8000` under systemd.
2. Build the SPA: `cd frontend && npm run build`, copy `dist/*` to
   `/var/www/word-describer`.
3. Drop `deploy/nginx.conf` into `/etc/nginx/sites-available/word-describer`,
   symlink to `sites-enabled`, reload.
4. Add the matching `map $http_upgrade $connection_upgrade { … }` block at
   the `http {}` level (it lives at the top of `deploy/nginx.conf` as a hint
   but nginx only allows it once per process).

## Backups / persistence

There is none to manage in v1 — rooms live in memory only and disappear when
the backend restarts. Players are notified by the WS close code and bounced
to the lobby form to rejoin.

## Smoke test after deploy

```bash
curl -fsS https://words.example.com/healthz
# → {"ok":true}
```

Then open the URL in two separate browsers (or one + an incognito) and
confirm:

1. Create-room hands out a 6-char code.
2. The second browser can join the code.
3. Picking a theme broadcasts to the other client within ~200 ms.
4. Starting a game transitions both clients to the board.
5. The describer's word appears only in their browser.
