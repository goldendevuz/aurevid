# Name selection record (2026-11-17)

Criteria: coined English-looking word, 2-3 syllables, 5-9 letters, easy to say in uz/ru/en, no bad
meaning in Uzbek or Russian, not a dictionary word, no AI/video/creative product with the same or a
very similar name, `.app` and `.dev` free.

Method: web search; GitHub `name in:name` repo search; RDAP lookups (`.app`/`.dev` at Google
Registry, `.com` at Verisign; 404 = not registered); `.uz` by DNS NS lookup only (weak signal: no
whois available); npm and PyPI registry lookups; YouTube `@handle` and Telegram `t.me` pages.
Instagram, X and TikTok need a login to check and were **not checked**.

| Candidate | Web (AI/video use) | GitHub repos | .app | .dev | .uz (DNS) | .com | npm / PyPI | YouTube / Telegram / @_bot | Decision |
|---|---|---|---|---|---|---|---|---|---|
| kadrino | none found, but **"Kadro Video Editor"** (open-source video editor) is very close | 1 | free | free | no NS | registered 2026-07, parked (Afternic) | free / free | taken / taken / free | Rejected (similar video product); backup name |
| kadrova | not searched (failed on GitHub/handles) | 5 | free | free | no NS | registered | free / free | taken / taken / **taken** | Rejected |
| zelvio | none (Zelios agency differs) | 24 | **taken** | not checked (rate-limited) | no NS | registered | free / free | taken / free / taken | Rejected |
| rendaro | none; "Rendora AI" video tool is close | 3 | **taken** | free | no NS | registered | free / free | taken / taken / free | Rejected |
| freymo | none | 28 | not checked | not checked | no NS | registered | free / free | taken / taken / free | Rejected (GitHub) |
| nuvexa | not searched | 112 | not checked | not checked | no NS | registered | free / free | taken / taken / taken | Rejected |
| zivano | not searched | 45 | not checked | not checked | no NS | registered | free / free | taken / taken / free | Rejected |
| tolvex | not searched | 8 | free | not checked | no NS | registered | **taken / taken** | taken / taken / free | Rejected |
| **aurevid** (pre-checked fallback) | none per owner's earlier check | **0** | **free** | **free** | no NS | registered 2026-08 (GoDaddy NS, empty title page) | free / free | free / free / free | **Chosen** |

No new candidate met every condition, so the pre-checked fallback **Aurevid** was chosen, as the brief
requires. Known downside: Google autocorrects it toward "ayurvedic". Mitigation: always pair the name
with "AI studio" in titles and descriptions.

Repository: `aurevid` · Description: "Open-source multi-model AI image studio: one prompt box, free
providers first, your own keys optional." · Topics: `ai`, `image-generation`, `fastapi`, `react`,
`flux`, `open-source`, `agpl`, `uzbekistan`, `i18n`, `self-hosted`.
