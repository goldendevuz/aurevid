# Design direction

Two original moodboard directions were considered before building the UI.

## A. Darkroom Amber (v1, replaced by Aurora Night, see below)

- Colours: warm charcoal `#121110` / `#1c1a18` / `#26231f`, hairlines `#3a352f`, text `#f3efe8`,
  muted `#a39b8f`, single accent amber `#f0a73a`, success `#6fcf97`, danger `#ef6f5e`
- Type: system UI stack (no web fonts), 600 weight titles with tight tracking, small uppercase labels
- Spacing: 4 px scale, 12 px card radius, 20 px card padding, generous gaps between panels

## B. Paper Studio

- Colours: off-white paper `#f6f2ea`, ink `#1d1b19`, teal accent `#1f7a74`, soft grey borders
- Type: system serif titles + system sans body
- Spacing: wider margins, flat cards with shadows

## Why A (v1)

Generated images are the product, and a dark, warm-neutral surface lets their colours read accurately
without glare. A single amber accent sets us apart from the common purple/blue look of AI tools.
System fonts avoid font licensing and third-party font requests.

## Logo ideas

1. **Aperture-A** (used as the current favicon): a solid geometric "A" whose counter forms a small
   lens opening, with an amber dot like a recording light.
2. **Light trail "a"**: a lowercase "a" drawn as one continuous stroke that ends in a short glowing
   arc, suggesting camera motion. Works in a single colour.

## Aurora Night (v2, replaced by Neon Coast, see below)

A premium, startup-grade refresh. Original work: the palette, gradient, icon set, logo treatment
and layouts were designed for Aurevid and do not copy any other product's artwork, code or brand.

- **Stage:** ink-black `#06070b` with a faint blue undertone, panels `#0d0f16` / `#151824`,
  hairlines `#232736` and 8% white. Generated media carries all the colour.
- **Signature:** one aurora gradient (mint `#6ff2cc` -> violet `#9a8cff` -> rose `#ff86c1`), used only
  for the primary action, logo, key numbers and selection rings. Solid accent for focus is mint.
- **Surfaces:** frosted "glass" panels (translucent fill, hairline, soft inner highlight), 18 px card
  radius, 24 px for the composer. A fixed, cheap ambient aurora sits behind the app.
- **Type:** system stack only (no web fonts, no third-party requests). Large tight-tracked heroes,
  small uppercase labels at 0.08 em.
- **Layout:** Studio is a hero plus one large composer (model chip -> picker dialog, ratio, size,
  count/length, resolution, one aurora Generate button), then a media-first results grid whose
  actions appear as icon buttons over the image (always visible on touch). Mobile gets a bottom tab bar.
- **Components:** `ui.tsx` (Button, Card, PageHeader, EmptyState, Segmented, Badge, inputs),
  `icons.tsx` (original stroke icons), `ModelPicker.tsx` (accessible dialog with focus trap, Esc).
- **Accessibility:** text colours keep >= 4.5:1 on the stage, visible focus ring, `aria-pressed`
  toggles, labelled icon-only buttons, `prefers-reduced-motion` respected.
- **Charts:** series colours stay a CVD-safe gold/blue pair, separate from the brand gradient.

## Neon Coast (v3, current, temporary)

> **Status:** a temporary production theme that follows the current synthwave/coastal-night trend.
> A full redesign may replace it next month. Earlier directions are archived in git and can be
> restored or mixed: **Solar Darkroom** (black + yellow-lime accent `#d4ff3a`, commit `67c5c8c`,
> PR #20) and **Mono** (black stage, grey layers, white pill actions, Geist; commit `f06e03d`,
> PR #22, branch `feat/mono-redesign`). Keep new pages on the shared tokens (`accent`, `aurora`,
> `glass`, `btn-aurora`) so a theme swap stays a CSS change, and keep scenery in `Scenery.tsx` only.

A night sky over a sunset coast, in the spirit of 80s synthwave posters. All artwork (sun, palms,
skyline, grid) is original SVG/CSS drawn for Aurevid; no game, film or brand artwork is used.

- **Stage:** deep purple `#12071f`, panels `#1a0b2c` / `#24113b`, hairlines `#3a2257`, text `#f6ecff`,
  muted `#b3a0cc`. A fixed violet-to-sunset sky drifts slowly behind the app, with faint scanlines.
- **Colour:** pink `#ff3e8a` (accent), orange `#ff9a3c`, teal neon `#19e3d3` (focus ring, secondary
  glow). The sunset gradient (pink -> orange) fills primary buttons; the headline gradient runs gold ->
  orange -> pink -> violet. Chart series are an orange/teal pair.
- **Type:** Anton (OFL) for uppercase poster headlines, Kaushan Script (OFL) for one brush accent line
  per hero, Geist (OFL) for body text. Anton and Kaushan have no Cyrillic, so Russian headings fall
  back to Geist glyph by glyph.
- **Scenery:** `components/Scenery.tsx` stages the landing hero: a striped sun (`.sun-glow`), a
  skyline with flickering windows (`.neon-flicker`), two swaying palms (`.palm-sway`) and a scrolling
  perspective grid (`.grid-floor`). Hero sample tiles use the `.postcard` frame.
- **Motion:** every scenery animation and the sky drift are disabled under `prefers-reduced-motion`.
- **Token names** (`accent`, `aurora`, `glass`, `btn-aurora`) are unchanged, so every page follows.

### Neon Coast additions (workspace, marquee, mono data)

Borrowed ideas, built on the shared tokens so a theme swap stays a CSS change:

- **Lime `--color-accent-4` (`#c8ff2e`)**, owner-approved, used sparingly: ok-status dots (available provider in
  `ModelPicker`, hero tile badges), "live/ready" badges (`Badge tone="live"`, the marquee header) and key highlights. Never a main button colour.
- **Mono data font:** `--font-mono` = JetBrains Mono Variable (`@fontsource-variable/jetbrains-mono`) for prompt counters,
  prices/credits, times and model names. Headlines stay Anton, body Geist.
- **`ModelMarquee`** (landing, under the hero): slow endless strip of model chips (mono text, provider dot, faded edges via
  `mask-image`, list duplicated for a seamless loop, paused on hover). `prefers-reduced-motion` turns it into a static wrapping list.
  It lists only what the registry really offers, from the public, credential-free `GET /api/catalog/models`
  (same `enabled_providers()` as `/api/providers`, so the commercial-use filter applies). Nothing is hard-coded; if the request
  fails the strip is not rendered.
- **Routes:** `/` is always the Landing page (signed-in people get a "Create" button instead of sign-up links); the Studio lives at
  `/create` (`/studio` redirects there, router state kept). Sign-in and register land on `/create` unless `state.next` says otherwise,
  and a protected page remembers where you wanted to go. The logo goes to `/` and scrolls to the top, even when already there.
- **Favicon:** original Neon Coast mark (striped pink-to-orange sun and a teal horizon line on dark purple), `favicon.svg` plus
  `favicon-32.png` and `apple-touch-icon.png`; `index.html` links carry `?v=2` to bust caches.
- **Studio workspace (lg+):** two columns. Left = composer (mode, model, prompt, options, presets), right = sticky
  `ResultPanel` with states empty ("Ready to generate"), generating (neon orbit), error (credits-exhausted gets its own card
  linking to `/credits`) and result (the latest job rendered by the existing `JobCard`). The panel only reads state `Studio`
  already has (`focusId`, `error`, `compareRun`); generation logic is unchanged. Below lg it stays one column as before
  (panel hidden, inline error, compare results below the composer). No resizable handle.
- **Multi-scene video (video mode):** a second `Segmented` (Single / Multi-scene) under the Image/Video one, shown only when a
  text-to-video model offers 5 s clips (`storyCapable`). Multi-scene swaps the single prompt for 2-4 numbered scene fields
  (add / remove), a fixed "5 s per scene" chip and a summed price line; the start-image upload, presets, examples, upscale and
  voice button are hidden. `StoryCard` (glass card, same radius as `JobCard`) shows a progress bar while generating or joining,
  the joined video with Download/Delete when ready, and a per-scene grid (first-frame thumbnail, status chip, Retry on a failed
  scene). It appears in `ResultPanel`, in Studio's "Recent results" (merged with jobs by date) and in a "Multi-scene videos"
  block at the top of History. Scene jobs are hidden from `GET /api/jobs` (they live inside their story).
- **Blueprint sheet:** `.blueprint` on the inner-page wrapper in `Layout`: thin grid and heavier lines every 128 px from
  `--hairline`, ruler ticks on the top and left edges, sides faded. Not used on the landing hero (it keeps the scenery).
- **Provider dots:** `ProviderDot` / `--color-provider-1..5` (plain `:root` variables, because `@theme` drops unused
  variables), shown in `ModelPicker`, `ModelSwatch` and the marquee.


## Publishable output: honest sizes, Draft badge, Publish quality, video tiers

Why: a creator wants output that is "not even slightly blurry". Wan on Modal made 832x480 while the job
said "large" 1344x768, and FLUX.1 schnell (4 steps) gives soft detail. 480p cannot honestly become
publishable by upscaling, so the UI says what a result is instead.

- **Honest sizes.** Every model has a real output size: `ModelInfo.fixed_dimensions` (models that ignore
  the Size choice: Modal and GPU-worker Wan 832x480, schnell 1024x1024), `resolution_sizes` (Seedance),
  else `dimensions(aspect, size)`. `prepare_job` stores that as `params.width/height` (the *expected* real
  size; `gen_width/gen_height` is what the provider is asked for). When a job finishes, the worker replaces
  it with the file's own size: images from the decoded pixels, video from the MP4 header (`images.probe_mp4_size`,
  no ffmpeg needed; the stored `Asset` has used the same numbers since this change). `params.size` keeps the
  requested label for Remix only. The UI shows `W x H` and the class (480p, 720p, 1080p, 2K, 4K) from the real
  numbers (`frontend/src/quality.ts`), and hides the Size select for models where it changes nothing.
- **Draft badge.** `isDraft`: video with a short side under 720 px, or an image under 1024 px. Shown on the
  result card (top-left), in the detail dialog, in the output-size chip of the composer and on a multi-scene
  video. It uses the real asset size, so History and Studio agree.
- **Image "Publish quality".** One toggle in the image composer. It selects the best model that is free to
  use (provider tier `free`), `commercial_use=="yes"` and has `publish_max_side` (`registry.publish_image_model`;
  today FLUX.2 klein 4B on Cloudflare, 1920 px max, from the Workers AI docs). The job renders at the largest
  size of the chosen ratio on the 64 px grid (1920x1920, 1920x1088, ...) and then runs the existing Real-ESRGAN
  upscaler to 2K (2560 px long side, default) or 4K, with the same deadline (`UPSCALER_TIMEOUT_SECONDS`,
  checked between tiles), CPU class (`cpu_job_concurrency`), queue admission and daily limit as any upscaled
  image. Publish feeds the network the real render, capped at 1280 px (2K) or 1920 px (4K) per side, and then
  Lanczos-resizes the 4x result, so detail is not thrown away first (`PUBLISH_NET_LONG`). One image per job.
  The delivered asset is the upscaled one; the original is **not** kept (a second asset would break the
  one-asset-per-output model behind refunds and the card badges). Error codes: `quality_unsupported`.
- **No free-share loophole.** A 1920 px klein image costs about 3x a 1024 px one in Neurons. The provider's
  `quota_weight` (area in 512 px tiles x 26.05 Neurons / 147) is stored as `params.quota_weight`; the daily share,
  the worker's server-key fallback and the quota learner count the job that many times.
- **Video tiers (Seedance via OpenRouter, BYOK).** `providers/openrouter_video.py`. Studio video mode has a
  quality selector: Draft (Mini 480p), **Standard** (Mini 720p, the default), Publish (2.5 Flash 720p), Premium
  (2.5 1080p, explicit, shows a dollar warning). A tier is just model + resolution; the API takes
  `resolution` (`resolution_unsupported`). Cost is shown in cents under a dollar ("23c"), exact USD in the
  tooltip, from `usd_per_second` in the catalog (tokens per second x price x 1.07 margin); the provider's own
  `usage.cost` is stored as `params.usd_cost` and shown as "billed". Credits: model cost + `resolution_credits`.
  Wan on Modal stays available but is listed last and never preselected.
- **Money safety of the adapter.** An ambiguous submit (timeout, dropped connection, 5xx) is never retried; only a
  clear 429 is retried with backoff; a poll that times out is not retried; a failed/cancelled/expired job is
  an error with a refund (once, idempotency key `refund:<job>`); the clip is downloaded server-side with the
  Authorization header, and the key only ever goes to openrouter.ai. The owner key is optional and off by
  default; with it set, only the Mini 480p draft runs and only within a per-user allowance (0 by default).
- **Stories** carry `resolution` per scene (retry too) and use the Seedance models (5 s is one of their
  durations). Clips of one model share a layout, so the ffmpeg join is a lossless copy; mixed sizes re-encode
  to the first clip's size (a 1080p re-encode is the slow case, `STITCH_TIMEOUT_SECONDS`).
