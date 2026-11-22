# SPDX-License-Identifier: AGPL-3.0-or-later
"""Cloudflare Workers AI adapter. Free daily allocation (10,000 Neurons) on CF accounts.

Image models: FLUX.1 [schnell] (text-to-image) and FLUX.2 [klein] 4B (text-to-image and editing
with a start image). Side tools on the same account: image description (alt text) with Qwen 3.8
27B and speech-to-text (voice prompts) with Whisper large-v3-turbo. Licences: MODEL_LICENSES.md.
"""

import base64
import io
import logging
import math
import re
from typing import Any

import httpx

from app.config import get_settings
from app.providers.base import (
    Credentials,
    GeneratedImage,
    GenerationRequest,
    ImageProvider,
    ModelInfo,
    ProviderError,
    ProviderInfo,
)

_ACCOUNT_RE = re.compile(r"^[a-f0-9]{32}$")
_DETAIL_MAX = 160
SCHNELL = "@cf/black-forest-labs/flux-1-schnell"
KLEIN = "@cf/black-forest-labs/flux-2-klein-4b"
CAPTION_MODEL = "@cf/qwen/qwen3.8-27b"
WHISPER_MODEL = "@cf/openai/whisper-large-v3-turbo"
# Workers AI: klein input images "must be smaller than 512x512" (changelog 2026-01-15).
KLEIN_INPUT_MAX_SIDE = 496
KLEIN_MAX_SIDE = 1920  # largest width/height Workers AI accepts for klein
NEURONS_PER_OUTPUT_TILE = 26.05  # klein 4B, per 512x512 output tile (pricing page, 2026-11-20)
QUOTA_UNIT_NEURONS = 147  # what one "output" of the free share is assumed to cost (see prior)
EDIT_OUTPUT_LONG_SIDE = 1024  # ~4 output tiles, same Neuron cost as a 1024x1024 image
ALT_TEXT_MAX = 300
_CAPTION_PROMPT = (
    "Write alt text for this image: one or two plain sentences, at most 40 words, describing "
    "what is visible (subject, setting, colours, any readable text). No preamble."
)
log = logging.getLogger(__name__)


def _error_detail(resp: httpx.Response, secrets: tuple[str, ...] = ()) -> str:
    """One short, sanitised message from Cloudflare's structured error (`errors[0].message`).

    Never the raw body; control characters are stripped, whitespace collapsed, any credential
    value that happens to be echoed is masked, and the result is length-capped.
    """
    try:
        message = str(resp.json()["errors"][0]["message"])
    except (ValueError, KeyError, IndexError, TypeError):
        return ""
    for secret in secrets:
        if len(secret) >= 8:  # real credentials are long; short values would mangle the text
            message = message.replace(secret, "***")
    message = " ".join("".join(c for c in message if c.isprintable() or c.isspace()).split())
    return message[:_DETAIL_MAX]


class CloudflareProvider(ImageProvider):
    """Images on Workers AI; `describe_image` / `transcribe` below reuse the same credentials."""

    info = ProviderInfo(
        id="cloudflare",
        name="Cloudflare Workers AI",
        tier="free",
        byok=True,
        byok_fields=["account_id", "api_token"],
        requires_key=True,
        models=[
            ModelInfo(
                id="@cf/black-forest-labs/flux-1-schnell",
                label="FLUX.1 schnell",
                license="Apache-2.0",
                commercial_use="yes",
                aspect_ratios=["1:1"],  # endpoint takes no size params; output is square
                credit_cost=1,
                fixed_dimensions={"1:1": (1024, 1024)},  # the size choice has no effect
            ),
            ModelInfo(
                id=KLEIN,
                label="FLUX.2 klein 4B",
                license="Apache-2.0",
                commercial_use="yes",
                # width/height are free, 256-1920 each (Cloudflare changelog 2026-01-15)
                aspect_ratios=["1:1", "16:9", "9:16", "4:3", "3:4"],
                credit_cost=1,
                accepts_image=True,  # "Edit with text": the start image is edited by the prompt
                publish_max_side=KLEIN_MAX_SIDE,  # "Publish quality": render at 1920, then upscale
            ),
        ],
        notes="Free daily allocation on your Cloudflare account; output is 1024x1024.",
        # Both models (and alt text) share one 10,000 Neurons/day allocation. Per Cloudflare's
        # pricing page (2026-11-20): schnell 1024px 4 steps = 4x4.80 + 4x9.60 = ~58 Neurons;
        # klein 4B 1024px = 4 output tiles x 26.05 = ~104 (+5.37 per input tile when editing);
        # alt text on a <=512px image ~25-40. Prior = worst case (klein + alt text, ~147) so the
        # free share never promises more than the account can do: 10,000 / 147 = 68 outputs/day.
        # The learner raises the estimate when more succeed (services/quota.py).
        daily_quota_prior=68,
        key_url="https://dash.cloudflare.com/profile/api-tokens",
        key_guide_url="https://developers.cloudflare.com/workers-ai/get-started/rest-api/",
    )

    def server_credentials(self) -> Credentials:
        s = get_settings()
        if s.cf_account_id and s.cf_api_token:
            return Credentials(
                {"account_id": s.cf_account_id, "api_token": s.cf_api_token}, "server"
            )
        return Credentials()

    def quota_weight(self, model_id: str, width: int, height: int) -> int:
        """A 1920 px klein image costs ~3x a 1024 px one in Neurons; the free share counts it so."""
        if model_id != KLEIN:
            return 1
        tiles = math.ceil(width * height / (512 * 512))
        return max(1, math.ceil(tiles * NEURONS_PER_OUTPUT_TILE / QUOTA_UNIT_NEURONS))

    async def generate(self, req: GenerationRequest, creds: Credentials) -> GeneratedImage:
        if req.model == KLEIN:
            result = await _run(creds, KLEIN, files=_klein_form(req), wait=90)
        else:
            # The FLUX schnell schema on Workers AI accepts only prompt + steps (verified live
            # 2026-11-17: sending "seed" returns 400 "Additional properties '/seed' not allowed").
            result = await _run(creds, req.model, json={"prompt": req.prompt, "steps": 4})
        try:
            image_b64 = result["image"]
            return GeneratedImage(base64.b64decode(image_b64, validate=True), "image/jpeg")
        except (ValueError, KeyError, TypeError) as exc:
            raise ProviderError("Unexpected response from Cloudflare") from exc


def _fit(width: int, height: int, long_side: int) -> tuple[int, int]:
    scale = long_side / max(width, height)
    return max(256, round(width * scale / 64) * 64), max(256, round(height * scale / 64) * 64)


def _klein_form(req: GenerationRequest) -> dict[str, Any]:
    """Multipart fields for FLUX.2 [klein] (Workers AI takes multipart even for a prompt only)."""
    from PIL import Image  # local import: only needed for edits

    width, height = req.width, req.height
    fields: dict[str, Any] = {"prompt": (None, req.prompt)}
    if req.image:
        with Image.open(io.BytesIO(req.image)) as img:
            frame = img.convert("RGB")
        width, height = _fit(frame.width, frame.height, EDIT_OUTPUT_LONG_SIDE)  # keep the shape
        frame.thumbnail((KLEIN_INPUT_MAX_SIDE, KLEIN_INPUT_MAX_SIDE))
        buf = io.BytesIO()
        frame.save(buf, format="JPEG", quality=90)
        fields["input_image_0"] = ("image.jpg", buf.getvalue(), "image/jpeg")
    fields["width"] = (None, str(width))
    fields["height"] = (None, str(height))
    if req.seed is not None:
        fields["seed"] = (None, str(req.seed))
    return fields


async def _run(creds: Credentials, model: str, *, wait: float = 90, **body: Any) -> Any:
    """POST to Workers AI `/ai/run/{model}` and return `result`. Errors become ProviderError."""
    account = creds.values.get("account_id", "")
    token = creds.values.get("api_token", "")
    if not _ACCOUNT_RE.match(account) or not token:
        raise ProviderError("Cloudflare credentials are missing or invalid")
    url = f"https://api.cloudflare.com/client/v4/accounts/{account}/ai/run/{model}"
    try:
        async with httpx.AsyncClient(timeout=wait) as client:
            resp = await client.post(url, headers={"Authorization": f"Bearer {token}"}, **body)
    except httpx.HTTPError as exc:
        raise ProviderError("Cloudflare is unreachable", retryable=True) from exc
    if resp.status_code == 429:
        raise ProviderError("Cloudflare free quota or rate limit reached", quota=True)
    if resp.status_code in (401, 403):
        raise ProviderError("Cloudflare rejected the credentials")
    if resp.status_code >= 400:
        # 4xx = our request is wrong (retrying won't help); 5xx = transient.
        detail = _error_detail(resp, (token, account))
        log.warning("Cloudflare returned %s: %s", resp.status_code, detail or "(no detail)")
        raise ProviderError(
            f"Cloudflare error ({resp.status_code})" + (f": {detail}" if detail else ""),
            retryable=resp.status_code >= 500,
        )
    try:
        return resp.json()["result"]
    except (ValueError, KeyError, TypeError) as exc:
        raise ProviderError("Unexpected response from Cloudflare") from exc


def clean_text(text: str, limit: int) -> str:
    """Printable characters only, whitespace collapsed, length-capped."""
    text = "".join(c for c in text if c.isprintable() or c.isspace())
    return " ".join(text.split())[:limit].strip()


async def describe_image(jpeg: bytes, creds: Credentials) -> str:
    """Alt text for one image (JPEG, ideally <=512px so it costs few Neurons)."""
    data_uri = "data:image/jpeg;base64," + base64.b64encode(jpeg).decode()
    body = {
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": _CAPTION_PROMPT},
                    {"type": "image_url", "image_url": {"url": data_uri, "detail": "low"}},
                ],
            }
        ],
        "max_completion_tokens": 120,
        "temperature": 0.2,
        "chat_template_kwargs": {"enable_thinking": False},  # no paid reasoning tokens
    }
    result = await _run(creds, CAPTION_MODEL, json=body, wait=60)
    try:
        if isinstance(result, dict) and "choices" in result:
            text = result["choices"][0]["message"]["content"]
        else:
            text = result["response"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ProviderError("Unexpected response from Cloudflare") from exc
    if not isinstance(text, str):
        raise ProviderError("Unexpected response from Cloudflare")
    return clean_text(text, ALT_TEXT_MAX)


async def transcribe(audio: bytes, creds: Credentials, language: str | None = None) -> str:
    """Speech to text with Whisper large-v3-turbo. Returns the cleaned transcription."""
    body: dict[str, Any] = {
        "audio": base64.b64encode(audio).decode(),
        "task": "transcribe",
        "vad_filter": True,
    }
    if language:
        body["language"] = language
    result = await _run(creds, WHISPER_MODEL, json=body, wait=60)
    try:
        text = result["text"]
    except (KeyError, TypeError) as exc:
        raise ProviderError("Unexpected response from Cloudflare") from exc
    if not isinstance(text, str):
        raise ProviderError("Unexpected response from Cloudflare")
    return clean_text(text, 2000)
