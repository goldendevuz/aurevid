# Model & provider licenses

Checked on 2026-11-17. Licences and service terms change, so re-check before a commercial launch.
This is an engineering record, not legal advice.

| Provider (adapter) | Model | Model licence | Commercial use of outputs | Service terms | Default |
|---|---|---|---|---|---|
| Cloudflare Workers AI (`cloudflare`) | `@cf/black-forest-labs/flux-1-schnell` | Apache-2.0 (FLUX.1 [schnell] weights) | **Yes** by model licence | Cloudflare Workers AI terms; free allocation of 10,000 Neurons/day per account, shared across all models, requests fail above it on the Free plan | **On** (needs a CF account ID + token: server or BYOK) |
| fal.ai (`fal`) | `fal-ai/flux/schnell` | Apache-2.0 | **Yes** by model licence | fal.ai terms; **paid**, billed to the user's own key | **Off** (`FAL_ENABLED=false`) |
| fal.ai (`fal`) | `fal-ai/wan/v2.2-5b/text-to-video` | Apache-2.0 (Wan 2.2 TI2V-5B weights) | **Yes** by model licence | fal.ai terms; **paid**, $0.15 per video per fal's model page (2026-11-17) | **Off** |
| fal.ai (`fal`) | `fal-ai/wan/v2.2-a14b/image-to-video` | Apache-2.0 (Wan 2.2 I2V-A14B weights) | **Yes** by model licence | fal.ai terms; **paid**, $0.04-0.08 per video second by resolution | **Off** |
| fal.ai (`fal`) | `fal-ai/kling-video/v2.6/pro/text-to-video` | Proprietary hosted API (Kling, via fal.ai); no weights are distributed or used by us | **Unclear**: check Kling/fal.ai terms before commercial use | fal.ai terms; **paid**, fal lists about $0.07/s audio off and $0.14/s audio on (third-party and fal page figures, not verified); generates native audio | **Off** |
| Pollinations (`pollinations_video`) | `alibaba/wan-2.2-fast` | Apache-2.0 (Wan 2.2 weights); hosted by Pollinations | **Unclear**: check Pollinations terms | Billed to the user's own Pollinations key (pollen); cost per clip not verified; model list read from the API 2026-11-18 | **On** (`POLLINATIONS_VIDEO_ENABLED`), BYOK only |
| Pollinations (`pollinations_video`) | `bytedance/seedance-2.0-mini` | Proprietary hosted API (ByteDance, via Pollinations) | **Unclear**: check Pollinations and ByteDance terms | Billed to the user's own Pollinations key; cost not verified | **On**, BYOK only |
| fal.ai (`fal`) | `fal-ai/kling-video/v2.6/pro/image-to-video` | Proprietary hosted API (Kling, via fal.ai); no weights are distributed or used by us | **Unclear**: check Kling/fal.ai terms before commercial use | fal.ai terms; **paid**, same pricing as above; generates native audio | **Off** |
| Local, on our server (`local`) | Real-ESRGAN `realesr-general-x4v3` (4x upscaler, ONNX, CPU) | BSD-3-Clause (c) 2021 Xintao Wang | **Yes** | none: runs on your server, no API | **On** (`UPSCALER_ENABLED`) |
| fal.ai (`fal`) | Topaz video upscale (`fal-ai/topaz/upscale/video`, model "Proteus") for 4K/8K video | Proprietary service | **Unclear**: output terms not stated on fal's model page | **paid**: $0.08 per output second above 1080p, per pass (fal model page, 2026-11-17) | **Off** (`FAL_VIDEO_UPSCALE_ENABLED=false`) |
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
- **Not used:** LTX-2 / LTX-2.x (native 4K video). Its *LTX-2 Community License* allows free
  commercial use only below USD 10M annual revenue and output ownership is not clearly stated, so
  it is conditional, not permissive.
- fal image-to-video sends the start frame as a base64 data URI. fal documents data URIs as accepted
  by *some* models; this was not verified live for Wan 2.2 I2V (no key in CI).
- Pollinations: no first-party terms found in search. **Rule applied: unclear licence → disabled by
  default.** Enable only for personal testing until its terms are reviewed.

## Rules for adding a model

1. Record the model licence and the provider's terms here **before** enabling it.
2. Set `commercial_use` in the adapter's `ModelInfo` to `yes`, `no` or `unclear`; the UI shows it.
3. If either the licence or the terms are unclear, ship the adapter disabled by default.
4. Never add a model whose licence forbids the hosted use we make of it.
