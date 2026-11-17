# Architecture

## Components

| Component | Tech | Notes |
|---|---|---|
| Web client | React 19 + Vite + TypeScript + Tailwind 4, i18next | SPA, same-origin API calls, no tokens in JS |
| Edge | nginx (unprivileged) | Serves SPA, proxies `/api`, CSP + security headers, SSE unbuffered |
| API | FastAPI, Pydantic v2, SQLAlchemy 2 (async), Alembic | Stateless; any number of replicas with Redis rate limits |
| Worker | `python -m app.worker` | DB-backed queue; claims jobs with a conditional UPDATE |
| Database | SQLite (WAL, `BEGIN IMMEDIATE`) → PostgreSQL via `DATABASE_URL` | Same code, same migrations |
| Rate limits | `limits` library, memory (dev) or Redis | Per IP and per user |
| Assets | Local disk (random names, WebP re-encoded) | R2 adapter planned |

## Core concepts (tables)

- `users`: email, argon2id hash, locale, flags, cached `credit_balance` (CHECK ≥ 0)
- `refresh_tokens`: hashed, rotated, grouped in families for reuse detection
- `jobs`: `queued | running | done | failed`, provider, model, params, cost, client idempotency key
- `assets`: owner, job, storage key, mime, size, favourite
- `credits_ledger`: append-only rows with unique idempotency keys and `balance_after`
- `provider_keys`: BYOK secrets, Fernet-encrypted
- `reports`, `webhook_events`
- `presets`: JSON files in `backend/app/presets/` (versioned with the code)

## Request flow: generate

1. `POST /api/jobs` (CSRF + auth + rate limit) → validate → moderation → provider/model/ratio checks
   → daily limit → **one transaction:** insert job + debit ledger + decrement balance.
2. Worker claims the oldest queued job (`UPDATE ... WHERE status='queued'`), resolves credentials
   (user BYOK > server key), calls the adapter, validates and re-encodes each image, stores it.
3. Worker finishes the job; unused credits are refunded with key `refund:<job>` (idempotent).
4. Client follows `GET /api/jobs/{id}/events` (SSE) or polls `GET /api/jobs/{id}`.

## Adding a provider

Implement `ImageProvider` in `backend/app/providers/<name>.py` (fill `ProviderInfo`, implement
`generate`), register it in `registry.py` behind a `*_ENABLED` setting, add a row to
`MODEL_LICENSES.md`. Raise `ProviderError(public_message, retryable=...)`, never leak upstream bodies.
If the provider returns a URL, download it with `ssrf.safe_get`.

## API for future clients

Telegram bot, desktop (Tauri), PWA and browser extension will reuse `/api`. Cookie auth suits
browser-based clients. For the bot and native apps, add a token-based login (e.g. Telegram login
widget → short-lived bearer tokens) as a separate auth dependency, without changing resource endpoints.
