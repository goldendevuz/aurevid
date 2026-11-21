# SPDX-License-Identifier: AGPL-3.0-or-later
"""Modal video adapter against a fake Modal workspace (no network, no real token)."""

import httpx
import pytest

from app.providers import modal_video as mv
from app.providers.base import Credentials, GenerationRequest, ProviderError

SUBMIT = "https://alice--aurevid-wan-submit.modal.run"
KEY = Credentials({"submit_url": SUBMIT, "token_id": "wk-1", "token_secret": "ws-1"}, "user")


def _req(aspect="16:9", duration=5, workdir=None):
    return GenerationRequest(
        prompt="waves",
        model=mv.WAN,
        aspect_ratio=aspect,
        width=0,
        height=0,
        seed=9,
        kind="video",
        duration_s=duration,
        workdir=workdir,
    )


def _install(monkeypatch, handler):
    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(
        mv, "_http", lambda timeout: httpx.AsyncClient(transport=transport, timeout=timeout)
    )
    monkeypatch.setattr(mv, "POLL_SECONDS", 0)


def _workspace(seen, pending=2):
    state = {"polls": 0}

    def handler(request):
        seen.append(request)
        if request.method == "POST":
            return httpx.Response(200, json={"call_id": "fc-1"})
        state["polls"] += 1
        if state["polls"] <= pending:
            return httpx.Response(202)
        return httpx.Response(200, content=b"MP4", headers={"content-type": "video/mp4"})

    return handler


async def test_submits_then_polls_the_sibling_result_endpoint(monkeypatch):
    seen = []
    _install(monkeypatch, _workspace(seen))
    media = await mv.ModalVideoProvider().generate(_req(), KEY)
    assert media.data == b"MP4" and media.mime == "video/mp4"
    post, *polls = seen
    assert post.url.host == "alice--aurevid-wan-submit.modal.run"
    assert polls[0].url.host == "alice--aurevid-wan-result.modal.run"
    assert polls[0].url.params["call_id"] == "fc-1"
    assert post.headers["modal-key"] == "wk-1" and post.headers["modal-secret"] == "ws-1"
    assert len(polls) == 3


async def test_sizes_and_frames_follow_the_ratio_and_duration(monkeypatch):
    seen = []
    _install(monkeypatch, _workspace(seen, pending=0))
    await mv.ModalVideoProvider().generate(_req(aspect="9:16", duration=3), KEY)
    import json

    body = json.loads(seen[0].content)
    assert (body["width"], body["height"], body["frames"], body["seed"]) == (480, 832, 73, 9)
    assert body["width"] % 32 == 0 and body["height"] % 32 == 0 and (body["frames"] - 1) % 4 == 0


async def test_streams_to_disk_with_a_workdir(monkeypatch, tmp_path):
    _install(monkeypatch, _workspace([], pending=0))
    media = await mv.ModalVideoProvider().generate(_req(workdir=tmp_path), KEY)
    assert media.path is not None and media.path.read_bytes() == b"MP4"


@pytest.mark.parametrize(
    "url",
    [
        "http://alice--aurevid-wan-submit.modal.run",
        "https://evil.example.com/--submit.modal.run",
        "https://alice--aurevid-wan-submit.modal.run.evil.com",
        "https://alice--aurevid-wan-result.modal.run",
    ],
)
def test_only_modal_submit_urls_are_accepted(url):
    with pytest.raises(ProviderError):
        mv.endpoints(url)


@pytest.mark.parametrize(
    ("status", "needle"), [(401, "rejected"), (404, "not found"), (422, "refused")]
)
async def test_errors_are_readable_and_never_show_the_token(monkeypatch, status, needle):
    _install(monkeypatch, lambda r: httpx.Response(status, json={"detail": "x"}))
    with pytest.raises(ProviderError) as err:
        await mv.ModalVideoProvider().generate(_req(), KEY)
    assert needle in err.value.public and "ws-1" not in err.value.public


async def test_needs_all_three_user_values():
    provider = mv.ModalVideoProvider()
    assert provider.has_usable_credentials(Credentials({}, "server")) is False
    with pytest.raises(ProviderError):
        await provider.generate(_req(), Credentials({"submit_url": SUBMIT}, "user"))


def _modal_models(**flags):
    from app.config import get_settings
    from app.providers.registry import enabled_providers

    s = get_settings()
    s.modal_video_enabled = True
    for k, v in flags.items():
        setattr(s, k, v)
    return [m.id for m in enabled_providers()["modal_video"].info.models]


def test_ltx_is_hidden_by_default_and_wan_is_unchanged():
    assert _modal_models() == [mv.WAN, mv.WAN_LONG]


def test_ltx_is_visible_only_with_allow_unclear_models():
    assert _modal_models(allow_unclear_models=True) == [mv.WAN, mv.WAN_LONG, mv.LTX]
    ltx = mv.ModalVideoProvider().model(mv.LTX)
    assert ltx.commercial_use == "unclear" and ltx.has_audio is True
    assert mv.ModalVideoProvider().model(mv.WAN).has_audio is False


async def test_payload_carries_the_model_and_ltx_uses_its_own_sizes(monkeypatch):
    import dataclasses
    import json

    seen = []
    _install(monkeypatch, _workspace(seen, pending=0))
    ltx_req = dataclasses.replace(_req(aspect="9:16", duration=3), model=mv.LTX)
    await mv.ModalVideoProvider().generate(ltx_req, KEY)
    await mv.ModalVideoProvider().generate(_req(), KEY)
    ltx_body, wan_body = json.loads(seen[0].content), json.loads(seen[2].content)
    assert ltx_body["model"] == mv.LTX
    assert (ltx_body["width"], ltx_body["height"], ltx_body["frames"]) == (448, 768, 73)
    assert (ltx_body["frames"] - 1) % 8 == 0 and ltx_body["width"] % 32 == 0
    assert wan_body["model"] == mv.WAN and (wan_body["width"], wan_body["height"]) == (832, 480)


def test_long_clip_model_is_own_key_only_and_uses_wan_endpoint():
    from app.providers import modal_video as mv

    info = {m.id: m for m in mv.ModalVideoProvider().info.models}
    long_ = info[mv.WAN_LONG]
    assert long_.commercial_use == "yes" and long_.server_key_ok is False
    assert long_.durations == [15] and long_.credit_cost > info[mv.WAN].credit_cost
    assert mv._LONG_FRAMES == 361 and (361 - 1) % 4 == 0
    assert all(w % 32 == 0 and h % 32 == 0 for w, h in mv._LONG_SIZES.values())


async def test_worker_gives_the_long_clip_its_own_timeout(monkeypatch):
    import asyncio

    from app import worker
    from app.providers.base import GenerationRequest

    seen = []
    real = asyncio.wait_for

    async def spy(coro, timeout):  # noqa: ASYNC109
        seen.append(timeout)
        return await real(coro, timeout=timeout)

    class Fake:
        info = __import__("app.providers.modal_video", fromlist=["x"]).ModalVideoProvider().info

        async def generate(self, req, creds):
            return "ok"

    monkeypatch.setattr(worker.asyncio, "wait_for", spy)
    from app.providers import modal_video as mv

    for model, expect in ((mv.WAN, 600), (mv.WAN_LONG, mv.LONG_CLIP_TIMEOUT_S)):
        req = GenerationRequest(
            prompt="x", model=model, aspect_ratio="16:9", width=8, height=8, kind="video"
        )
        assert await worker._generate_with_retry(Fake(), req, None) == "ok"
        assert seen[-1] == expect
