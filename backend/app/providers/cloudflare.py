# SPDX-License-Identifier: AGPL-3.0-or-later
"""Cloudflare Workers AI adapter (FLUX.1 [schnell]). Free daily allocation on CF accounts."""

import base64
import logging
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
_DETAIL_MAX = 160
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
        # 10,000 Neurons/day; ~58 Neurons per 1024px 4-step image (third-party estimate).
        daily_quota_prior=170,
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

    async def generate(self, req: GenerationRequest, creds: Credentials) -> GeneratedImage:
        account = creds.values.get("account_id", "")
        token = creds.values.get("api_token", "")
        if not _ACCOUNT_RE.match(account) or not token:
            raise ProviderError("Cloudflare credentials are missing or invalid")
        url = f"https://api.cloudflare.com/client/v4/accounts/{account}/ai/run/{req.model}"
        # The FLUX schnell schema on Workers AI accepts only prompt + steps (verified live
        # 2026-11-17: sending "seed" returns 400 "Additional properties '/seed' not allowed").
        body: dict = {"prompt": req.prompt, "steps": 4}
        try:
            async with httpx.AsyncClient(timeout=90) as client:
                resp = await client.post(
                    url, json=body, headers={"Authorization": f"Bearer {token}"}
                )
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
            image_b64 = resp.json()["result"]["image"]
            return GeneratedImage(base64.b64decode(image_b64, validate=True), "image/jpeg")
        except (ValueError, KeyError, TypeError) as exc:
            raise ProviderError("Unexpected response from Cloudflare") from exc
