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

## Aurevid Dark Studio (v4, current)

> **Direction:** "dark studio": quiet, neutral, premium; colour appears only where it means something.
> Replaces Neon Coast. Removes hot-pink/orange/teal neon accents, the Anton poster display font,
> Kaushan script and the blueprint grid/scenery. Headings use Geist 600 with tight tracking (-0.02em);
> numbers use tabular figures (`font-variant-numeric: tabular-nums`).

### 1. Palette & Surface Tokens
| Token | Value | Role |
|---|---|---|
| `--bg` | `#09090b` | Page background (near-black, slightly cool) |
| `--surface-1` | `#111113` | Panels, cards, modal backings |
| `--surface-2` | `#17171a` | Inputs, tiles, secondary controls |
| `--surface-3` | `#1f1f23` | Hover states, raised elements |
| `--border` | `rgb(255 255 255 / 0.08)` | Subtle component borders |
| `--border-strong` | `rgb(255 255 255 / 0.16)` | Active/focus component borders |
| `--text` | `#f4f4f5` | Primary body text and headings |
| `--text-2` | `#a1a1aa` | Secondary labels, descriptions |
| `--text-3` | `#6b6b74` | Tertiary labels, captions, timestamps |
| `--accent` | `#c8ff2e` | Primary CTA, active nav indicator, focus ring, selected state ONLY |
| `--accent-ink` | `#0b0f00` | Text on accent |
| `--info` | `#6aa8ff` | Informational links, chips |
| `--success` | `#4ade80` | Success states, ready badges |
| `--warning` | `#fbbf24` | Warning banners, rate alerts |
| `--danger` | `#f87171` | Error states, destructive actions |

### 2. Radii & Elevation
- `--radius-sm`: `8px` (chips, compact buttons, badges)
- `--radius-md`: `12px` (buttons, input tiles, popovers)
- `--radius-lg`: `16px` (cards, panels)
- `--radius-xl`: `24px` (modals, sheets)
- `--shadow-pop`: `0 12px 40px rgb(0 0 0 / 0.5)`

### 3. Typography
- `--font-sans`: `"Geist Variable"`, `"Geist"`, system-ui, sans-serif
- `--font-mono`: `"JetBrains Mono Variable"`, `"JetBrains Mono"`, ui-monospace
- Headings: Geist 600, tight tracking (`-0.02em`), sizes on a 12/14/16/20/28/40/56 scale
- Body: 14–15px
- Numbers: `font-variant-numeric: tabular-nums` for all numbers (credits, costs, timers, counters)

### 4. Buttons & Interaction
- **Primary button ("Generate"):** solid accent button (`--accent`, `#c8ff2e`) with a 2px lower lip (`box-shadow: inset 0 -2px 0 rgb(0 0 0 / 0.28)`); pressing removes the lip (`translateY(1px)` and flat shadow).
- **Secondary button:** surface-2 (`#17171a`) with 1px border.
- **Ghost button:** transparent with muted text, hover background surface-2.
- **Focus ring:** 2px solid `--accent`. Disabled: 50% opacity.
- **Motion:** 120–180ms ease-out for hover/press, 220ms for popovers/modals; respects `prefers-reduced-motion`.

### 5. Logo Mark & Favicon
A clean geometric "A" mark in `--accent` (`#c8ff2e`) on `--bg` (`#09090b`) background, matching the favicon.

### 6. Light Theme Tokens (Archived for future reference)
```css
/*
:root[data-theme="light"] {
  --bg: #fafafa;
  --surface-1: #ffffff;
  --surface-2: #f4f4f5;
  --surface-3: #e4e4e7;
  --border: rgb(0 0 0 / 0.08);
  --border-strong: rgb(0 0 0 / 0.16);
  --text: #09090b;
  --text-2: #71717a;
  --text-3: #a1a1aa;
  --accent: #18181b;
  --accent-ink: #ffffff;
  --info: #2563eb;
  --success: #16a34a;
  --warning: #d97706;
  --danger: #dc2626;
}
*/
```


### 7. Layout & Core Pages (Dark Studio v4)

- **Studio Generator (`/create`):**
  - **Two-Column Workspace (lg+):**
    - Left Control Panel (400–440px, sticky): Mode tabs (Image / Video), Scene tabs (Single / Multi-scene / Director), reference dropzones (start/end image frames with upload and preview), prompt card with autogrow textarea, char counter, voice button, audio toggle, Expand prompt button with Undo, model selector row, setting tiles 2-column grid (aspect ratio popover with shape icons, duration popover, resolution popover with draft badge, quality tier), and sticky bottom action bar with primary Generate button and cost line.
    - Right Canvas: Top toolbar with History vs. How-it-works tabs, filter chips (All / Image / Video / Favorites), density grid switcher (2, 3, or 4 columns), list/grid view toggle. Result tiles render live status, progress bar, action overlay, and detailed metadata.
  - **Lightbox Modal:** Fullscreen blurred backdrop, media stage, glass side panel with prompt (one-click copy), technical details (model, dimensions, duration, cost, timestamp), action grid (Recreate, Animate, Upscale, Download, Share, Favorite), and keyboard navigation (Left/Right arrows, Esc to dismiss, focus trapped).
  - **Mobile (<1024px):** Control panel stacks naturally above the results canvas; Generate bar sticks above the mobile bottom tab bar; popovers and model picker open as accessible bottom sheets. No horizontal scroll at 390px.

- **Director Flow (`/create?mode=director`):**
  - A guided storyboarding flow accessible via the "Director" tab in Video mode.
  - Chat-style idea prompt input with video duration selection (5s, 10s, 15s), aspect ratio, and model tier.
  - One-click "Draft plan" calls `/api/prompt/expand` to generate a structured **Plan Card** detailing:
    1. Opening frame (editable inline).
    2. Timeline beats table (time ranges, scene names, and prompt descriptions editable per row).
    3. Look & cinematography style (editable inline).
    4. Soundscape & audio cues (editable inline).
  - Real-time cost estimate line with model label and USD/credits.
  - **Approve & Generate** automatically determines payload: creates a single-clip job when duration <= model max clip duration, or decomposes into a multi-scene Story when duration exceeds single-clip maximums.
  - Clean hint banner with link to Settings/Account when prompt expansion is unavailable (`expand_available=false`).

- **Home / Explore (`/`):**
  - Hero with headline, value proposition, and an interactive prompt bar that redirects to `/create` with the text prefilled.
  - 3 "Start here" cards for quick access to Image generation, Video clips, and Multi-Scene stories.
  - Media wall showcasing 10 sample outputs using Aurevid's built-in sample files and smooth gradients (no third-party media).
  - `ModelMarquee` dynamic strip streaming live models from `/api/catalog/models`.
  - 3-step workflow strip and Free & Open Source AGPL-3.0 banner.

- **Pricing (`/pricing`):**
  - Credit pack cards for local inPAY payments.
  - Transparent "What 1 credit buys" comparison table in cents across image and video tiers.
  - BYOK (Bring Your Own Key) zero-markup explainer card.
  - Interactive FAQ accordion for common billing and model questions.

- **Library (`/library`):**
  - User assets grid with filter chips (All, Image, Video, Story, Favorites).
  - List / grid view switcher.
  - Multi-asset selection mode enabling bulk download and bulk deletion.
  - Clean empty state with quick link to `/create`.

- **Authentication (`/auth`):**
  - Centered Dark Studio card with email and password inputs, consent checkbox, and descriptive error states.



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

## E2E Testing & Screenshot Pipeline

Browser end-to-end testing and canonical UI screenshot capturing are managed through Playwright (`@playwright/test@1.65.1`).

### Running E2E Tests
Ensure the backend (running with `MOCK_PROVIDER_ENABLED=true` on port 8000) and frontend Vite dev server (port 5173) are active:
```bash
cd frontend
npm run e2e
```
This runs the full test suite across Desktop (1440x900) and Mobile (390x844) projects:
- `no-hscroll.spec.ts`: Asserts `document.documentElement.scrollWidth <= window.innerWidth` across all public and authenticated routes (`/`, `/pricing`, `/auth`, `/library`, `/create`, `/create?mode=director`).
- `keyboard.spec.ts`: Asserts accessible modal focus trapping (Tab/Shift+Tab cycles only within dialog) and Esc dismissal restoring focus to the trigger button for both `ModelPicker` and `JobDialog` (Lightbox).
- `states.spec.ts`: Verifies real UI job lifecycle states (`queued`, `running`, `ready`, and `failed`) using the deterministic mock provider.

### Capturing UI Screenshots
Run the screenshot capture suite:
```bash
cd frontend
SHOTS=1 npm run e2e
```
This generates 20 canonical full-page screenshots in `docs/img/ui-v2/` (10 views x 2 viewports):
- `desktop-home.png` / `mobile-home.png`
- `desktop-pricing.png` / `mobile-pricing.png`
- `desktop-auth.png` / `mobile-auth.png`
- `desktop-studio-image.png` / `mobile-studio-image.png`
- `desktop-studio-video.png` / `mobile-studio-video.png`
- `desktop-model-picker.png` / `mobile-model-picker.png` (inactive section expanded)
- `desktop-director.png` / `mobile-director.png`
- `desktop-library.png` / `mobile-library.png`
- `desktop-history-tiles.png` / `mobile-history-tiles.png` (one ready tile, one running tile)
- `desktop-lightbox.png` / `mobile-lightbox.png`

All generated images are verified to be non-blank and byte-distinct (`verify_shots.py` cmp check: 0 identical pairs).
