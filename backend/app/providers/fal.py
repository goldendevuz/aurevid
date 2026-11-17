# SPDX-License-Identifier: AGPL-3.0-or-later
"""fal.ai adapter (PAID, bring-your-own-key only). Disabled unless FAL_ENABLED=true.

Images use the synchronous endpoint; videos use the queue API (submit → poll → result).
The user's key is only ever sent to fal hosts. Not exercised against the live API in CI.
"""

import asyncio
import base64
import secrets
from pathlib import Path
from urllib.parse import urlsplit

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
from app.ssrf import UnsafeURLError, safe_get

_SIZES = {
    "1:1": "square_hd",
    "16:9": "landscape_16_9",
    "9:16": "portrait_16_9",
    "4:3": "landscape_4_3",
    "3:4": "portrait_4_3",
}
_QUEUE_HOSTS = {"queue.fal.run"}
POLL_SECONDS = 4.0

TOPAZ_VIDEO = "fal-ai/topaz/upscale/video"
TOPAZ_MODEL = "Proteus"  # Topaz's general-purpose model (fal default)
UPSCALE_SHORT_SIDE = {"4k": 2160, "8k": 4320}
T2V = "fal-ai/wan/v2.2-5b/text-to-video"
I2V = "fal-ai/wan/v2.2-a14b/image-to-video"
# model id -> (frames per second, {size: resolution})
_VIDEO = {
    T2V: (24, {"small": "580p", "medium": "580p", "large": "720p"}),
    I2V: (16, {"small": "480p", "medium": "580p", "large": "720p"}),
}


def _http(timeout: float) -> httpx.AsyncClient:
    """Factory (tests replace it with a MockTransport client)."""
    return httpx.AsyncClient(timeout=timeout, follow_redirects=False)


def _fal_queue_url(url: object) -> str:
    """Only follow queue URLs on fal's own host: the key must never go anywhere else."""
    if not isinstance(url, str):
        raise ProviderError("Unexpected response from fal.ai")
    parts = urlsplit(url)
    if parts.scheme != "https" or parts.hostname not in _QUEUE_HOSTS:
        raise ProviderError("Unexpected response from fal.ai")
    return url


BILLING_URL = "https://fal.ai/dashboard/billing"


def _check(resp: httpx.Response) -> None:
    if resp.status_code in (401, 402, 403):
        detail = resp.text[:500].lower()  # inspected only, never shown to users verbatim
        if resp.status_code == 402 or "balance" in detail or "locked" in detail:
            raise ProviderError(f"Your fal.ai balance is empty. Top up at {BILLING_URL}")
        raise ProviderError("fal.ai rejected the key")
    if resp.status_code == 429:
        raise ProviderError("fal.ai rate limit reached", quota=True)
    if resp.status_code >= 400:
        raise ProviderError(f"fal.ai error ({resp.status_code})", retryable=resp.status_code >= 500)


class FalProvider(ImageProvider):
    info = ProviderInfo(
        id="fal",
        name="fal.ai",
        tier="paid",
        byok=True,
        byok_fields=["api_key"],
        requires_key=True,
        track_quota=False,
        models=[
            ModelInfo(
                id="fal-ai/flux/schnell",
                label="FLUX.1 schnell (fal)",
                license="Apache-2.0",
                commercial_use="yes",
                aspect_ratios=list(_SIZES),
                credit_cost=1,
            ),
            ModelInfo(
                id=T2V,
                label="Wan 2.2 5B text-to-video (fal)",
                kind="video",
                license="Apache-2.0",
                commercial_use="yes",
                aspect_ratios=["16:9", "9:16", "1:1"],
                credit_cost=5,
                max_count=1,
                durations=[5, 3],
                upscale_targets=["4k", "8k"],
            ),
            ModelInfo(
                id=I2V,
                label="Wan 2.2 A14B image-to-video (fal)",
                kind="video",
                license="Apache-2.0",
                commercial_use="yes",
                aspect_ratios=["16:9", "9:16", "1:1"],
                credit_cost=5,
                max_count=1,
                durations=[5, 3],
                accepts_image=True,
                requires_image=True,
                upscale_targets=["4k", "8k"],
            ),
        ],
        notes="Paid: billed to your own fal.ai account via your key. 4K/8K video uses Topaz "
        "upscaling on fal (about $0.08 per output second per pass above 1080p).",
        key_url="https://fal.ai/dashboard/keys",
    )

    def has_usable_credentials(self, creds: Credentials) -> bool:
        return creds.source == "user"  # never spend a server key on a paid provider

    async def generate(self, req: GenerationRequest, creds: Credentials) -> GeneratedMedia:
        key = creds.values.get("api_key")
        if not key or creds.source != "user":
            raise ProviderError("Add your fal.ai key in Settings to use this provider")
        if req.kind == "video":
            return await self._video(req, key)
        return await self._image(req, key)

    async def _image(self, req: GenerationRequest, key: str) -> GeneratedMedia:
        body = {"prompt": req.prompt, "image_size": _SIZES[req.aspect_ratio], "num_images": 1}
        if req.seed is not None:
            body["seed"] = req.seed
        try:
            async with _http(120) as client:
                resp = await client.post(
                    f"https://fal.run/{req.model}",
                    json=body,
                    headers={"Authorization": f"Key {key}"},
                )
        except httpx.HTTPError as exc:
            raise ProviderError("fal.ai is unreachable", retryable=True) from exc
        _check(resp)
        try:
            image_url = resp.json()["images"][0]["url"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise ProviderError("Unexpected response from fal.ai") from exc
        return await self._download(image_url, 15 * 1024 * 1024, "image/jpeg")

    def video_body(self, req: GenerationRequest) -> dict:
        if req.model not in _VIDEO:
            raise ProviderError("Unknown fal.ai video model")
        fps, resolutions = _VIDEO[req.model]
        frames = max(17, min(161, (req.duration_s or 5) * fps + 1))
        body: dict = {
            "prompt": req.prompt,
            "aspect_ratio": req.aspect_ratio,
            "resolution": resolutions.get(req.size, "720p"),
            "num_frames": frames,
            "frames_per_second": fps,
            "enable_safety_checker": True,
            "enable_output_safety_checker": True,
        }
        if req.seed is not None:
            body["seed"] = req.seed
        if req.model == I2V:
            if not req.image:
                raise ProviderError("This model needs a start image")
            # Data URI: accepted by some fal models per fal docs; not verified for this one.
            body["image_url"] = "data:image/jpeg;base64," + base64.b64encode(req.image).decode()
        return body

    async def _queue(self, client, model: str, body: dict, headers: dict, deadline: float) -> dict:
        """Submit to fal's queue, poll until COMPLETED, return the result JSON."""
        loop = asyncio.get_running_loop()
        submit = await client.post(f"https://queue.fal.run/{model}", json=body, headers=headers)
        _check(submit)
        try:
            data = submit.json()
            status_url = _fal_queue_url(data["status_url"])
            response_url = _fal_queue_url(data["response_url"])
        except (ValueError, KeyError, TypeError) as exc:
            raise ProviderError("Unexpected response from fal.ai") from exc
        while True:
            st = await client.get(status_url, headers=headers)
            _check(st)
            if st.json().get("status") == "COMPLETED":
                break
            if loop.time() > deadline:
                raise ProviderError("fal.ai took too long")
            await asyncio.sleep(POLL_SECONDS)
        result = await client.get(response_url, headers=headers)
        _check(result)  # COMPLETED also covers failures; the result call reports them
        try:
            return result.json()
        except ValueError as exc:
            raise ProviderError("Unexpected response from fal.ai") from exc

    def upscale_passes(self, req: GenerationRequest) -> list[float]:
        """Topaz factors (each 1-4x) that take the base resolution to the 4K/8K short side."""
        if not req.upscale:
            return []
        _, resolutions = _VIDEO[req.model]
        base_short = int(resolutions.get(req.size, "720p").rstrip("p"))
        total = UPSCALE_SHORT_SIDE[req.upscale] / base_short
        passes: list[float] = []
        while total > 1.001:
            factor = min(4.0, total)
            passes.append(round(factor, 3))
            total /= factor
        return passes

    async def _video(self, req: GenerationRequest, key: str) -> GeneratedMedia:
        body = self.video_body(req)
        headers = {"Authorization": f"Key {key}"}
        passes = self.upscale_passes(req)
        loop = asyncio.get_running_loop()
        budget = get_settings().video_timeout_seconds * (1 + len(passes))
        deadline = loop.time() + max(60, budget - 30)
        try:
            async with _http(60) as client:
                result = await self._queue(client, req.model, body, headers, deadline)
                video_url = _video_url(result)
                for i, factor in enumerate(passes):
                    last = i == len(passes) - 1
                    upscale_body = {
                        # A fal-hosted URL from the previous step: nothing of ours is uploaded.
                        "video_url": video_url,
                        "upscale_factor": factor,
                        "model": TOPAZ_MODEL,
                        # H.264 plays everywhere up to 4K; H.265 keeps 8K files a sane size.
                        "H264_output": not (last and req.upscale == "8k"),
                        "enable_safety_checker": True,
                    }
                    result = await self._queue(client, TOPAZ_VIDEO, upscale_body, headers, deadline)
                    video_url = _video_url(result)
        except httpx.HTTPError as exc:
            raise ProviderError("fal.ai is unreachable", retryable=True) from exc
        return await self._download(
            video_url, get_settings().max_video_bytes, "video/mp4", req.workdir
        )

    async def _download(
        self, url: str, max_bytes: int, default_mime: str, workdir: Path | None = None
    ) -> GeneratedMedia:
        # The result URL comes from a third party: fetch it through the SSRF guard, no key.
        dest = workdir / f"{secrets.token_hex(8)}.part" if workdir else None
        try:
            data, ctype = await safe_get(url, max_bytes=max_bytes, dest=dest)
        except (UnsafeURLError, httpx.HTTPError) as exc:
            raise ProviderError("Could not download the fal.ai result") from exc
        return GeneratedMedia(data, ctype.split(";")[0] or default_mime, path=dest)


def _video_url(result: dict) -> str:
    try:
        url = result["video"]["url"]
    except (KeyError, TypeError) as exc:
        raise ProviderError("fal.ai returned no video") from exc
    if not isinstance(url, str):
        raise ProviderError("fal.ai returned no video")
    return url
