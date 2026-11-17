# Threat model (MVP)

Scope: the web app (React SPA behind nginx), the FastAPI API, the DB-queue worker, SQLite/PostgreSQL,
the local asset store, Redis (rate limits), and outbound calls to generation providers.

## Assets

| Asset | Why it matters |
|---|---|
| User accounts & sessions | Account takeover exposes prompts, images, keys, credits |
| BYOK provider keys | Direct financial loss for users (paid providers) |
| Server provider keys (Cloudflare token) | Quota theft; abuse attributed to us |
| Prompts and generated/uploaded images | Private creative work; may contain personal data |
| Credit ledger | Free generations = real cost; integrity required before payments exist |
| Service availability & reputation | Abuse (illegal content, spam) can get accounts/IPs banned |

## Attackers

1. **Anonymous internet user**: credential stuffing, mass sign-ups, scraping, injection.
2. **Authenticated user**: IDOR on other users' jobs/assets, credit races, upload exploits, SSRF,
   prompt abuse (prohibited content), quota exhaustion.
3. **Malicious website** visited by a logged-in user: CSRF, clickjacking.
4. **Compromised/hostile provider**: returns malformed or hostile files or redirect URLs.
5. **Supply chain**: malicious or vulnerable dependency, leaked secret in git.
6. **Operator mistakes**: weak secrets in prod, wildcard CORS, mock provider left on.

## Threats → controls (and tests)

| Threat | Control | Where / test |
|---|---|---|
| Password theft from DB | argon2id hashes, no plaintext anywhere | `security.py`, `test_password_is_argon2id_hashed` |
| User enumeration | Same error for wrong password / unknown user; generic register conflict; dummy-hash timing | `test_login_wrong_password_and_unknown_user`, `test_duplicate_email_is_generic` |
| Brute force / mass sign-up | Per-IP + per-email limits; Turnstile when configured | `ratelimit.py`, `test_login_rate_limited` |
| Session theft via XSS | Tokens only in httpOnly cookies; CSP `script-src 'self'`; React escaping; no tokens or keys in localStorage | `nginx.conf`, `api.ts` |
| Stolen refresh token | Rotation on every refresh; reuse of an old token revokes the whole family | `test_refresh_rotation_and_reuse_detection` |
| CSRF | SameSite=Lax + double-submit token header + Origin allowlist on unsafe methods | `test_csrf_required_for_unsafe_methods`, `test_foreign_origin_rejected` |
| Clickjacking | `frame-ancestors 'none'`, `X-Frame-Options: DENY` | headers tests |
| IDOR | Every lookup filtered by owner; not-yours == not-found (404) | `test_idor.py` |
| Mass assignment | `extra="forbid"` on all input models | `test_register_validation` |
| Credit double-spend / negative balance | Conditional UPDATE + CHECK constraint + unique idempotency keys, one transaction with the job insert; SQLite `BEGIN IMMEDIATE` | `test_credits.py` (25 concurrent debits) |
| Duplicate job on retry | `Idempotency-Key` header, unique per user | `test_idempotency_key_prevents_double_charge` |
| Malicious upload (polyglot, SVG/XSS, bombs) | Content sniffing via Pillow, allowlist PNG/JPEG/WebP, pixel cap, re-encode to WebP (drops EXIF/payloads), random server names, `nosniff` | `test_upload_checks_content_not_name`, `test_reencode_*` |
| Path traversal | Server-generated keys only; resolved path must stay in asset root | `test_asset_path_traversal_blocked` |
| SSRF via provider result URLs | https only, default ports, no userinfo, resolve-then-connect to a vetted public IP with SNI pinning, manual redirects re-validated, size cap | `ssrf.py`, `test_ssrf_*` |
| Key leakage | BYOK encrypted with Fernet; write-only API; server keys only in env; never logged | `test_byok_key_encrypted_and_never_returned` |
| Prohibited content | Prompt keyword screen (incl. minors + sexual), report button, admin block/remove | `moderation.py`, `admin.py`, `test_moderation` |
| Animating someone else's image (IDOR) | `image_asset_id` must be the caller's own image, re-checked by the worker | `test_cannot_animate_someone_elses_image` |
| Hostile provider video | MP4 top-level box structure, brand allowlist, size cap, served as `video/mp4` + nosniff; users cannot upload video | `test_mp4_validation` |
| BYOK key exfiltration via provider-supplied URLs | fal queue URLs must be `https://queue.fal.run/...`; result files fetched without the key through the SSRF guard | `test_key_never_sent_to_foreign_status_url` |
| Hammering a provider into a ban / burning shared quota | Learned cooldowns block new jobs (`429 provider_cooldown`), worker waits or refunds | `test_worker_learns_and_api_blocks_during_cooldown` |
| Resource exhaustion / one user starving others | Per-user active-job cap, global queue cap with 503 back-pressure, round-robin claiming, CPU and per-provider lanes, worker slots, hard deadlines, janitor | `test_queue.py` |
| Huge images/videos exhausting RAM or CPU | Pixel cap (8192²), bounded upscaler input (target/4), tile deadline, provider image size cap, videos streamed to disk (600 MB cap) | `test_upscale.py`, `test_video.py` |
| Third-party telemetry from dependencies | `ORT_DISABLE_TELEMETRY=1` set before ONNX Runtime is imported (code + Dockerfile) | `upscaler.py` |
| Webhook forgery/replay (future payments) | HMAC-SHA256 over timestamp+body, 5-min window, processed-event table | `webhooks.py`, `test_webhook_*` |
| Weak production config | Settings refuse missing secrets, wildcard CORS, insecure cookies, mock provider in prod | `test_cors_wildcard_and_weak_prod_config_refused` |
| Spoofed client IP | Only uvicorn `--proxy-headers` with `FORWARDED_ALLOW_IPS`; nginx overwrites X-Forwarded-For | `Dockerfile`, `nginx.conf` |
| Vulnerable dependency | Exact pins + lockfiles, Dependabot, pip-audit, npm audit in CI | `.github/` |
| Secret committed to git | `.env` ignored, gitleaks in pre-commit and CI | `.pre-commit-config.yaml`, `ci.yml` |
| PII in logs | Worker logs only job ids/status; validation errors never echo input | `worker.py`, `main.py` |

## Known gaps (accepted for the MVP, tracked)

- Keyword moderation is easy to evade; no image-output classifier yet. Add a real moderation model
  before opening public sign-ups widely.
- No email verification or password reset yet (needs an email provider or magic links).
- Access JWTs stay valid until expiry (15 min) after logout or block; blocked users are rejected on
  every request because the user row is checked, but a stolen access token works until it expires.
- SQLite `BEGIN IMMEDIATE` serialises writers; fine for a small beta, switch to PostgreSQL to scale.
- GitHub Actions are pinned to major tags, not commit SHAs; Dependabot updates them. Pin to SHAs
  before accepting outside contributors with workflow changes.
- Assets on local disk are not encrypted at rest; use an encrypted volume or R2 with SSE in prod.
- Prompts are sent to the chosen third-party provider; this is disclosed in the Terms.
- Videos are not re-encoded (no ffmpeg in the image), so container metadata from the provider is
  kept. Only provider output is accepted, never user uploads.
- Image-to-video start frames are sent to fal as data URIs: the user's image leaves our server
  (disclosed by choosing that provider).
