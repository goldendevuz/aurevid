# SPDX-License-Identifier: AGPL-3.0-or-later
"""Pollinations adapter: keyless public image endpoint, used as a free fallback.

Best-effort service with no SLA; check its terms before commercial use (MODEL_LICENSES.md).
"""

from urllib.parse import quote

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

_ALL_RATIOS = ["1:1", "16:9", "9:16", "4:3", "3:4"]
_MAX_BYTES = 15 * 1024 * 1024


class PollinationsProvider(ImageProvider):
    info = ProviderInfo(
        id="pollinations",
        name="Pollinations",
        tier="free",
        byok=False,
        requires_key=False,
        models=[
            ModelInfo(
                id="flux",
                label="FLUX (Pollinations)",
                license="Service terms (see MODEL_LICENSES.md)",
                commercial_use="unclear",
                aspect_ratios=_ALL_RATIOS,
                credit_cost=1,
                max_count=1,  # anonymous tier answers 402 to back-to-back requests
            )
        ],
        notes="Keyless public service, no SLA. Commercial use: check its terms first.",
    )

    async def generate(self, req: GenerationRequest, creds: Credentials) -> GeneratedImage:
        base = get_settings().pollinations_base_url.rstrip("/")
        url = f"{base}/prompt/{quote(req.prompt, safe='')}"
        params = {
            "width": req.width,
            "height": req.height,
            "model": req.model,
            "nologo": "true",
            "private": "true",
            "safe": "true",
        }
        if req.seed is not None:
            params["seed"] = req.seed
        try:
            async with httpx.AsyncClient(timeout=120, follow_redirects=False) as client:
                resp = await client.get(url, params=params)
        except httpx.HTTPError as exc:
            raise ProviderError("Pollinations is unreachable", retryable=True) from exc
        if resp.status_code in (402, 429):
            # Observed 2026-11: anonymous requests get 402 once the free quota is used up.
            raise ProviderError("Pollinations free quota reached, try again later")
        if resp.status_code >= 400:
            raise ProviderError(f"Pollinations error ({resp.status_code})", retryable=True)
        if len(resp.content) > _MAX_BYTES:
            raise ProviderError("Pollinations returned an oversized file")
        ctype = resp.headers.get("content-type", "").split(";")[0]
        if not ctype.startswith("image/"):
            raise ProviderError("Pollinations did not return an image")
        return GeneratedImage(resp.content, ctype)
