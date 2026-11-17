# Deploying Aurevid for free (or almost)

Prices and free tiers change; check each provider's page before relying on them. Everything below
works without a credit card **except** where noted.

## Before any public deployment

```bash
python -c "import secrets;print(secrets.token_urlsafe(48))"      # JWT_SECRET
cd backend && uv run python -m app.cli gen-key                    # BYOK_ENCRYPTION_KEY (back it up!)
```

Set in the server environment (never in git):

```
APP_ENV=prod
JWT_SECRET=...
BYOK_ENCRYPTION_KEY=...
COOKIE_SECURE=true
CORS_ORIGINS=["https://your.domain"]
MOCK_PROVIDER_ENABLED=false
CF_ACCOUNT_ID=...            # optional shared free tier
CF_API_TOKEN=...             # "Workers AI: Read" only
TURNSTILE_SECRET=...         # strongly recommended for public sign-ups
RATE_LIMIT_STORAGE=redis://...   # required when running more than one API process
VITE_SOURCE_URL=https://github.com/<you>/aurevid   # AGPL source offer
```

Then make yourself admin: `python -m app.cli make-admin you@example.com`.

The frontend and API **must share one origin** (e.g. `https://app.example.com` serving the SPA and
proxying `/api`), because auth uses first-party cookies. The bundled nginx image does this.

## Sizing for 4K/8K

Local image upscaling is CPU work. Rough timings: 8 cores → 4K ≈ 30 s, 8K ≈ 100 s (measured); a 4-core free
ARM VM is about twice as slow. Plan ≥ 1 GB RAM for the worker (an 8K square peaked at ~780 MB
in our measurement). Keep `CPU_JOB_CONCURRENCY=1` on small machines; the queue makes
other users wait their turn instead of overloading the server. Set `UPSCALER_ENABLED=false` to turn it off.

## Option 0: shared home/VPS host with Cloudflare Tunnel (used for the first deployment)

```bash
git clone https://github.com/goldendevuz/aurevid.git ~/projects/aurevid && cd ~/projects/aurevid
cp .env.example .env   # set prod values + TUNNEL_TOKEN (Zero Trust → Networks → Tunnels)
docker compose -f docker-compose.yml -f docker-compose.prod.yml --profile tunnel up -d --build
docker compose exec api python -m app.cli make-admin you@example.com
```

In the tunnel's *Public Hostname* set the service to `http://web:8080`. No port is opened on
the host, and `docker-compose.prod.yml` caps CPU/RAM so upscaling cannot starve other services.
Update: `git pull && docker compose -f docker-compose.yml -f docker-compose.prod.yml --profile tunnel up -d --build`.

## Option A: one small VM (simplest, recommended)

Oracle Cloud *Always Free* ARM VM, or any €4-5/month VPS (Hetzner, etc.).

```bash
git clone https://github.com/<you>/aurevid && cd aurevid
cp .env.example .env && nano .env        # prod values as above
docker compose up -d --build
```

Put HTTPS in front:
- **Cloudflare Tunnel** (free, no open ports): `cloudflared tunnel --url http://localhost:8080`, or
- **Caddy** as reverse proxy with automatic Let's Encrypt certificates.

The compose file binds the web container to `127.0.0.1:8080` only, so nothing is exposed until you
add the tunnel or proxy. Back up the `aurevid-data` volume (SQLite DB + images).

## Option B: Fly.io / Render (single container)

Free tiers here change often and may need a card. Use one container that runs the API with the worker
inside (`RUN_WORKER_IN_API=true`) plus a persistent volume for `/app/data`. Build the frontend
separately (Option C) or serve it with the same nginx image on a second service under the same domain.

## Option C: static frontend on Cloudflare Pages / Vercel

`cd frontend && npm ci && npm run build`, deploy `dist/`. Configure the host to **proxy `/api/*`**
to your backend under the same domain (Cloudflare: a Worker route or Pages Functions; Vercel:
`rewrites`). Copy the CSP and security headers from `frontend/nginx.conf` into the host's headers config.

## Database: PostgreSQL later

Set `DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/aurevid` and run `alembic upgrade head`.
Free options: Neon, Supabase (check current limits). SQLite is fine for the first users.

## Images on Cloudflare R2

The MVP stores images on local disk (`ASSET_DIR`). An R2 storage adapter is not built yet; R2's free
tier (check current limits) is the planned target. Until then, keep `/app/data` on a persistent volume.

## What still costs money

- Nothing for development and a small beta on Cloudflare's free allocation (~170 images/day/account).
- A domain name (optional; Cloudflare Tunnel gives a free subdomain for testing).
- Paid providers (fal.ai) are billed to each user's own key, never to you.
