# Model & provider licenses

Checked on 2026-11-17; Cloudflare additions (FLUX.2 klein 4B, Qwen 3.8 27B alt text, Whisper) on 2026-11-20. Licences and service terms change, so re-check before a commercial launch.
This is an engineering record, not legal advice.

| Provider (adapter) | Model | Model licence | Commercial use of outputs | Service terms | Default |
|---|---|---|---|---|---|
| Cloudflare Workers AI (`cloudflare`) | `@cf/black-forest-labs/flux-1-schnell` | Apache-2.0 (FLUX.1 [schnell] weights) | **Yes** by model licence | Cloudflare Workers AI terms; free allocation of 10,000 Neurons/day per account, shared across all models, requests fail above it on the Free plan | **On** (needs a CF account ID + token: server or BYOK) |
| Cloudflare Workers AI (`cloudflare`) | `@cf/black-forest-labs/flux-2-klein-4b` (text-to-image and "Edit with text") | Apache-2.0 (FLUX.2 [klein] 4B weights) | **Yes**: weights Apache-2.0; BFL terms linked from the CF page claim no ownership of outputs | Same 10,000 Neurons/day as schnell (shared); ~104 Neurons per 1024px image, +5.37 per input tile when editing | **On** |
| Cloudflare Workers AI (`cloudflare`) | `@cf/qwen/qwen3.8-27b` (alt text: image → short description) | Apache-2.0 (Qwen/Qwen3.8-27B model card) | **Yes** by model licence | Same shared allocation; ~25-40 Neurons per description (image downscaled to 512px, thinking off, ≤120 output tokens) | **On** (`ALT_TEXT_ENABLED`) |
| Cloudflare Workers AI (`cloudflare`) | `@cf/openai/whisper-large-v3-turbo` (voice prompts, speech → text) | MIT (openai/whisper-large-v3-turbo model card) | **Yes** by model licence | Same shared allocation; 46.63 Neurons per audio minute (≤30 s clips, 6/min and 40/day per user) | **On** (`VOICE_ENABLED`) |
| fal.ai (`fal`) | `fal-ai/flux/schnell` | Apache-2.0 | **Yes** by model licence | fal.ai terms; **paid**, billed to the user's own key | **On** (`FAL_ENABLED`, owner decision 2026-11-17), BYOK only |
| fal.ai (`fal`) | `fal-ai/wan/v2.2-5b/text-to-video` | Apache-2.0 (Wan 2.2 TI2V-5B weights) | **Yes** by model licence | fal.ai terms; **paid**, $0.15 per video per fal's model page (2026-11-17) | **On**, BYOK only |
| fal.ai (`fal`) | `fal-ai/wan/v2.2-a14b/image-to-video` | Apache-2.0 (Wan 2.2 I2V-A14B weights) | **Yes** by model licence | fal.ai terms; **paid**, $0.04-0.08 per video second by resolution | **On**, BYOK only |
| fal.ai (`fal`) | `fal-ai/kling-video/v2.6/pro/text-to-video` | Proprietary hosted API (Kling, via fal.ai); no weights are distributed or used by us | **Unclear**: check Kling/fal.ai terms before commercial use | fal.ai terms; **paid**, fal lists about $0.07/s audio off and $0.14/s audio on (third-party and fal page figures, not verified); generates native audio | **Hidden** (commercial use unclear, rule 3) |
| Modal (`modal_video`) | `wan-2.2-ti2v-5b` | Apache-2.0 (Wan 2.2 TI2V-5B weights, Wan-AI/Wan2.2-TI2V-5B-Diffusers) | **Yes** by model licence | Runs in the user's own Modal workspace, paid from their Modal credit; no third party sees prompts except Modal | **On** (`MODAL_VIDEO_ENABLED`), BYOK only |
| Modal (`modal_video`) | `ltx-2.3` (LTX-2.3 22B distilled, video **with audio**) | **LTX-2 Community License Agreement** (Lightricks, 2026-01-05) for the weights; repo code is Apache-2.0; the Gemma text encoder stays under Google's Gemma terms | **Unclear (conditional)**: free only for entities with annual revenue below USD 10,000,000 (incl. affiliates); at or above it a paid commercial licence from Lightricks is required; outputs: "Licensor claims no rights in the Output" but you are accountable for input and use | Runs in the user's own Modal workspace (same terms as Wan above); hosting for third parties (SaaS) is allowed only if the licence text and Attachment A use restrictions are passed on to users; ~32 GB+ VRAM | **Off / hidden** (`commercial_use="unclear"`, rule 3), not enabled; see Evidence |
| GPU worker (`gpu_worker`) | `wan-2.2-ti2v-5b` | Apache-2.0 (Wan 2.2 TI2V-5B weights, Wan-AI/Wan2.2-TI2V-5B-Diffusers) | **Yes** by model licence | Runs on a GPU machine the owner operates (`deploy/gpu-worker/`); no third party sees prompts. Free for users (0 credits); the owner pays only electricity. The worker is trusted with prompts and start images, so only the owner's machine holds the token | **Off** until `GPU_WORKER_TOKEN` is set |
| Pollinations (`pollinations_video`) | `alibaba/wan-2.2-fast` | Apache-2.0 (Wan 2.2 weights); hosted by Pollinations | **Unclear**: check Pollinations terms | Billed to the user's own Pollinations key (pollen); cost per clip not verified; model list read from the API 2026-11-18 | **Off** (`POLLINATIONS_VIDEO_ENABLED=false`), hidden (rule 3) |
| Pollinations (`pollinations_video`) | `bytedance/seedance-2.0-mini` | Proprietary hosted API (ByteDance, via Pollinations) | **Unclear**: check Pollinations and ByteDance terms | Billed to the user's own Pollinations key; cost not verified | **Hidden** (commercial use unclear, rule 3) |
| fal.ai (`fal`) | `fal-ai/kling-video/v2.6/pro/image-to-video` | Proprietary hosted API (Kling, via fal.ai); no weights are distributed or used by us | **Unclear**: check Kling/fal.ai terms before commercial use | fal.ai terms; **paid**, same pricing as above; generates native audio | **Hidden** (commercial use unclear, rule 3) |
| Local, on our server (`local`) | Real-ESRGAN `realesr-general-x4v3` (4x upscaler, ONNX, CPU) | BSD-3-Clause (c) 2021 Xintao Wang | **Yes** | none: runs on your server, no API | **On** (`UPSCALER_ENABLED`) |
| fal.ai (`fal`) | Topaz video upscale (`fal-ai/topaz/upscale/video`, model "Proteus") for 4K/8K video | Proprietary service | **Unclear**: output terms not stated on fal's model page | **paid**: $0.08 per output second above 1080p, per pass (fal model page, 2026-11-17) | **Off** (`FAL_VIDEO_UPSCALE_ENABLED=false`), hidden (rule 3) |
| Pollinations (`pollinations`) | `flux` | Not stated by the service in a form we could verify | **Unclear** | We could not find Pollinations' own terms of service; the anonymous tier returned HTTP 402 after one image during testing | **Off** (`POLLINATIONS_ENABLED=false`) |
| Offline demo (`demo`) | `loop` video | Our clip (rendered with ffmpeg's `gradients` source, AGPL-3.0-or-later) | Yes | n/a | Dev only |
| Offline demo (`demo`) | gradient sketch | Our code (AGPL-3.0-or-later), no AI model | Yes | n/a | Dev only; refused when `APP_ENV=prod` |

## Evidence

- FLUX.1 [schnell] is published by Black Forest Labs with `license: apache-2.0` in its model card
  (revisions of `huggingface.co/black-forest-labs/FLUX.1-schnell`). The live page is gated and we could
  not read its current tag directly. Note: **FLUX.1 [dev] is non-commercial**; do not add it without a
  commercial licence.
- Cloudflare free allocation: developers.cloudflare.com/workers-ai/platform/pricing/
  (10,000 Neurons/day, resets 00:00 UTC). A 1024×1024 image at 4 steps costs roughly 58 Neurons
  (third-party estimate), so about 170 images/day per account.
- Wan 2.2 (TI2V-5B, I2V-A14B): Apache-2.0 per the Wan-AI model card revisions on Hugging Face and press
  coverage; the live official card was not read directly. Turbo/distilled community variants may
  carry different licences and are not used.
- **Video has no free tier we could verify.** Cloudflare Workers AI now lists third-party video
  models (e.g. `lightricks/ltx-2-5-fast`, $0.09 per second at 720p on its model page), but neither the
  model page nor the pricing page says the 10,000 Neurons/day free allocation covers them, and output
  terms are not stated. **Rule applied: unclear → not integrated.** Video runs on fal.ai with the
  user's own key, or on the offline demo in development.
- **4K/8K images** come from the local Real-ESRGAN upscaler: official checkpoint from the
  Real-ESRGAN v0.2.5.0 release, converted by `scripts/convert_realesrgan.py`; hashes and licence in
  `backend/app/upscale/`. Free, offline, commercial use allowed (BSD-3, keep the notice).
- **4K/8K video** has no free path. It uses Topaz upscaling on fal (720p → 4K = one 3x pass;
  8K = 4x + 1.5x passes). Topaz/fal output terms are not stated on the model page, so it is
  **opt-in** (`FAL_VIDEO_UPSCALE_ENABLED`). 8K output is H.265 and may not play in every browser.
- **Not used:** MMAudio (video-to-audio). Code is MIT but the checkpoints are CC-BY-NC 4.0
  (README of hkchengrex/MMAudio, read 2026-11-20), so outputs cannot be used commercially.
  Its Modal script was removed; Modal clips are silent.
- **Prepared, NOT enabled:** LTX-2.3 (Lightricks, 22B, video + audio) as an optional second Modal
  model (`deploy/modal/ltx_video.py`, `ltx-2.3`). Licence file read 2026-11-21
  (github.com/Lightricks/LTX-2/blob/main/LICENSE-2, "LTX-2 Community License Agreement", 2026-01-05):
  free use for any purpose subject to Attachment A (use restrictions); entities with annual revenue of
  at least USD 10,000,000 (affiliates counted together) need a paid Commercial Use Agreement, otherwise
  breach with liquidated damages of double the fees; hosting for third parties (SaaS) is allowed if
  the use restrictions are made enforceable in our terms and users get a copy of the licence;
  "Licensor claims no rights in the Output" (section 5); Lightricks may update/restrict remotely
  (section 6). The Gemma text encoder keeps Google's licence. Official need: 32 GB+ VRAM. Because the
  right to use it depends on the operator's revenue, it is recorded as `commercial_use="unclear"`
  (conditional), so the registry hides it (rule 3) and only `ALLOW_UNCLEAR_MODELS=true` (local testing,
  refused in prod) shows it. **Owner exception:** the owner may record a documented, dated exception
  here (the entity is under the revenue threshold, Attachment A is passed on to users, Gemma terms
  checked) and then change `commercial_use` to `yes` in code; until then it stays off. Previously this
  line said "not used"; the licence is conditional, not permissive, which is why it stays unclear.
- fal image-to-video sends the start frame as a base64 data URI. fal documents data URIs as accepted
  by *some* models; this was not verified live for Wan 2.2 I2V (no key in CI).
- Pollinations: no first-party terms found in search. **Rule applied: unclear licence → disabled by
  default.** Enable only for personal testing until its terms are reviewed.

- **Cloudflare additions, checked 2026-11-20** (official pages fetched with curl):
  - FLUX.2 [klein] 4B: CF model page developers.cloudflare.com/workers-ai/models/flux-2-klein-4b/
    links "Terms and License" to bfl.ai/legal/terms-of-service ("We claim no ownership rights in
    and to Your Content", i.e. inputs and outputs); model card huggingface.co/black-forest-labs/FLUX.2-klein-4B
    has `license: apache-2.0` ("Fully open under Apache 2.0 ... production use"). Workers AI
    specifics from the CF changelog 2026-01-15: multipart input, fixed 4 steps, up to 4 reference
    images, each "smaller than 512x512". **Not used:** FLUX.2 [dev] and FLUX.2 [klein] 9B
    (non-commercial licences).
  - Alt text: Qwen 3.8 27B, CF page developers.cloudflare.com/workers-ai/models/qwen3.8-27b/ (Vision:
    Yes, `image_url` input), model card huggingface.co/Qwen/Qwen3.8-27B `license: apache-2.0`.
    **Rejected:** Llama 3.2 11B Vision (Llama 3.2 licence: 700M MAU cap and no rights for EU-domiciled
    entities to the multimodal models), Llama 4 Scout (Llama 4 licence, MAU cap and branding
    duties), Moondream 3.1 (Moondream licence, not permissive), LLaVA 1.5 (Llama 2 base, planned
    CF deprecation 2026-11-20), Mistral Small 3.1 (Apache-2.0, but the CF schema takes no image
    input), Gemma 3 / UForm (removed from the CF catalogue).
  - Whisper large-v3-turbo: CF page developers.cloudflare.com/workers-ai/models/whisper-large-v3-turbo/,
    model card huggingface.co/openai/whisper-large-v3-turbo `license: mit`.
  - Neuron prices: developers.cloudflare.com/workers-ai/platform/pricing/ (klein 4B: 5.37 Neurons per
    input 512px tile, 26.05 per output tile; schnell: 4.80 per tile + 9.60 per step; Qwen 3.8 27B:
    40,909 / 290,909 Neurons per M input / output tokens; Whisper turbo: 46.63 per audio minute).
    All share the account's 10,000 Neurons/day, so the quota prior is 68 outputs/day (worst case:
    klein image + alt text, ~147 Neurons); see `backend/app/providers/cloudflare.py`.
  - Not verified live (no key in CI): whether Whisper on Workers AI decodes WebM/Opus and MP4/AAC
    as recorded by browsers; the request shapes follow the published JSON schemas.

## Rules for adding a model

1. Record the model licence and the provider's terms here **before** enabling it.
2. Set `commercial_use` in the adapter's `ModelInfo` to `yes`, `no` or `unclear`; the UI shows it.
3. If either the licence or the terms are unclear, ship the adapter disabled by default.
   **Owner rule (2026-11-20, replaces the 2026-11-19 BYOK exception):** only models whose
   licence *and* service terms clearly allow commercial use are offered, whoever pays. The
   registry hides every model with `commercial_use` other than `yes`; `ALLOW_UNCLEAR_MODELS=true`
   exists for local testing only and the app refuses to start with it in prod. Currently hidden:
   Pollinations video (Wan 2.2 fast, Seedance 2.0 mini), Kling 2.6 on fal, Topaz video upscaling, LTX-2.3 on Modal (conditional licence).
4. Never add a model whose licence forbids the hosted use we make of it.
