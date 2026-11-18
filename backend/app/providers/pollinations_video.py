# SPDX-License-Identifier: AGPL-3.0-or-later
"""Pollinations video adapter (text-to-video), billed to the user's own Pollinations key.

`GET https://gen.pollinations.ai/video/{prompt}` answers with the video itself (OpenAPI spec
read 2026-11-18). The key is sent only to that host. Which models an account may use, and how
many "pollen" each costs, depends on the account; see enter.pollinations.ai (MODEL_LICENSES.md).
"""

import secrets
from urllib.parse import quote

import httpx

from app.config import get_settings
from app.providers.base import (
    Credentials,
    GeneratedMedia,
    GenerationRequest,
    ImageProvider,
    ModelInfo,
    ProviderError,
    ProviderInfo,
)

BASE_URL = "https://gen.pollinations.ai"
WAN_FAST = "alibaba/wan-2.2-fast"
SEEDANCE_MINI = "bytedance/seedance-2.0-mini"
# What each model is asked for: the lowest resolution it lists, the cheapest clip.
_RESOLUTION = {WAN_FAST: "480p", SEEDANCE_MINI: "720p"}
_RATIOS = ["16:9", "9:16", "1:1"]
BALANCE_URL = "https://enter.pollinations.ai"


def _http(timeout: float) -> httpx.AsyncClient:
    """Factory (tests replace it with a MockTransport client)."""
    return httpx.AsyncClient(timeout=timeout, follow_redirects=False)


class PollinationsVideoProvider(ImageProvider):
    info = ProviderInfo(
        id="pollinations_video",
        name="Pollinations (video)",
        tier="paid",
        byok=True,
        byok_fields=["api_key"],
        requires_key=True,
        track_quota=False,
        models=[
            ModelInfo(
                id=WAN_FAST,
                label="Wan 2.2 Fast text-to-video (Pollinations)",
                kind="video",
                license="Apache-2.0 (Wan 2.2 weights); hosted under Pollinations terms",
                commercial_use="unclear",
                aspect_ratios=_RATIOS,
                credit_cost=5,
                max_count=1,
                durations=[5],
            ),
            ModelInfo(
                id=SEEDANCE_MINI,
                label="Seedance 2.0 Mini text-to-video (Pollinations)",
                kind="video",
                license="Proprietary hosted API (ByteDance, via Pollinations)",
                commercial_use="unclear",
                aspect_ratios=_RATIOS,
                credit_cost=5,
                max_count=1,
                durations=[5],
            ),
        ],
        notes="Uses the balance (pollen) of your own Pollinations key; a free key is made at "
        "enter.pollinations.ai. Whether a free balance covers video depends on your account.",
        key_url="https://enter.pollinations.ai/keys",
    )

    def has_usable_credentials(self, creds: Credentials) -> bool:
        return creds.source == "user"  # never spend a server key on someone else's video

    async def generate(self, req: GenerationRequest, creds: Credentials) -> GeneratedMedia:
        key = creds.values.get("api_key")
        if not key or creds.source != "user":
            raise ProviderError("Add your Pollinations key in Settings to use this provider")
        if req.kind != "video" or self.model(req.model) is None:
            raise ProviderError("Unknown Pollinations video model")
        params: dict[str, str | int] = {
            "model": req.model,
            "aspectRatio": req.aspect_ratio,
            "resolution": _RESOLUTION[req.model],
            "duration": req.duration_s or 5,
            "audio": "false",
            "safe": "true",
        }
        if req.seed is not None:
            params["seed"] = req.seed
        url = f"{BASE_URL}/video/{quote(req.prompt, safe='')}"
        headers = {"Authorization": f"Bearer {key}"}
        settings = get_settings()
        dest = req.workdir / f"{secrets.token_hex(8)}.part" if req.workdir else None
        try:
            async with _http(settings.video_timeout_seconds) as client:
                async with client.stream("GET", url, params=params, headers=headers) as resp:
                    self._check(resp)
                    ctype = resp.headers.get("content-type", "").split(";")[0]
                    if not ctype.startswith("video/"):
                        raise ProviderError("Pollinations did not return a video")
                    return await self._read(resp, ctype, dest, settings.max_video_bytes)
        except httpx.HTTPError as exc:
            raise ProviderError("Pollinations is unreachable", retryable=True) from exc

    @staticmethod
    def _check(resp: httpx.Response) -> None:
        code = resp.status_code
        if code in (401, 403):
            raise ProviderError("Pollinations rejected the key")
        if code == 402:
            raise ProviderError(f"Your Pollinations balance is empty. Check it at {BALANCE_URL}")
        if code == 429:
            raise ProviderError("Pollinations rate limit reached", quota=True)
        if code >= 400:
            raise ProviderError(f"Pollinations error ({code})", retryable=code >= 500)

    @staticmethod
    async def _read(resp: httpx.Response, ctype: str, dest, max_bytes: int) -> GeneratedMedia:
        size = 0
        chunks: list[bytes] = []
        handle = dest.open("wb") if dest else None
        try:
            async for chunk in resp.aiter_bytes():
                size += len(chunk)
                if size > max_bytes:
                    raise ProviderError("Pollinations returned an oversized video")
                if handle:
                    handle.write(chunk)
                else:
                    chunks.append(chunk)
        finally:
            if handle:
                handle.close()
        if size == 0:
            raise ProviderError("Pollinations returned an empty video")
        return GeneratedMedia(b"" if dest else b"".join(chunks), ctype, path=dest)
