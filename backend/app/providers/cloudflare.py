# SPDX-License-Identifier: AGPL-3.0-or-later
"""Cloudflare Workers AI adapter (FLUX.1 [schnell]). Free daily allocation on CF accounts."""

import base64
import re

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


class CloudflareProvider(ImageProvider):
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
            )
        ],
        notes="Free daily allocation on your Cloudflare account; output is 1024x1024.",
    )

    def server_credentials(self) -> Credentials:
        s = get_settings()
        if s.cf_account_id and s.cf_api_token:
            return Credentials(
                {"account_id": s.cf_account_id, "api_token": s.cf_api_token}, "server"
            )
        return Credentials()

    async def generate(self, req: GenerationRequest, creds: Credentials) -> GeneratedImage:
        account = creds.values.get("account_id", "")
        token = creds.values.get("api_token", "")
        if not _ACCOUNT_RE.match(account) or not token:
            raise ProviderError("Cloudflare credentials are missing or invalid")
        url = f"https://api.cloudflare.com/client/v4/accounts/{account}/ai/run/{req.model}"
        body: dict = {"prompt": req.prompt, "steps": 4}
        if req.seed is not None:
            body["seed"] = req.seed
        try:
            async with httpx.AsyncClient(timeout=90) as client:
                resp = await client.post(
                    url, json=body, headers={"Authorization": f"Bearer {token}"}
                )
        except httpx.HTTPError as exc:
            raise ProviderError("Cloudflare is unreachable", retryable=True) from exc
        if resp.status_code == 429:
            raise ProviderError("Cloudflare free quota or rate limit reached", retryable=True)
        if resp.status_code in (401, 403):
            raise ProviderError("Cloudflare rejected the credentials")
        if resp.status_code >= 400:
            raise ProviderError(f"Cloudflare error ({resp.status_code})", retryable=True)
        try:
            image_b64 = resp.json()["result"]["image"]
            return GeneratedImage(base64.b64decode(image_b64, validate=True), "image/jpeg")
        except (ValueError, KeyError, TypeError) as exc:
            raise ProviderError("Unexpected response from Cloudflare") from exc
