# SPDX-License-Identifier: AGPL-3.0-or-later
"""fal.ai adapter (PAID, bring-your-own-key only). Disabled unless FAL_ENABLED=true.

Not exercised against the live API in CI; treat as a starting point.
"""

import httpx

from app.providers.base import (
    Credentials,
    GeneratedImage,
    GenerationRequest,
    ImageProvider,
    ModelInfo,
    ProviderError,
    ProviderInfo,
)
from app.ssrf import UnsafeURLError, safe_get

_SIZES = {
    "1:1": "square_hd",
    "16:9": "landscape_16_9",
    "9:16": "portrait_16_9",
    "4:3": "landscape_4_3",
    "3:4": "portrait_4_3",
}


class FalProvider(ImageProvider):
    info = ProviderInfo(
        id="fal",
        name="fal.ai",
        tier="paid",
        byok=True,
        byok_fields=["api_key"],
        requires_key=True,
        models=[
            ModelInfo(
                id="fal-ai/flux/schnell",
                label="FLUX.1 schnell (fal)",
                license="Apache-2.0",
                commercial_use="yes",
                aspect_ratios=list(_SIZES),
                credit_cost=1,
            )
        ],
        notes="Paid: billed to your own fal.ai account via your key.",
    )

    def has_usable_credentials(self, creds: Credentials) -> bool:
        return creds.source == "user"  # never spend a server key on a paid provider

    async def generate(self, req: GenerationRequest, creds: Credentials) -> GeneratedImage:
        key = creds.values.get("api_key")
        if not key or creds.source != "user":
            raise ProviderError("Add your fal.ai key in Settings to use this provider")
        body = {"prompt": req.prompt, "image_size": _SIZES[req.aspect_ratio], "num_images": 1}
        if req.seed is not None:
            body["seed"] = req.seed
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                resp = await client.post(
                    f"https://fal.run/{req.model}",
                    json=body,
                    headers={"Authorization": f"Key {key}"},
                )
        except httpx.HTTPError as exc:
            raise ProviderError("fal.ai is unreachable", retryable=True) from exc
        if resp.status_code in (401, 403):
            raise ProviderError("fal.ai rejected the key")
        if resp.status_code >= 400:
            raise ProviderError(f"fal.ai error ({resp.status_code})", retryable=True)
        try:
            image_url = resp.json()["images"][0]["url"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise ProviderError("Unexpected response from fal.ai") from exc
        # The result URL comes from a third party: fetch it through the SSRF guard.
        try:
            data, ctype = await safe_get(image_url, max_bytes=15 * 1024 * 1024)
        except (UnsafeURLError, httpx.HTTPError) as exc:
            raise ProviderError("Could not download the fal.ai result") from exc
        return GeneratedImage(data, ctype.split(";")[0] or "image/jpeg")
