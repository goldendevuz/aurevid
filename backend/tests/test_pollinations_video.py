# SPDX-License-Identifier: AGPL-3.0-or-later
"""Pollinations video adapter against a fake API (no network, no real key)."""

import httpx
import pytest

from app.providers import pollinations_video as pv
from app.providers.base import Credentials, GenerationRequest, ProviderError

KEY = Credentials({"api_key": "sk_test"}, "user")


def _req(model=pv.WAN_FAST, workdir=None):
    return GenerationRequest(
        prompt="a red kite over the sea",
        model=model,
        aspect_ratio="16:9",
        width=1344,
        height=768,
        seed=3,
        kind="video",
        duration_s=5,
        workdir=workdir,
    )


def _install(monkeypatch, handler):
    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(
        pv, "_http", lambda timeout: httpx.AsyncClient(transport=transport, timeout=timeout)
    )


async def test_returns_the_video_and_sends_the_key_only_to_pollinations(monkeypatch):
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, content=b"MP4BYTES", headers={"content-type": "video/mp4"})

    _install(monkeypatch, handler)
    media = await pv.PollinationsVideoProvider().generate(_req(), KEY)
    assert media.data == b"MP4BYTES" and media.mime == "video/mp4"
    request = seen[0]
    assert request.url.host == "gen.pollinations.ai"
    assert request.headers["authorization"] == "Bearer sk_test"
    assert request.url.params["model"] == pv.WAN_FAST
    assert request.url.params["resolution"] == "480p"
    assert request.url.params["aspectRatio"] == "16:9"


async def test_streams_to_disk_when_there_is_a_workdir(monkeypatch, tmp_path):
    _install(
        monkeypatch,
        lambda r: httpx.Response(200, content=b"MP4BYTES", headers={"content-type": "video/mp4"}),
    )
    media = await pv.PollinationsVideoProvider().generate(_req(workdir=tmp_path), KEY)
    assert media.data == b"" and media.path is not None and media.path.read_bytes() == b"MP4BYTES"


@pytest.mark.parametrize(
    ("status", "needle"),
    [(401, "rejected"), (402, "balance is empty"), (429, "rate limit")],
)
async def test_errors_are_readable(monkeypatch, status, needle):
    _install(monkeypatch, lambda r: httpx.Response(status, json={"error": "x"}))
    with pytest.raises(ProviderError) as err:
        await pv.PollinationsVideoProvider().generate(_req(), KEY)
    assert needle in err.value.public
    assert "sk_test" not in err.value.public


async def test_a_json_answer_is_not_a_video(monkeypatch):
    _install(monkeypatch, lambda r: httpx.Response(200, json={"ok": True}))
    with pytest.raises(ProviderError):
        await pv.PollinationsVideoProvider().generate(_req(), KEY)


async def test_needs_the_users_own_key():
    provider = pv.PollinationsVideoProvider()
    assert provider.has_usable_credentials(Credentials({}, "server")) is False
    with pytest.raises(ProviderError):
        await provider.generate(_req(), Credentials({}, "none"))
