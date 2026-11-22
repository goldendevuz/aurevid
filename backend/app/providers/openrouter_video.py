# SPDX-License-Identifier: AGPL-3.0-or-later
"""OpenRouter video generation (ByteDance Seedance), billed to the user's own OpenRouter key.

API (verified by the owner with a real run, 2026-11-22): ``POST /api/v1/videos`` answers 202 with
``{id, polling_url, status}``; ``GET /api/v1/videos/{id}`` is polled until ``completed``,
``failed``, ``cancelled`` or ``expired`` (a failed job is ``status: "failed"`` with an error
message, not an HTTP error); the file comes from ``GET /api/v1/videos/{id}/content`` and needs the
Authorization header, so it is downloaded here on the server and never handed to the browser.
There is no cancel and no estimate endpoint. Failed jobs are not billed.

Money safety:

* A submit whose outcome we cannot know (timeout, dropped connection, 5xx) is **never retried**:
  the job may exist and be billed. Only a clear 429 (not accepted) is retried, with backoff.
* A poll that runs out of time is not retried either (the clip may still finish and be billed).
* The key goes only to ``openrouter.ai``; the poll URL is built from the job id, not taken from
  the response, so the response cannot redirect the key anywhere else.
"""

import asyncio
import base64
import re
import secrets
import time

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

BASE_URL = "https://openrouter.ai/api/v1"
CREDITS_URL = "https://openrouter.ai/settings/credits"
MINI = "bytedance/seedance-2.0-mini"
FLASH = "bytedance/seedance-2.5-flash"
PRO = "bytedance/seedance-2.5"
POLL_SECONDS = 5.0
SUBMIT_429_RETRIES = 3
SUBMIT_429_BACKOFF = 2.0  # seconds, doubled each time
MAX_POLL_FAILURES = 6  # consecutive transient poll errors tolerated (the job is already paid for)
DOWNLOAD_TRIES = 3
DEADLINE_MARGIN = 20  # finish before the worker's own timeout so we report a clear error
_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
_DETAIL_MAX = 160
TERMINAL_FAILURES = {"failed", "cancelled", "expired"}

# Price margin: the real run came back 5.6% above the label (864x496 for "480p"), so estimates
# are shown ~7% high. USD per 1M video tokens (OpenRouter model list, 2026-11-22); a second of
# video is width * height * 24 / 1024 tokens.
MARGIN = 1.07
TOKEN_FPS = 24 / 1024
USD_PER_M_TOKENS: dict[str, dict[str, float]] = {
    MINI: {"480p": 3.5, "720p": 3.5},
    FLASH: {"480p": 7.0, "720p": 7.0},
    PRO: {"480p": 10.7, "720p": 10.7, "1080p": 11.7},
}
# Nominal sizes from OpenRouter's `supported_sizes` per model (real files can be a bit larger).
_ORDER = ["1:1", "3:4", "9:16", "4:3", "16:9"]


def _sizes(*rows: tuple[str, list[tuple[int, int]]]) -> dict[str, dict[str, tuple[int, int]]]:
    return {res: dict(zip(_ORDER, dims, strict=True)) for res, dims in rows}


_MINI_SIZES = _sizes(
    ("480p", [(480, 480), (480, 640), (480, 854), (640, 480), (854, 480)]),
    ("720p", [(720, 720), (720, 960), (720, 1280), (960, 720), (1280, 720)]),
)
_V25_SIZES = _sizes(
    ("480p", [(640, 640), (560, 752), (480, 854), (752, 560), (854, 480)]),
    ("720p", [(960, 960), (834, 1112), (720, 1280), (1112, 834), (1280, 720)]),
    ("1080p", [(1080, 1080), (1080, 1440), (1080, 1920), (1440, 1080), (1920, 1080)]),
)
_RATIOS = ["16:9", "9:16", "1:1", "4:3", "3:4"]
_SIZES = {
    MINI: _MINI_SIZES,
    FLASH: {k: v for k, v in _V25_SIZES.items() if k != "1080p"},
    PRO: _V25_SIZES,
}
_LICENSE = "Proprietary hosted API (ByteDance Seedance via OpenRouter)"


def _http(timeout: float) -> httpx.AsyncClient:
    """Factory (tests replace it with a MockTransport client)."""
    return httpx.AsyncClient(timeout=timeout, follow_redirects=False)


def usd_per_second(model_id: str, resolution: str, aspect: str) -> float | None:
    rate = USD_PER_M_TOKENS.get(model_id, {}).get(resolution)
    size = _SIZES.get(model_id, {}).get(resolution, {}).get(aspect)
    if rate is None or size is None:
        return None
    return round(size[0] * size[1] * TOKEN_FPS * rate / 1_000_000 * MARGIN, 5)


def estimate_usd(model_id: str, resolution: str, aspect: str, seconds: int) -> float | None:
    per_second = usd_per_second(model_id, resolution, aspect)
    return None if per_second is None else round(per_second * seconds, 4)


def _error_detail(resp: httpx.Response, key: str) -> str:
    """One short, sanitised message from OpenRouter's error body; never the raw body."""
    try:
        data = resp.json()
        err = data["error"]
        message = str(err["message"] if isinstance(err, dict) else err)
    except (ValueError, KeyError, TypeError):
        return ""
    return _clean(message, key)


def _clean(message: str, key: str = "") -> str:
    if len(key) >= 8:
        message = message.replace(key, "***")
    message = " ".join("".join(c for c in message if c.isprintable() or c.isspace()).split())
    return message[:_DETAIL_MAX]


def _model(model_id: str, label: str, credit_cost: int, extra: dict[str, int]) -> ModelInfo:
    sizes = _SIZES[model_id]
    return ModelInfo(
        id=model_id,
        label=label,
        kind="video",
        license=_LICENSE,
        commercial_use="yes",  # BytePlus AI terms 2.1: you own the Output (MODEL_LICENSES.md)
        aspect_ratios=_RATIOS,
        credit_cost=credit_cost,
        max_count=1,
        durations=[5, 4, 8, 10],
        accepts_image=True,  # first frame
        has_audio=True,
        resolutions=list(sizes),
        default_resolution="720p",  # 1080p is always an explicit choice
        resolution_credits=extra,
        resolution_sizes=sizes,
    )


class OpenRouterVideoProvider(ImageProvider):
    info = ProviderInfo(
        id="openrouter_video",
        name="OpenRouter (Seedance video)",
        tier="paid",
        byok=True,
        byok_fields=["api_key"],
        requires_key=True,
        track_quota=False,
        models=[
            _model(MINI, "Seedance 2.0 Mini (OpenRouter)", 3, {"720p": 2}),
            _model(FLASH, "Seedance 2.5 Flash (OpenRouter)", 6, {"720p": 2}),
            _model(PRO, "Seedance 2.5 (OpenRouter)", 10, {"720p": 4, "1080p": 12}),
        ],
        notes="Billed in USD to your own OpenRouter key (about 14 cents for a 4 s 480p draft, "
        "about 3 dollars for 5 s of 1080p). The estimate is shown before you generate.",
        key_url="https://openrouter.ai/settings/keys",
    )

    def server_credentials(self) -> Credentials:
        key = get_settings().openrouter_api_key
        return Credentials({"api_key": key}, "server") if key else Credentials()

    def has_usable_credentials(self, creds: Credentials) -> bool:
        if creds.source == "user":
            return bool(creds.values.get("api_key"))
        # The owner's key is optional and off by default; it only runs inside a small allowance.
        s = get_settings()
        return creds.source == "server" and s.openrouter_free_clips_per_user > 0

    def server_allows(self, model_id: str, resolution: str | None) -> bool:
        # The owner's money only buys the cheapest draft.
        return model_id == MINI and resolution == "480p"

    def usd_per_second(self, model_id: str, resolution: str, aspect: str) -> float | None:
        return usd_per_second(model_id, resolution, aspect)

    async def generate(self, req: GenerationRequest, creds: Credentials) -> GeneratedMedia:
        key = creds.values.get("api_key", "")
        if not key or creds.source == "none":
            raise ProviderError("Add your OpenRouter key in Settings to use this provider")
        model = self.model(req.model)
        if req.kind != "video" or model is None:
            raise ProviderError("Unknown OpenRouter video model")
        resolution = req.resolution or model.default_resolution or model.resolutions[0]
        body: dict = {
            "model": req.model,
            "prompt": req.prompt,
            "duration": req.duration_s or model.durations[0],
            "resolution": resolution,
            "aspect_ratio": req.aspect_ratio,
            "generate_audio": True,
        }
        if req.seed is not None:
            body["seed"] = req.seed
        if req.image:
            data_uri = "data:image/jpeg;base64," + base64.b64encode(req.image).decode()
            body["frame_images"] = [
                {"type": "image_url", "image_url": {"url": data_uri}, "frame_type": "first_frame"}
            ]
        headers = {"Authorization": f"Bearer {key}"}
        settings = get_settings()
        deadline = time.monotonic() + max(30, settings.video_timeout_seconds - DEADLINE_MARGIN)
        dest = req.workdir / f"{secrets.token_hex(8)}.part" if req.workdir else None
        async with _http(60) as client:
            job_id = await self._submit(client, body, headers, key)
            usd = await self._wait(client, job_id, headers, key, deadline)
            media = await self._download(client, job_id, headers, dest, settings.max_video_bytes)
        if usd is not None:
            media.meta["usd_cost"] = usd
        return media

    async def _submit(self, client: httpx.AsyncClient, body: dict, headers: dict, key: str) -> str:
        for attempt in range(SUBMIT_429_RETRIES + 1):
            try:
                resp = await client.post(f"{BASE_URL}/videos", json=body, headers=headers)
            except httpx.HTTPError as exc:
                # The request may have reached OpenRouter: never send it again.
                raise ProviderError(
                    "OpenRouter did not confirm the job. It may still be billed: check "
                    "your OpenRouter activity before trying again"
                ) from exc
            code = resp.status_code
            if code == 429:  # clearly not accepted, so a retry cannot double-bill
                if attempt < SUBMIT_429_RETRIES:
                    await asyncio.sleep(SUBMIT_429_BACKOFF * 2**attempt)
                    continue
                raise ProviderError("OpenRouter rate limit reached, try again later", quota=True)
            if code == 402:
                raise ProviderError(f"Your OpenRouter credits are used up. Top up at {CREDITS_URL}")
            if code in (401, 403):
                raise ProviderError("OpenRouter rejected the key")
            if code in (400, 422):
                detail = _error_detail(resp, key)
                raise ProviderError(
                    "OpenRouter refused the video settings" + (f": {detail}" if detail else "")
                )
            if code >= 400:  # 5xx and the rest: outcome unknown, so not retryable
                raise ProviderError(
                    f"OpenRouter error ({code}). It may still be billed: check your activity"
                )
            try:
                job_id = resp.json()["id"]
            except (ValueError, KeyError, TypeError):
                job_id = None
            if not isinstance(job_id, str) or not _ID_RE.match(job_id):
                raise ProviderError("OpenRouter did not return a job id. It may still be billed")
            return job_id
        raise ProviderError(
            "OpenRouter rate limit reached, try again later", quota=True
        )  # pragma: no cover

    async def _wait(
        self, client: httpx.AsyncClient, job_id: str, headers: dict, key: str, deadline: float
    ) -> float | None:
        """Poll until completed. Returns the billed USD (``usage.cost``) when reported."""
        failures = 0
        while True:
            try:
                resp = await client.get(f"{BASE_URL}/videos/{job_id}", headers=headers)
                code = resp.status_code
                if code in (401, 402, 403):
                    raise ProviderError("OpenRouter rejected the key while the video was running")
                if code == 404:
                    raise ProviderError("OpenRouter lost the video job")
                if code == 429 or code >= 500:
                    raise httpx.TransportError("transient")
                if code >= 400:
                    raise ProviderError(f"OpenRouter error ({code})")
                data = resp.json()
                failures = 0
            except (httpx.HTTPError, ValueError):
                failures += 1
                if failures >= MAX_POLL_FAILURES:
                    raise ProviderError(
                        "OpenRouter stopped answering while the video was running"
                    ) from None
                data = {}
            status = str(data.get("status", "")) if isinstance(data, dict) else ""
            if status == "completed":
                cost = (data.get("usage") or {}).get("cost")
                return float(cost) if isinstance(cost, int | float) and cost >= 0 else None
            if status in TERMINAL_FAILURES:
                detail = _clean(str(data.get("error") or ""), key)
                label = {"failed": "failed", "cancelled": "was cancelled", "expired": "expired"}[
                    status
                ]
                raise ProviderError(f"OpenRouter video {label}" + (f": {detail}" if detail else ""))
            if time.monotonic() >= deadline:
                # Not retryable: the clip may still finish (and be billed) after we give up.
                raise ProviderError("OpenRouter took too long to make the video")
            await asyncio.sleep(POLL_SECONDS)

    async def _download(
        self, client: httpx.AsyncClient, job_id: str, headers: dict, dest, max_bytes: int
    ) -> GeneratedMedia:
        """The clip is made and paid for, so a failed download is simply fetched again."""
        last: ProviderError | None = None
        for attempt in range(DOWNLOAD_TRIES):
            try:
                return await self._fetch(client, job_id, headers, dest, max_bytes)
            except httpx.HTTPError:
                last = ProviderError("OpenRouter is unreachable while downloading the video")
            except _Transient as exc:
                last = ProviderError(str(exc))
            except ProviderError:
                if dest:
                    dest.unlink(missing_ok=True)
                raise
            if dest:
                dest.unlink(missing_ok=True)
            await asyncio.sleep(POLL_SECONDS * (attempt + 1) / 5)
        assert last is not None
        raise last

    async def _fetch(
        self, client: httpx.AsyncClient, job_id: str, headers: dict, dest, max_bytes: int
    ) -> GeneratedMedia:
        async with client.stream(
            "GET", f"{BASE_URL}/videos/{job_id}/content", headers=headers
        ) as resp:
            if resp.status_code == 429 or resp.status_code >= 500:
                raise _Transient(f"OpenRouter could not deliver the video ({resp.status_code})")
            if resp.status_code != 200:
                raise ProviderError(f"OpenRouter could not deliver the video ({resp.status_code})")
            ctype = resp.headers.get("content-type", "").split(";")[0]
            if not ctype.startswith("video/"):
                raise ProviderError("OpenRouter did not return a video")
            size = 0
            chunks: list[bytes] = []
            handle = dest.open("wb") if dest else None
            try:
                async for chunk in resp.aiter_bytes():
                    size += len(chunk)
                    if size > max_bytes:
                        raise ProviderError("OpenRouter returned an oversized video")
                    if handle:
                        handle.write(chunk)
                    else:
                        chunks.append(chunk)
            finally:
                if handle:
                    handle.close()
        if size == 0:
            raise ProviderError("OpenRouter returned an empty video")
        return GeneratedMedia(b"" if dest else b"".join(chunks), ctype, path=dest)


class _Transient(Exception):
    """A download answer worth asking for again (429 / 5xx)."""
