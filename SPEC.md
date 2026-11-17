# Aurevid: functional specification

Clean-room spec written in our own words. It describes **what** the product does, not how any other
product looks or is built. No text, preset names, layouts or assets were copied from anywhere.

**Source labels:** `observed` = seen on a public page · `user` = from the project owner's brief ·
`assumption` = our decision where the brief was silent · `unknown` = not determined.

**Research note.** The reference site's public homepage is client-rendered. A plain fetch returned only
its page title, which describes an AI studio for video, image and voice (`observed`). No feature list,
pricing or UI could be read without running its JavaScript, and we did not try to get around that.
Its robots.txt allows `/` for general agents but sets `ai-train=no`. **Fallback plan used:** this spec
rests on the owner's brief, not on the reference product's features.

## 1. Users and goals

| # | Requirement | Source |
|---|---|---|
| 1.1 | Target users: small businesses and content creators, Uzbekistan first, then international | user |
| 1.2 | Interface in English, Uzbek (Latin) and Russian; English is the base language | user |
| 1.3 | Free to run for development and first users; no mandatory paid service | user |

## 2. Generation studio (MVP)

| # | Requirement | Source | Status |
|---|---|---|---|
| 2.1 | One prompt box; user picks a generation model from a list of providers | user | done |
| 2.2 | Image first, video later | user | image done; video API-ready (`kind`) |
| 2.3 | Settings: aspect ratio, size, number of outputs | user | done (5 ratios, 3 sizes, 1-4) |
| 2.4 | Each model shows clearly whether it is free or paid, and whether it needs a key | user | done |
| 2.5 | Each model shows its commercial-use status (yes / no / unclear) | assumption | done |
| 2.6 | Results appear in a history gallery; items can be favourited | user | done |
| 2.7 | Jobs are asynchronous: queued → running → done/failed, live status via SSE with polling fallback | user | done |
| 2.8 | Failed or partial generations refund unused credits automatically | assumption | done |
| 2.9 | Reuse a past prompt in one click | assumption | done |

## 3. Camera / motion presets

| # | Requirement | Source | Status |
|---|---|---|---|
| 3.1 | Library of presets with **original** names and prompt text | user | done (3) |
| 3.2 | A preset becomes prompt text plus provider parameters (`image_defaults`, `video_params`) | user | done |
| 3.3 | MVP ships 3 presets: Gentle Drift In, Halo Orbit, Skyward Unveil | user (count) / assumption (names) | done |
| 3.4 | Presets are JSON files validated at startup; user text cannot inject template fields | assumption | done |

## 4. Later (not in MVP)

| # | Requirement | Source | Status |
|---|---|---|---|
| 4.1 | Marketing helper: product image or text → short ad prompt set for 9:16 and 1:1 | user | not built; upload endpoint ready |
| 4.2 | Image-to-video as an optional provider adapter | user | not built; interface ready |
| 4.3 | Payments (Payme/Click), Telegram bot, desktop (Tauri), PWA, browser extension | user | not built; one API for all clients |
| 4.4 | Voice generation | observed (page title only) | unknown, out of scope |

## 5. Accounts, credits, limits

| # | Requirement | Source | Status |
|---|---|---|---|
| 5.1 | Email + password sign-up and login | user | done |
| 5.2 | Optional magic link / Telegram login | user | not built |
| 5.3 | Credits page: balance, today's usage, recent activity | user | done |
| 5.4 | Append-only credit ledger; no negative balance | user | done |
| 5.5 | Starter credits on sign-up (default 50); no paid top-ups yet | assumption | done |
| 5.6 | Daily generation limit per user (default 30 jobs) and rate limits | user | done |
| 5.7 | Bring-your-own-key, stored encrypted on the server, never returned | user | done |
| 5.8 | Export my data; delete my account | user | done |

## 6. Safety and content

| # | Requirement | Source | Status |
|---|---|---|---|
| 6.1 | Terms / Acceptable Use page; user responsible for prompts and uploads | user | done (draft, en/uz/ru) |
| 6.2 | Prohibited: infringing, deceptive, sexual and minor-related content | user | done (terms + prompt filter) |
| 6.3 | Report button on results; admin can block users and remove assets | user | done (API; no admin UI yet) |
| 6.4 | Image-output moderation | assumption | not built (known gap) |

## 7. Providers (MVP)

| Provider | Tier | Key | Default | Source |
|---|---|---|---|---|
| Cloudflare Workers AI, FLUX.1 schnell | free (daily allocation) | server or BYOK | on | user |
| Pollinations | free (anonymous) | none | **off**, terms unclear | user (fallback) / assumption (off) |
| fal.ai | paid | BYOK only | off | user |
| Replicate | paid | BYOK | not built | user |
| Offline demo | free | none | dev only | assumption |
