# SPDX-License-Identifier: AGPL-3.0-or-later
"""fal.ai video adapter against a fake fal API (no network, no real key)."""

import base64
import json

import httpx
import pytest

from app.providers import fal
from app.providers.base import Credentials, GenerationRequest, ProviderError

KEY = Credentials({"api_key": "test-fal-key"}, "user")
QUEUE = "https://queue.fal.run/fal-ai/wan/requests/abc"


def _req(model=fal.T2V, image=None):
    return GenerationRequest(
        prompt="waves",
        model=model,
        aspect_ratio="9:16",
        width=768,
        height=1344,
        seed=7,
        kind="video",
        size="large",
        duration_s=5,
        image=image,
    )


def _fake_fal(seen: list, status_url=f"{QUEUE}/status", polls: int = 2, result_code=200):
    state = {"polls": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        url = str(request.url)
        if request.method == "POST":
            return httpx.Response(
                200, json={"request_id": "abc", "status_url": status_url, "response_url": QUEUE}
            )
        if url.endswith("/status"):
            state["polls"] += 1
            done = state["polls"] >= polls
            return httpx.Response(200, json={"status": "COMPLETED" if done else "IN_PROGRESS"})
        if url == QUEUE:
            if result_code != 200:
                return httpx.Response(result_code, json={"detail": "boom"})
            return httpx.Response(200, json={"video": {"url": "https://v3.fal.media/x.mp4"}})
        return httpx.Response(404)

    return httpx.MockTransport(handler)


@pytest.fixture
def patched(monkeypatch):
    seen: list[httpx.Request] = []
    downloads: list[str] = []

    def install(**kw):
        transport = _fake_fal(seen, **kw)
        monkeypatch.setattr(
            fal, "_http", lambda timeout: httpx.AsyncClient(transport=transport, timeout=timeout)
        )

    async def fake_safe_get(url, max_bytes, dest=None):
        downloads.append(url)
        if dest is not None:
            dest.write_bytes(b"MP4BYTES")
            return b"", "video/mp4"
        return b"MP4BYTES", "video/mp4"

    monkeypatch.setattr(fal, "safe_get", fake_safe_get)
    monkeypatch.setattr(fal, "POLL_SECONDS", 0)
    return install, seen, downloads


async def test_text_to_video_queue_flow(patched):
    install, seen, downloads = patched
    install()
    out = await fal.FalProvider().generate(_req(), KEY)
    assert out.data == b"MP4BYTES" and out.mime == "video/mp4"
    submit = json.loads(seen[0].content)
    assert seen[0].url == f"https://queue.fal.run/{fal.T2V}"
    assert submit["num_frames"] == 121 and submit["resolution"] == "720p"
    assert submit["aspect_ratio"] == "9:16" and submit["enable_safety_checker"] is True
    assert all(r.headers["authorization"] == "Key test-fal-key" for r in seen)
    assert downloads == ["https://v3.fal.media/x.mp4"]


async def test_key_never_sent_to_foreign_status_url(patched):
    install, seen, _ = patched
    install(status_url="https://evil.example/steal")
    with pytest.raises(ProviderError):
        await fal.FalProvider().generate(_req(), KEY)
    assert all(r.url.host == "queue.fal.run" for r in seen)


async def test_failed_result_is_reported(patched):
    install, _, _ = patched
    install(result_code=422)
    with pytest.raises(ProviderError) as err:
        await fal.FalProvider().generate(_req(), KEY)
    assert "422" in err.value.public


async def test_image_to_video_sends_start_frame(patched):
    install, seen, _ = patched
    install()
    await fal.FalProvider().generate(_req(fal.I2V, image=b"\xff\xd8jpeg"), KEY)
    body = json.loads(seen[0].content)
    assert (
        body["image_url"] == "data:image/jpeg;base64," + base64.b64encode(b"\xff\xd8jpeg").decode()
    )
    assert body["num_frames"] == 81


async def test_image_to_video_requires_image_and_user_key(patched):
    install, _, _ = patched
    install()
    with pytest.raises(ProviderError):
        await fal.FalProvider().generate(_req(fal.I2V), KEY)
    with pytest.raises(ProviderError):
        await fal.FalProvider().generate(_req(), Credentials({"api_key": "k"}, "server"))


def _multi_fake(seen: list):
    """Fake fal queue that answers any submitted model; results carry per-step video URLs."""

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        url = str(request.url)
        if request.method == "POST":
            n = sum(1 for r in seen if r.method == "POST")
            base = f"https://queue.fal.run/fal-ai/x/requests/r{n}"
            return httpx.Response(
                200,
                json={"request_id": f"r{n}", "status_url": f"{base}/status", "response_url": base},
            )
        if url.endswith("/status"):
            return httpx.Response(200, json={"status": "COMPLETED"})
        n = url.rsplit("r", 1)[-1]
        return httpx.Response(200, json={"video": {"url": f"https://v3.fal.media/step{n}.mp4"}})

    return httpx.MockTransport(handler)


@pytest.mark.parametrize("target,factors", [("4k", [3.0]), ("8k", [4.0, 1.5])])
async def test_video_upscale_chain_to_4k_and_8k(patched, monkeypatch, tmp_path, target, factors):
    _, _, downloads = patched
    seen: list[httpx.Request] = []
    transport = _multi_fake(seen)
    monkeypatch.setattr(
        fal, "_http", lambda timeout: httpx.AsyncClient(transport=transport, timeout=timeout)
    )
    req = _req()
    req.upscale, req.workdir = target, tmp_path
    out = await fal.FalProvider().generate(req, KEY)
    posts = [json.loads(r.content) for r in seen if r.method == "POST"]
    assert [p.get("upscale_factor") for p in posts[1:]] == factors
    # Each pass upscales the previous fal-hosted result; nothing of ours is uploaded.
    assert posts[1]["video_url"] == "https://v3.fal.media/step1.mp4"
    assert posts[-1]["H264_output"] is (target == "4k")
    assert seen[len(factors) * 3].url.host == "queue.fal.run"
    assert downloads[-1] == f"https://v3.fal.media/step{len(factors) + 1}.mp4"
    assert out.path is not None and out.path.read_bytes() == b"MP4BYTES"
