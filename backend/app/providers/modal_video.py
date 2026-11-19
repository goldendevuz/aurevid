# SPDX-License-Identifier: AGPL-3.0-or-later
"""Wan 2.2 text-to-video running in the user's own Modal workspace (deploy/modal/wan_video.py).

The user gives the URL of their `submit` endpoint and a Modal proxy auth token. We POST the job,
then poll the sibling `result` endpoint until the mp4 is ready. The endpoint host must be a
`*.modal.run` address, so a pasted key cannot be used to make this server call arbitrary
addresses; the token is sent only there.
"""

import asyncio
import secrets
import time
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

WAN = "wan-2.2-ti2v-5b"
POLL_SECONDS = 5.0
# (width, height) per ratio: multiples of 32 for Wan 2.2 5B, small so a clip stays cheap.
_SIZES = {"16:9": (832, 480), "9:16": (480, 832), "1:1": (640, 640)}
_FRAMES = {5: 121, 3: 73}  # 24 fps, 4k+1 frames


def _http(timeout: float) -> httpx.AsyncClient:
    """Factory (tests replace it with a MockTransport client)."""
    return httpx.AsyncClient(timeout=timeout, follow_redirects=False)


def endpoints(submit_url: str) -> tuple[str, str]:
    """(submit, result) URLs from the pasted submit URL; refuses anything but a Modal endpoint."""
    parts = urlsplit(submit_url.strip())
    host = parts.hostname or ""
    if parts.scheme != "https" or parts.port not in (None, 443) or not host.endswith(".modal.run"):
        raise ProviderError("The Modal URL must be an https://….modal.run address")
    if "-submit" not in host.split(".")[0]:
        raise ProviderError("Use the URL of the `submit` endpoint from `modal deploy`")
    result_host = host.replace("-submit", "-result", 1)
    return f"https://{host}/", f"https://{result_host}/"


class ModalVideoProvider(ImageProvider):
    info = ProviderInfo(
        id="modal_video",
        name="Modal (your own Wan 2.2)",
        tier="paid",
        byok=True,
        byok_fields=["submit_url", "token_id", "token_secret"],
        requires_key=True,
        track_quota=False,
        models=[
            ModelInfo(
                id=WAN,
                label="Wan 2.2 TI2V-5B text-to-video (your Modal)",
                kind="video",
                license="Apache-2.0",
                commercial_use="yes",
                aspect_ratios=list(_SIZES),
                credit_cost=5,
                max_count=1,
                durations=[5, 3],
                has_audio=True,
            )
        ],
        notes="Runs on a GPU in your own Modal workspace, paid from your Modal credit "
        "(see deploy/modal/README.md). The first clip after a pause waits for the GPU to start.",
        key_url="https://modal.com/settings/proxy-auth-tokens",
    )

    def has_usable_credentials(self, creds: Credentials) -> bool:
        return creds.source == "user"  # never spend a server key on someone else's video

    async def generate(self, req: GenerationRequest, creds: Credentials) -> GeneratedMedia:
        values = creds.values
        submit_url = values.get("submit_url")
        token_id, token_secret = values.get("token_id"), values.get("token_secret")
        if not (submit_url and token_id and token_secret) or creds.source != "user":
            raise ProviderError(
                "Add your Modal endpoint and token in Settings to use this provider"
            )
        if req.kind != "video" or req.model != WAN:
            raise ProviderError("Unknown Modal video model")
        submit, result = endpoints(submit_url)
        headers = {"Modal-Key": token_id, "Modal-Secret": token_secret}
        width, height = _SIZES.get(req.aspect_ratio, _SIZES["16:9"])
        body = {
            "prompt": req.prompt,
            "width": width,
            "height": height,
            "frames": _FRAMES.get(req.duration_s or 5, 121),
            "seed": req.seed or 0,
        }
        settings = get_settings()
        deadline = time.monotonic() + settings.video_timeout_seconds
        dest = req.workdir / f"{secrets.token_hex(8)}.part" if req.workdir else None
        try:
            async with _http(60) as client:
                resp = await client.post(submit, json=body, headers=headers)
                self._check(resp)
                call_id = resp.json().get("call_id") if resp.content else None
                if not isinstance(call_id, str) or not call_id:
                    raise ProviderError("Modal did not accept the job")
                while True:
                    async with client.stream(
                        "GET", result, params={"call_id": call_id}, headers=headers
                    ) as poll:
                        if poll.status_code != 202:
                            self._check(poll)
                            return await self._read(poll, dest, settings.max_video_bytes)
                    if time.monotonic() >= deadline:
                        raise ProviderError("Modal took too long to make the video", retryable=True)
                    await asyncio.sleep(POLL_SECONDS)
        except (httpx.HTTPError, ValueError) as exc:
            raise ProviderError("Modal is unreachable", retryable=True) from exc

    @staticmethod
    def _check(resp: httpx.Response) -> None:
        code = resp.status_code
        if code in (401, 403):
            raise ProviderError("Modal rejected the token")
        if code == 404:
            raise ProviderError("Modal endpoint not found; deploy it again and check the URL")
        if code == 422:
            raise ProviderError("Modal refused the video settings")
        if code == 429:
            raise ProviderError("Modal rate limit reached", quota=True)
        if code >= 400:
            raise ProviderError(f"Modal error ({code})", retryable=code >= 500)

    @staticmethod
    async def _read(resp: httpx.Response, dest, max_bytes: int) -> GeneratedMedia:
        ctype = resp.headers.get("content-type", "").split(";")[0]
        if not ctype.startswith("video/"):
            raise ProviderError("Modal did not return a video")
        size = 0
        chunks: list[bytes] = []
        handle = dest.open("wb") if dest else None
        try:
            async for chunk in resp.aiter_bytes():
                size += len(chunk)
                if size > max_bytes:
                    raise ProviderError("Modal returned an oversized video")
                if handle:
                    handle.write(chunk)
                else:
                    chunks.append(chunk)
        finally:
            if handle:
                handle.close()
        if size == 0:
            raise ProviderError("Modal returned an empty video")
        return GeneratedMedia(b"" if dest else b"".join(chunks), ctype, path=dest)
