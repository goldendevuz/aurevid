# Model & provider licenses

Checked on 2026-11-17. Licences and service terms change, so re-check before a commercial launch.
This is an engineering record, not legal advice.

| Provider (adapter) | Model | Model licence | Commercial use of outputs | Service terms | Default |
|---|---|---|---|---|---|
| Cloudflare Workers AI (`cloudflare`) | `@cf/black-forest-labs/flux-1-schnell` | Apache-2.0 (FLUX.1 [schnell] weights) | **Yes** by model licence | Cloudflare Workers AI terms; free allocation of 10,000 Neurons/day per account, shared across all models, requests fail above it on the Free plan | **On** (needs a CF account ID + token: server or BYOK) |
| fal.ai (`fal`) | `fal-ai/flux/schnell` | Apache-2.0 | **Yes** by model licence | fal.ai terms; **paid**, billed to the user's own key | **Off** (`FAL_ENABLED=false`) |
| Pollinations (`pollinations`) | `flux` | Not stated by the service in a form we could verify | **Unclear** | We could not find Pollinations' own terms of service; the anonymous tier returned HTTP 402 after one image during testing | **Off** (`POLLINATIONS_ENABLED=false`) |
| Offline demo (`demo`) | gradient sketch | Our code (AGPL-3.0-or-later), no AI model | Yes | n/a | Dev only; refused when `APP_ENV=prod` |

## Evidence

- FLUX.1 [schnell] is published by Black Forest Labs with `license: apache-2.0` in its model card
  (revisions of `huggingface.co/black-forest-labs/FLUX.1-schnell`). The live page is gated and we could
  not read its current tag directly. Note: **FLUX.1 [dev] is non-commercial**; do not add it without a
  commercial licence.
- Cloudflare free allocation: developers.cloudflare.com/workers-ai/platform/pricing/
  (10,000 Neurons/day, resets 00:00 UTC). A 1024×1024 image at 4 steps costs roughly 58 Neurons
  (third-party estimate), so about 170 images/day per account.
- Pollinations: no first-party terms found in search. **Rule applied: unclear licence → disabled by
  default.** Enable only for personal testing until its terms are reviewed.

## Rules for adding a model

1. Record the model licence and the provider's terms here **before** enabling it.
2. Set `commercial_use` in the adapter's `ModelInfo` to `yes`, `no` or `unclear`; the UI shows it.
3. If either the licence or the terms are unclear, ship the adapter disabled by default.
4. Never add a model whose licence forbids the hosted use we make of it.
