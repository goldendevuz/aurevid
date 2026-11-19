# Aurevid

**Open-source multi-model AI image studio: one prompt box, free providers first, your own keys optional.**

[O'zbekcha](README.uz.md) · [Spec](SPEC.md) · [Security](SECURITY.md) · [Threat model](docs/threat-model.md) · [Deploy](docs/deploy.md)

Aurevid lets small businesses and creators generate images from a single prompt box, pick a model
from several providers (each clearly labelled free or paid, with its commercial-use status), apply
original camera presets, and keep results in a history gallery with favourites. Interface: English,
Uzbek, Russian.

![Studio (Uzbek interface)](docs/img/studio-uz.png)

> Status: **MVP / beta.** Image and video generation work end to end. The marketing helper, payments
> and other clients are planned, and the API is shaped for them.

## Features

- Prompt studio: model picker, aspect ratio (1:1, 16:9, 9:16, 4:3, 3:4), size, 1-4 images
- Video: text-to-video and **Animate** (image-to-video from any of your images), MP4 player in the gallery
- 3 original camera presets (Gentle Drift In, Halo Orbit, Skyward Unveil) with image and camera-motion wording
- **4K / 8K images for free**: a local AI upscaler (Real-ESRGAN, BSD-3) runs on your own server's
  CPU, no API or GPU needed (measured on 8 cores: ~30 s for 4K, ~100 s for 8K, peak ~780 MB RAM). "Upscale 4K/8K" on any image.
- Fair job queue: per-user limits, round-robin between users, one heavy CPU job at a time,
  per-provider concurrency caps, back-pressure (429/503 + Retry-After), queue position and ETA
- **Admin panel** (`/admin`): overview with trends (Tashkent time), users (search, filters,
  credits, block, team/test flag), jobs (filters, cancel, free retry, top errors), activation
  funnel, retention, cohort heatmap, moderation (reports + rejected-prompt categories), system
  health, learned provider limits, in-app announcements, persistent audit log, CSV export
- Self-learning provider limits: counts usage per provider/key and learns undocumented limits from
  quota errors ("≈N left today", automatic pause during the learned cooldown)
- Async job queue (works on SQLite, no Redis needed) with live status over Server-Sent Events
- History, favourites, delete, report
- Credits: append-only ledger, starter credits, daily limits, automatic refunds on failure
- Bring-your-own-key: encrypted server-side, never sent back to the browser
- Data export and account deletion
- en / uz / ru interface

## Providers

| Provider | Free? | Needs | Enabled by default |
|---|---|---|---|
| Cloudflare Workers AI (FLUX.1 schnell, FLUX.2 klein 4B incl. edit with text; Apache-2.0; plus alt text and voice prompts) | Yes, daily free allocation | Cloudflare account ID + API token (server-wide or per user) | Yes |
| fal.ai (FLUX.1 schnell image; Wan 2.2 video and image-to-video, Apache-2.0) | **Paid** (user's own key) | fal.ai key | Yes (BYOK only) |
| Modal (your own Wan 2.2 TI2V-5B on a Modal GPU, Apache-2.0; see `deploy/modal/`) | **Paid** from your Modal credit | Modal token | Yes (BYOK only) |
| Pollinations | Yes, anonymous | nothing | **No**: its terms could not be verified, see [MODEL_LICENSES.md](MODEL_LICENSES.md) |
| Offline demo (image + short video clip) | Yes | nothing | Dev only |

> **Video has no free provider.** We found no hosted video API with a verifiable free tier (see
> MODEL_LICENSES.md). Video uses the user's own key on fal.ai (about $0.15 per 5 s clip for
> Wan 2.2 5B at the time of writing) or Modal; development uses the offline demo clip.
> Only models whose commercial use is clearly allowed are offered; the rule is enforced in code
> (see MODEL_LICENSES.md, rule 3).

## Quick start (Docker, one command)

```bash
git clone https://github.com/goldendevuz/aurevid.git && cd aurevid
docker compose up --build
```

Open http://localhost:8080 and sign up. Without a `.env` file it runs in **dev mode** with the offline
demo provider. To generate real images, create a free Cloudflare account, make an API token with
*Workers AI: Read* permission, then:

```bash
cp .env.example .env
# set CF_ACCOUNT_ID, CF_API_TOKEN, JWT_SECRET, BYOK_ENCRYPTION_KEY
docker compose up --build
```

> If Docker says *"all predefined address pools have been fully subnetted"*, you have too many old
> Docker networks: `docker network prune` removes unused ones (check the list first).

## Local development

Requirements: Python 3.12 + [uv](https://docs.astral.sh/uv/), Node 20.19+ (or 22).

```bash
cd backend
uv sync
cp ../.env.example .env        # dev values are fine; set MOCK_PROVIDER_ENABLED=true
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --port 8000
```

```bash
cd frontend
npm ci
npm run dev                    # http://localhost:5173, proxies /api to :8000
```

Tests and checks:

```bash
cd backend && uv run ruff check . && uv run pytest -q
cd frontend && npm run typecheck && npm test && npm run build
```

## Architecture

```
Browser (React SPA) ──same origin──▶ nginx ──/api──▶ FastAPI ──▶ SQLite / PostgreSQL
                                                  │             ▲
                                                  ▼             │ claim job (conditional UPDATE)
                                               Redis        Worker ──▶ provider adapters
                                           (rate limits)        │      (Cloudflare, fal, ...)
                                                                ▼
                                                     asset store (disk / R2)
```

- `backend/app/providers/base.py`: the one interface every provider implements.
- `backend/app/worker.py`: DB-backed queue. Run it in the API process (`RUN_WORKER_IN_API=true`)
  for single-container hosting, or as a separate process.
- All clients (web now; Telegram bot, desktop, PWA later) use the same `/api`.

More: [docs/architecture.md](docs/architecture.md).

## Configuration

All settings are environment variables; see [.env.example](.env.example). Secrets live only in the
server environment. With `APP_ENV=prod` the app refuses to start without strong secrets, with
wildcard CORS, with insecure cookies, or with the demo provider on.

## Licence

[AGPL-3.0-or-later](LICENSE). If you run a modified version as a network service, you must offer
its source to your users; set `VITE_SOURCE_URL` so the footer links to it. Third-party licences:
[THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md); model licences: [MODEL_LICENSES.md](MODEL_LICENSES.md).

Contributions welcome: [CONTRIBUTING.md](CONTRIBUTING.md).
