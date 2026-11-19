# SPDX-License-Identifier: AGPL-3.0-or-later
"""FLUX.2 klein (text-to-image + edit with text), alt text and voice prompts on Cloudflare.

Every outgoing call goes through an httpx MockTransport: request shapes are checked, nothing
leaves the machine.
"""

import base64
import io
import json

import httpx
import pytest
from PIL import Image

from app import db
from app.config import get_settings
from app.models import Asset
from app.providers import cloudflare
from app.providers.base import Credentials, GenerationRequest, ProviderError
from app.worker import run_once
from tests.conftest import csrf_headers

CREDS = Credentials({"account_id": "a" * 32, "api_token": "tok-123456"}, "user")
WEBM = b"\x1a\x45\xdf\xa3" + b"\x00" * 200


def _jpeg(w: int = 64, h: int = 64, color=(200, 40, 40)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (w, h), color).save(buf, format="JPEG")
    return buf.getvalue()


def _form(request: httpx.Request) -> dict[str, bytes]:
    """Parse a multipart body into {field: raw bytes}."""
    boundary = request.headers["content-type"].split("boundary=")[1].encode()
    out = {}
    for part in request.content.split(b"--" + boundary):
        if b"name=" not in part:
            continue
        head, _, value = part.partition(b"\r\n\r\n")
        name = head.split(b'name="')[1].split(b'"')[0].decode()
        out[name] = value.rstrip(b"\r\n")
    return out


@pytest.fixture
def cf(monkeypatch):
    """Fake Workers AI. `state["status"]` forces an error code for every call."""
    state = {
        "seen": [],
        "status": 200,
        "caption": {"choices": [{"message": {"content": "A red square."}}]},
    }

    def handler(request: httpx.Request) -> httpx.Response:
        state["seen"].append(request)
        if state["status"] != 200:
            return httpx.Response(state["status"], json={"errors": [{"message": "nope"}]})
        path = request.url.path
        if path.endswith(cloudflare.KLEIN) or path.endswith(cloudflare.SCHNELL):
            img = base64.b64encode(_jpeg(256, 256)).decode()
            return httpx.Response(200, json={"result": {"image": img}})
        if path.endswith(cloudflare.CAPTION_MODEL):
            return httpx.Response(200, json={"result": state["caption"]})
        if path.endswith(cloudflare.WHISPER_MODEL):
            return httpx.Response(200, json={"result": {"text": " make it \x07 blue\n "}})
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    real = httpx.AsyncClient
    monkeypatch.setattr(
        cloudflare.httpx, "AsyncClient", lambda **kw: real(transport=transport, **kw)
    )
    return state


@pytest.fixture
def server_key():
    s = get_settings()
    s.cf_account_id, s.cf_api_token = "b" * 32, "server-token-xyz"


def _calls(state, model: str) -> list[httpx.Request]:
    return [r for r in state["seen"] if r.url.path.endswith(model)]


# --- adapter ---------------------------------------------------------------------------------


async def test_klein_text_to_image_is_multipart(cf):
    req = GenerationRequest("a lighthouse", cloudflare.KLEIN, "1:1", 768, 768, seed=7)
    out = await cloudflare.CloudflareProvider().generate(req, CREDS)
    assert out.mime == "image/jpeg" and out.data
    sent = cf["seen"][0]
    assert sent.url.path.endswith("/ai/run/@cf/black-forest-labs/flux-2-klein-4b")
    assert sent.headers["content-type"].startswith("multipart/form-data")
    form = _form(sent)
    assert form == {"prompt": b"a lighthouse", "width": b"768", "height": b"768", "seed": b"7"}


async def test_klein_edit_sends_small_reference_and_keeps_shape(cf):
    req = GenerationRequest(
        "make the background white", cloudflare.KLEIN, "1:1", 1024, 1024, image=_jpeg(1200, 800)
    )
    await cloudflare.CloudflareProvider().generate(req, CREDS)
    form = _form(cf["seen"][0])
    with Image.open(io.BytesIO(form["input_image_0"])) as ref:
        assert max(ref.size) <= cloudflare.KLEIN_INPUT_MAX_SIDE  # Workers AI: < 512x512
    assert (form["width"], form["height"]) == (b"1024", b"704")  # 3:2 kept, multiples of 64


async def test_schnell_body_unchanged(cf):
    req = GenerationRequest("x y z", cloudflare.SCHNELL, "1:1", 1024, 1024, seed=1)
    await cloudflare.CloudflareProvider().generate(req, CREDS)
    assert set(json.loads(cf["seen"][0].content)) == {"prompt", "steps"}


async def test_describe_image_request_and_both_response_shapes(cf):
    assert await cloudflare.describe_image(_jpeg(), CREDS) == "A red square."
    body = json.loads(cf["seen"][0].content)
    assert cf["seen"][0].url.path.endswith("/ai/run/@cf/qwen/qwen3.8-27b")
    assert body["chat_template_kwargs"] == {"enable_thinking": False}
    parts = body["messages"][0]["content"]
    assert parts[1]["image_url"]["url"].startswith("data:image/jpeg;base64,")
    cf["caption"] = {"response": "  A cat\x00 on a mat.  " + "x" * 400}
    text = await cloudflare.describe_image(_jpeg(), CREDS)
    assert text.startswith("A cat on a mat.") and len(text) <= cloudflare.ALT_TEXT_MAX


async def test_transcribe_request_and_cleaning(cf):
    assert await cloudflare.transcribe(WEBM, CREDS, "uz") == "make it blue"
    body = json.loads(cf["seen"][0].content)
    assert base64.b64decode(body["audio"]) == WEBM
    assert body["language"] == "uz" and body["task"] == "transcribe"
    assert cf["seen"][0].headers["authorization"] == "Bearer tok-123456"


async def test_quota_errors_are_flagged(cf):
    cf["status"] = 429
    with pytest.raises(ProviderError) as err:
        await cloudflare.transcribe(WEBM, CREDS)
    assert err.value.quota


async def test_klein_listed_as_commercial(alice):
    cf_info = {p["id"]: p for p in (await alice.get("/api/providers")).json()}["cloudflare"]
    klein = next(m for m in cf_info["models"] if m["id"] == cloudflare.KLEIN)
    assert klein["commercial_use"] == "yes" and klein["license"] == "Apache-2.0"
    assert klein["accepts_image"] is True


# --- edit with text --------------------------------------------------------------------------


async def _demo_image(client) -> str:
    job = (
        await client.post(
            "/api/jobs",
            json={"provider": "demo", "model": "gradient", "prompt": "product shot"},
            headers=csrf_headers(client),
        )
    ).json()
    await run_once()
    return (await client.get(f"/api/jobs/{job['id']}")).json()["assets"][0]["id"]


async def _edit(client, asset_id: str, instruction: str = "make the background white"):
    return await client.post(
        f"/api/assets/{asset_id}/edit",
        json={"instruction": instruction},
        headers=csrf_headers(client),
    )


async def test_edit_own_image_end_to_end(alice, cf, server_key):
    asset_id = await _demo_image(alice)
    cf["seen"].clear()
    r = await _edit(alice, asset_id)
    assert r.status_code == 201, r.text
    job = r.json()
    assert job["model"] == cloudflare.KLEIN and job["params"]["image_asset_id"] == asset_id
    await run_once()
    done = (await alice.get(f"/api/jobs/{job['id']}")).json()
    assert done["status"] == "done", done
    assert "input_image_0" in _form(_calls(cf, cloudflare.KLEIN)[0])
    # Alt text was written for the new image after the job finished.
    assert done["assets"][0]["alt_text"] == "A red square."
    sent = _calls(cf, cloudflare.CAPTION_MODEL)[0]
    assert sent.headers["authorization"] == "Bearer server-token-xyz"


async def test_cannot_edit_someone_elses_image(alice, bob, cf, server_key):
    asset_id = await _demo_image(alice)
    before = (await bob.get("/api/credits")).json()["balance"]
    r = await _edit(bob, asset_id)
    assert r.status_code == 404
    missing = await _edit(bob, "0" * 32)
    assert r.json() == missing.json()  # not-yours looks like not-found
    assert (await _edit(bob, "z" * 40)).status_code == 404
    assert (await bob.get("/api/credits")).json()["balance"] == before
    assert _calls(cf, cloudflare.KLEIN) == []


async def test_edit_instruction_is_moderated(alice, cf, server_key):
    asset_id = await _demo_image(alice)
    r = await _edit(alice, asset_id, "make her nude")
    assert r.status_code == 400 and r.json()["detail"]["code"] == "prompt_rejected"


async def test_edit_needs_a_cloudflare_key(alice):
    asset_id = await _demo_image(alice)
    r = await _edit(alice, asset_id)
    assert r.json()["detail"]["code"] == "provider_key_required"


async def test_edit_unavailable_when_cloudflare_disabled(alice):
    asset_id = await _demo_image(alice)
    get_settings().cloudflare_enabled = False
    r = await _edit(alice, asset_id)
    assert r.status_code == 503 and r.json()["detail"]["code"] == "edit_unavailable"


# --- alt text on uploads ---------------------------------------------------------------------


async def _upload(client, data: bytes):
    return await client.post(
        "/api/assets/upload",
        files={"file": ("x.jpg", data, "image/jpeg")},
        headers=csrf_headers(client),
    )


async def test_upload_gets_alt_text(alice, cf, server_key):
    r = await _upload(alice, _jpeg(900, 600))
    assert r.status_code == 201
    asset_id = r.json()["id"]
    sent = _calls(cf, cloudflare.CAPTION_MODEL)[0]
    url = json.loads(sent.content)["messages"][0]["content"][1]["image_url"]["url"]
    with Image.open(io.BytesIO(base64.b64decode(url.split(",", 1)[1]))) as small:
        assert max(small.size) <= 512  # few image tokens
    async with db.session_factory()() as session:
        assert (await session.get(Asset, asset_id)).alt_text == "A red square."


async def test_alt_text_failure_is_silent(alice, cf, server_key):
    cf["status"] = 500
    r = await _upload(alice, _jpeg())
    assert r.status_code == 201 and r.json()["alt_text"] is None


async def test_no_alt_text_without_key(alice, cf):
    assert (await _upload(alice, _jpeg())).status_code == 201
    assert cf["seen"] == []


# --- voice prompts ---------------------------------------------------------------------------


async def _voice(client, data: bytes = WEBM, language: str | None = "uz"):
    return await client.post(
        "/api/voice/transcribe",
        files={"file": ("voice.webm", data, "audio/webm")},
        data={"language": language} if language else {},
        headers=csrf_headers(client),
    )


async def test_voice_transcribes(alice, cf, server_key):
    r = await _voice(alice)
    assert r.status_code == 200, r.text
    assert r.json() == {"text": "make it blue"}
    assert json.loads(_calls(cf, cloudflare.WHISPER_MODEL)[0].content)["language"] == "uz"


async def test_voice_limits(alice, cf, server_key):
    get_settings().voice_max_bytes = 1000
    r = await _voice(alice, WEBM + b"\x00" * 1000)
    assert r.status_code == 413 and r.json()["detail"]["code"] == "audio_too_large"
    r = await _voice(alice, b"<html>" + b"\x00" * 100)
    assert r.status_code == 415 and r.json()["detail"]["code"] == "invalid_audio"
    assert (await _voice(alice, language="de")).status_code == 422
    assert cf["seen"] == []


async def test_voice_rate_limited(alice, cf, server_key):
    codes = [(await _voice(alice)).status_code for _ in range(7)]
    assert codes[:6] == [200] * 6 and codes[6] == 429


async def test_voice_needs_key_and_login(alice, anon, cf):
    r = await _voice(alice)
    assert r.json()["detail"]["code"] == "provider_key_required"
    await anon.get("/api/auth/csrf")
    assert (await _voice(anon)).status_code == 401
    assert cf["seen"] == []


async def test_voice_provider_failure(alice, cf, server_key):
    cf["status"] = 429
    r = await _voice(alice)
    assert r.status_code == 502 and r.json()["detail"]["code"] == "transcription_failed"
