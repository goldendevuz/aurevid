# SPDX-License-Identifier: AGPL-3.0-or-later
"""Marketing helper: templates, palette, AI path (mocked), safety, IDOR."""

import io
import json

import httpx
import pytest
from PIL import Image

from app.services import marketing
from tests.conftest import csrf_headers

BODY = {"product": "Atlas tea set", "description": "hand-painted ceramic", "tone": "premium"}


async def _post(client, **kw):
    return await client.post(
        "/api/marketing/ideas", json={**BODY, **kw}, headers=csrf_headers(client)
    )


async def test_template_ideas_both_formats_and_languages(alice):
    for lang, word in (("uz", "Atlas tea set"), ("ru", "Atlas tea set"), ("en", "Atlas tea set")):
        r = await _post(alice, language=lang, per_format=2, seed=1)
        data = r.json()
        assert r.status_code == 200 and data["source"] == "templates"
        fmts = [i["format"] for i in data["ideas"]]
        assert fmts.count("9:16") == 2 and fmts.count("1:1") == 2
        assert all(word in i["headline"] for i in data["ideas"])
        assert all("no text in the image" in i["prompt"] for i in data["ideas"])
    vertical = [i for i in data["ideas"] if i["format"] == "9:16"][0]
    assert "space at the top" in vertical["prompt"]


async def test_seed_is_deterministic(alice):
    a = (await _post(alice, seed=42)).json()["ideas"]
    b = (await _post(alice, seed=42)).json()["ideas"]
    assert a == b


async def test_palette_from_own_photo(alice, bob):
    img = Image.new("RGB", (120, 80), (40, 90, 200))
    img.paste((240, 140, 30), (0, 0, 40, 80))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    up = await alice.post(
        "/api/assets/upload",
        files={"file": ("p.png", buf.getvalue(), "image/png")},
        headers=csrf_headers(alice),
    )
    asset_id = up.json()["id"]
    data = (await _post(alice, image_asset_id=asset_id, seed=3)).json()
    names = [c["name"] for c in data["palette"]]
    assert "blue" in names and "orange" in names
    assert (await _post(bob, image_asset_id=asset_id)).status_code == 404  # not yours


async def test_unsafe_product_text_rejected(alice):
    r = await _post(alice, product="nude teen photo set")
    assert r.status_code == 400 and r.json()["detail"]["code"] == "prompt_rejected"


async def test_ai_requested_without_key_falls_back(alice):
    data = (await _post(alice, use_ai=True)).json()
    assert data["source"] == "templates" and data["note"] == "ai_needs_key"


@pytest.fixture
def fake_llm(monkeypatch):
    def install(payload, status=200):
        def handler(request):
            sent = json.loads(request.content)
            assert "guided_json" in sent and sent["messages"][0]["role"] == "system"
            return httpx.Response(status, json={"result": {"response": payload}})

        transport = httpx.MockTransport(handler)
        real = httpx.AsyncClient
        monkeypatch.setattr(
            marketing.httpx, "AsyncClient", lambda **kw: real(transport=transport, **kw)
        )

    return install


CREDS = marketing.Credentials({"account_id": "a" * 32, "api_token": "t"}, "user")


async def test_ai_output_is_validated_and_moderated(fake_llm):
    fake_llm(
        {
            "ideas": [
                {"format": "9:16", "scene": "x", "prompt": "Tea set on a marble table at golden hour", "headline": "Choy vaqti", "cta": "Buyurtma"},
                {"format": "1:1", "scene": "y", "prompt": "explicit nsfw scene with the tea set ok", "headline": "h", "cta": "c"},
                {"format": "1:1", "scene": "z", "prompt": "Tea set in a cozy kitchen with steam rising", "headline": "Iliq", "cta": "Oling"},
                {"format": "4:5", "scene": "bad", "prompt": "ignored format", "headline": "h", "cta": "c"},
            ]
        }
    )  # fmt: skip
    ideas = await marketing.ai_ideas(CREDS, "Tea", "", "", "friendly", "uz", 2, [])
    assert [i.format for i in ideas] == ["9:16", "1:1"]  # unsafe + bad format dropped
    assert all("no text in the image" in i.prompt for i in ideas)


async def test_ai_garbage_raises_for_fallback(fake_llm):
    fake_llm("not json at all")
    with pytest.raises(marketing.LLMUnavailable):
        await marketing.ai_ideas(CREDS, "Tea", "", "", "friendly", "en", 2, [])
