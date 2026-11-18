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
