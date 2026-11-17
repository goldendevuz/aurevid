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

## Video

`ModelInfo.kind` is `image` or `video`. Video models declare `durations` (seconds), and optionally
`accepts_image` / `requires_image` for image-to-video. Jobs store `kind`, `duration` and
`image_asset_id` (must be the caller's own image, checked at creation and again in the worker).
The worker loads the start frame, converts it to a JPEG (≤1280 px), calls the adapter with the longer
`VIDEO_TIMEOUT_SECONDS`, and stores the MP4 after a strict container check (`images.validate_mp4`).
fal video uses the queue API (submit → poll `status_url` → `response_url`); the key is only sent to
`queue.fal.run`, and the result file is downloaded through the SSRF guard without the key.

## Self-learning provider limits (`services/quota.py`)

Free services rarely publish exact limits. For every provider and credential scope
(`server`, `anon`, `user:<id>`) we keep a row in `provider_quotas`:

| Field | Meaning |
|---|---|
| `used_today` | outputs produced in the current UTC day |
| `est_daily_limit` | estimate: starts from a documented prior (Cloudflare ≈170 images/day) or unknown |
| `observations` | how many limit errors have informed the estimate |
| `cooldown_s`, `blocked_until` | learned back-off after a limit error |

Learning rules:
1. The first quota error of a streak is an observation `limit ≈ used_today`; the estimate moves
   halfway toward it (EWMA, α = 0.5), so repeated days converge on the real value.
2. Producing more than the estimate without an error proves a higher limit: the estimate is raised
   to `used_today` at once.
3. Each further error in a streak doubles the cooldown (15 s → … → 6 h max); a success shrinks it
   by 25 %.
4. Only the cooldown blocks requests (API answers `429 provider_cooldown` with `Retry-After`, the
   worker waits ≤30 s or refunds). The daily estimate is advisory, so a too-low estimate can still
   be corrected by probing.

Adapters flag provider-side limits with `ProviderError(..., quota=True)`. Paid providers set
`track_quota=False`.

## 4K / 8K output

* **Images (free):** `app/upscaler.py` runs Real-ESRGAN `realesr-general-x4v3` (ONNX Runtime, CPU).
  The source is resized to exactly target/4 and the network does one 4x step, in 192 px tiles with
  16 px context. Work is bounded (network input ≤ 1920 px for an 8K square, ~200 MB RAM) and a
  deadline is checked between tiles (`UPSCALER_TIMEOUT_SECONDS`). Measured on 8 cores (Docker): 4K ≈ 30 s,
  8K ≈ 100 s including WebP encoding; peak RSS ≈ 780 MB. Large images also get a ≤1024 px preview for galleries.
* **Video (paid, opt-in):** after the Wan 2.2 clip, Topaz on fal upscales the fal-hosted result
  (720p → 4K: 3x; 8K: 4x then 1.5x). The final file is streamed to disk through the SSRF guard
  and its MP4 structure validated without loading it into memory.

## Job queue and resource control (`services/queue.py`)

| Control | Setting | Effect |
|---|---|---|
| Per-user admission | `MAX_ACTIVE_JOBS_PER_USER` (3) | queued+running per user; beyond → 429 `too_many_active_jobs` |
| Global back-pressure | `MAX_QUEUE_LENGTH` (200) | beyond → 503 `queue_full` + Retry-After, nothing charged |
| Fairness | (always) | round-robin: each user's 1st job, then 2nd…; users with work running go behind |
| CPU lane | `CPU_JOB_CONCURRENCY` (1) | local upscaling never runs more than N at once, across workers |
| Provider lane | `PROVIDER_CONCURRENCY` (2) | in-flight jobs per remote provider |
| Worker slots | `WORKER_SLOTS` (3) | concurrent jobs per worker process; CPU work runs in threads |
| Deadlines | `JOB_TIMEOUT_SECONDS`, `VIDEO_TIMEOUT_SECONDS`, `UPSCALER_TIMEOUT_SECONDS` | stuck work fails and is refunded |
| Janitor | every 5 min | jobs left `running` by a crashed worker are failed and refunded |

Caps are computed from the `running` rows in the database, so they hold across several worker
processes; a claim that races past a cap is put back in the queue. Each queued job reports its
fair-order position and an ETA from the average duration of recent jobs of the same kind.

## Admin panel (`/admin`, `routers/admin.py`, `services/analytics.py`)

Admins are made with `python -m app.cli make-admin <email>` (never by email in config: sign-up
does not verify email ownership yet). Non-admins get 404 on every admin route.

| Tab | What it shows / does |
|---|---|
| Overview | KPI tiles (today vs yesterday, this vs last month), 30-day and 12-month charts, queue, storage, recent sign-ups and failures; auto-refresh |
| Users | search, filters (customers / team-test / blocked / admins; activated / never tried / tried-and-failed), sorting, paging; detail card with credits add/deduct (idempotent), block, team/test flag, admin flag, recent jobs and ledger |
| Jobs | filters (status, type, provider, period, email/id), cancel queued (refund), free retry of failed, top errors |
| Analytics | funnel (registered → tried → result → 2+ results → power user), retention (daily active new vs returning, active-day buckets, streaks), weekly/monthly cohort heatmap, time to first job |
| Moderation | user reports with preview, remove file, block owner, dismiss; rejected-prompt categories per user (prompt text is never stored) |
| System | DB, Redis, disk, worker heartbeats, queue, failure rate, upscaler, BYOK, providers, config warnings; learned provider limits with cooldown reset |
| Announcements | in-app banners in en/uz/ru with optional end time |
| Audit log | every admin action (who, what, target, when), stored in `admin_audit` |

Team/test accounts (`users.is_internal`) are excluded from analytics by default. Activity is one
row per user per Asia/Tashkent day (`user_activity`), written at most once per day per process.
CSV exports neutralise spreadsheet formulas (CSV injection).
