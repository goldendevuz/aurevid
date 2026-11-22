# SPDX-License-Identifier: AGPL-3.0-or-later
"""Tests for extended OpenRouter video models, pricing, access levels, and registry."""

import json
from pathlib import Path

import httpx
import pytest
from sqlalchemy import select

from app import db
from app.models import CreditLedger
from app.providers import openrouter_video as orv
from app.providers.base import Credentials, GenerationRequest, ProviderError
from app.providers.registry import enabled_providers, get_provider
from app.worker import run_once
from tests.conftest import csrf_headers

KEY = "sk-or-v1-" + "k" * 40
CREDS = Credentials({"api_key": KEY}, "user")
DEMO_MP4 = Path(__file__).resolve().parent.parent / "app" / "providers" / "media" / "demo.mp4"
MP4 = DEMO_MP4.read_bytes()


def _install(monkeypatch, handler):
    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(
        orv, "_http", lambda timeout: httpx.AsyncClient(transport=transport, timeout=timeout)
    )
    monkeypatch.setattr(orv, "POLL_SECONDS", 0)
    monkeypatch.setattr(orv, "SUBMIT_429_BACKOFF", 0)


def _openrouter(seen, *, final="completed", pending=0, cost=0.25, error=None, submit=None):
    state = {"polls": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        path = request.url.path
        if request.method == "POST":
            if submit is not None:
                return submit(request)
            return httpx.Response(
                202,
                json={"id": "vid_2", "status": "pending"},
            )
        if path.endswith("/content"):
            return httpx.Response(200, content=MP4, headers={"content-type": "video/mp4"})
        state["polls"] += 1
        if state["polls"] <= pending:
            return httpx.Response(200, json={"id": "vid_2", "status": "in_progress"})
        body = {"id": "vid_2", "status": final}
        if final == "completed":
            body["usage"] = {"cost": cost}
        if error:
            body["error"] = error
        return httpx.Response(200, json=body)

    return handler


async def _key(client, provider="openrouter_video"):
    r = await client.put(
        f"/api/me/keys/{provider}",
        json={"values": {"api_key": KEY}},
        headers=csrf_headers(client),
    )
    assert r.status_code == 200, r.text


# 1. openrouter_models.json file test
def test_openrouter_models_json_exists_and_valid():
    json_path = Path(__file__).resolve().parents[1] / "app" / "providers" / "openrouter_models.json"
    assert json_path.exists(), "openrouter_models.json must exist"
    data = json.loads(json_path.read_text(encoding="utf-8"))
    assert isinstance(data, list)
    assert len(data) >= 15
    slugs = {m["slug"] for m in data}
    expected = {
        orv.MINI,
        orv.FLASH,
        orv.PRO,
        orv.SEEDANCE_20,
        orv.SEEDANCE_20_FAST,
        orv.WAN_30,
        orv.WAN_30_PRIME,
        orv.HAPPYHORSE_10,
        orv.HAPPYHORSE_11,
        orv.GROK_15,
        orv.HAILUO_23,
        orv.VEO_31,
        orv.VEO_31_FAST,
        orv.VEO_31_LITE,
        orv.RUNWAY_GEN_45,
    }
    assert expected.issubset(slugs)


# 2. Sync script exists and is callable
def test_sync_openrouter_models_script():
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "sync_openrouter_models.py"
    assert script_path.exists()
    assert script_path.stat().st_mode & 0o111  # executable


# 3. Mini 4s 480p 16:9 price test (P2 specification exact case: >= 0.1421 and < 0.1421 * 1.1)
def test_mini_4s_480p_16_9_price_in_exact_range():
    usd = orv.estimate_usd(orv.MINI, "480p", "16:9", 4)
    assert usd is not None
    # Real run billed $0.1421. Must be >= 0.1421 and < 0.1421 * 1.1 (0.15631).
    assert usd >= 0.1421
    assert usd < 0.1421 * 1.1


# 4. Token model pricing table test
@pytest.mark.parametrize(
    "model_id,res,expected_per_sec",
    [
        (orv.SEEDANCE_20, "480p", 0.07242),
        (orv.SEEDANCE_20, "720p", 0.16119),
        (orv.SEEDANCE_20, "1080p", 0.40042),
        (orv.SEEDANCE_20_FAST, "480p", 0.05793),
        (orv.SEEDANCE_20_FAST, "720p", 0.12895),
    ],
)
def test_token_model_pricing_table(model_id, res, expected_per_sec):
    rate = orv.usd_per_second(model_id, res, "16:9")
    assert rate == pytest.approx(expected_per_sec, abs=0.001)


# 5. Per-second model pricing: Wan 3.0 & Wan 3.0 Prime
def test_per_second_model_pricing_wan30():
    assert orv.usd_per_second(orv.WAN_30, "480p", "16:9") == 0.05
    assert orv.usd_per_second(orv.WAN_30, "720p", "16:9") == 0.10
    assert orv.usd_per_second(orv.WAN_30, "1080p", "16:9") == 0.20
    assert orv.usd_per_second(orv.WAN_30_PRIME, "480p", "16:9") == 0.068
    assert orv.usd_per_second(orv.WAN_30_PRIME, "720p", "16:9") == 0.14
    assert orv.usd_per_second(orv.WAN_30_PRIME, "1080p", "16:9") == 0.28


# 6. Per-second model pricing: HappyHorse
def test_per_second_model_pricing_happyhorse():
    assert orv.usd_per_second(orv.HAPPYHORSE_10, "720p", "16:9") == 0.0988
    assert orv.usd_per_second(orv.HAPPYHORSE_10, "1080p", "16:9") == 0.1694
    assert orv.usd_per_second(orv.HAPPYHORSE_11, "720p", "16:9") == 0.0988
    assert orv.usd_per_second(orv.HAPPYHORSE_11, "1080p", "16:9") == 0.1278


# 7. Per-second model pricing: Grok Imagine 1.5
def test_per_second_model_pricing_grok():
    assert orv.usd_per_second(orv.GROK_15, "480p", "16:9") == 0.08
    assert orv.usd_per_second(orv.GROK_15, "720p", "16:9") == 0.14
    assert orv.usd_per_second(orv.GROK_15, "1080p", "16:9") == 0.25


# 8. Per-second model pricing: Hailuo 2.3
def test_per_second_model_pricing_hailuo():
    assert orv.usd_per_second(orv.HAILUO_23, "1080p", "16:9") == 0.0817


# 9. Per-second model pricing: Veo 3.1 family
def test_per_second_model_pricing_veo():
    assert orv.usd_per_second(orv.VEO_31, "720p", "16:9") == 0.40
    assert orv.usd_per_second(orv.VEO_31, "1080p", "16:9") == 0.40
    assert orv.usd_per_second(orv.VEO_31, "4K", "16:9") == 0.60
    assert orv.usd_per_second(orv.VEO_31_FAST, "720p", "16:9") == 0.10
    assert orv.usd_per_second(orv.VEO_31_FAST, "1080p", "16:9") == 0.12
    assert orv.usd_per_second(orv.VEO_31_LITE, "720p", "16:9") == 0.05
    assert orv.usd_per_second(orv.VEO_31_LITE, "1080p", "16:9") == 0.08


# 10. Per-second model pricing: Runway Gen-4.5
def test_per_second_model_pricing_runway():
    assert orv.usd_per_second(orv.RUNWAY_GEN_45, "720p", "16:9") == 0.12


# 11. Public catalog models only contains commercial_use == "yes"
async def test_public_catalog_models_only_contains_yes(anon):
    r = await anon.get("/api/catalog/models")
    assert r.status_code == 200
    models = r.json()
    provider = get_provider("openrouter_video")
    assert provider is not None
    # All models in public catalog must be commercial_use == "yes"
    for m_entry in models:
        p = get_provider(m_entry["provider_id"])
        if p:
            m = p.model(m_entry["id"])
            assert m is not None
            assert m.commercial_use == "yes"


# 12. Public catalog models excludes byok_only models
async def test_public_catalog_models_excludes_byok_only_models(anon):
    r = await anon.get("/api/catalog/models")
    models = r.json()
    ids = {m["id"] for m in models}
    byok_models = [
        orv.WAN_30,
        orv.WAN_30_PRIME,
        orv.HAPPYHORSE_10,
        orv.HAPPYHORSE_11,
        orv.GROK_15,
        orv.HAILUO_23,
        orv.VEO_31,
        orv.VEO_31_FAST,
        orv.VEO_31_LITE,
        orv.RUNWAY_GEN_45,
    ]
    for b in byok_models:
        assert b not in ids, f"{b} must not appear in public catalog"


# 13. Registry test: no non-yes non-byok model is public
def test_registry_no_non_yes_non_byok_model_is_public():
    providers = enabled_providers()
    for p in providers.values():
        for m in p.info.models:
            assert m.commercial_use in ("yes", "byok_only"), (p.info.id, m.id)


# 14. Signed-in user without key does not see byok_only models in active models
async def test_signed_in_user_without_key_does_not_see_byok_only_models(alice):
    r = await alice.get("/api/providers")
    assert r.status_code == 200
    providers = r.json()
    p = next(x for x in providers if x["id"] == "openrouter_video")
    model_ids = {m["id"] for m in p["models"]}
    assert orv.WAN_30 not in model_ids
    assert orv.VEO_31 not in model_ids
    assert orv.MINI in model_ids
    assert orv.SEEDANCE_20 in model_ids


# 15. Signed-in user with key sees byok_only models
async def test_signed_in_user_with_key_sees_byok_only_models(alice):
    await _key(alice)
    r = await alice.get("/api/providers")
    assert r.status_code == 200
    providers = r.json()
    p = next(x for x in providers if x["id"] == "openrouter_video")
    model_ids = {m["id"] for m in p["models"]}
    assert orv.WAN_30 in model_ids
    assert orv.VEO_31 in model_ids
    assert orv.GROK_15 in model_ids
    assert orv.RUNWAY_GEN_45 in model_ids


# 16. Submitting byok_only model without user key raises provider_key_required
async def test_byok_only_model_refuses_without_user_key(alice):
    r = await alice.post(
        "/api/jobs",
        json={
            "provider": "openrouter_video",
            "model": orv.WAN_30,
            "prompt": "flying eagle over mountains",
            "aspect_ratio": "16:9",
            "duration": 5,
        },
        headers=csrf_headers(alice),
    )
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "provider_key_required"


# 17. byok_only model runs with user key
async def test_byok_only_model_runs_with_user_key(alice, monkeypatch):
    await _key(alice)
    seen = []
    _install(monkeypatch, _openrouter(seen, cost=0.50))
    r = await alice.post(
        "/api/jobs",
        json={
            "provider": "openrouter_video",
            "model": orv.WAN_30,
            "prompt": "flying eagle over mountains",
            "aspect_ratio": "16:9",
            "duration": 5,
            "resolution": "720p",
        },
        headers=csrf_headers(alice),
    )
    assert r.status_code == 201, r.text
    job = r.json()
    assert job["model"] == orv.WAN_30
    assert job["params"]["resolution"] == "720p"
    assert job["params"]["estimated_usd"] == pytest.approx(0.50)


# 18. byok_only model failed refunds credits
async def test_byok_only_model_failed_refunds_credits(alice, monkeypatch):
    await _key(alice)
    _install(monkeypatch, _openrouter([], final="failed", error="safety filter"))
    r = await alice.post(
        "/api/jobs",
        json={
            "provider": "openrouter_video",
            "model": orv.WAN_30,
            "prompt": "sunset on mars",
            "aspect_ratio": "16:9",
            "duration": 5,
        },
        headers=csrf_headers(alice),
    )
    assert r.status_code == 201
    job = r.json()
    await run_once()
    done = (await alice.get(f"/api/jobs/{job['id']}")).json()
    assert done["status"] == "failed"
    assert "OpenRouter video failed: safety filter" in done["error"]
    async with db.session_factory()() as s:
        rows = (
            (await s.execute(select(CreditLedger).where(CreditLedger.job_id == job["id"])))
            .scalars()
            .all()
        )
    assert sorted(r.delta for r in rows) == [-job["cost"], job["cost"]]


# 19. byok_only model 402 handling
async def test_byok_only_model_402_handling(alice, monkeypatch):
    await _key(alice)
    _install(monkeypatch, _openrouter([], submit=lambda r: httpx.Response(402, json={})))
    r = await alice.post(
        "/api/jobs",
        json={
            "provider": "openrouter_video",
            "model": orv.WAN_30,
            "prompt": "ocean waves",
            "aspect_ratio": "16:9",
            "duration": 5,
        },
        headers=csrf_headers(alice),
    )
    assert r.status_code == 201
    job = r.json()
    await run_once()
    done = (await alice.get(f"/api/jobs/{job['id']}")).json()
    assert done["status"] == "failed"
    assert "credits are used up" in done["error"]


# 20. byok_only model expired handling
async def test_byok_only_model_expired_handling(monkeypatch):
    _install(monkeypatch, _openrouter([], final="expired"))
    req = GenerationRequest(
        prompt="neon city",
        model=orv.GROK_15,
        aspect_ratio="16:9",
        width=1280,
        height=720,
        kind="video",
        duration_s=5,
        resolution="720p",
    )
    with pytest.raises(ProviderError) as exc:
        await orv.OpenRouterVideoProvider().generate(req, CREDS)
    assert "expired" in exc.value.public


# 21. byok_only model 429 backoff
async def test_byok_only_model_429_backoff(monkeypatch):
    tries = {"n": 0}

    def submit(request):
        tries["n"] += 1
        if tries["n"] < 2:
            return httpx.Response(429, json={})
        return httpx.Response(202, json={"id": "vid_2", "status": "pending"})

    _install(monkeypatch, _openrouter([], submit=submit))
    req = GenerationRequest(
        prompt="neon city",
        model=orv.RUNWAY_GEN_45,
        aspect_ratio="16:9",
        width=1280,
        height=720,
        kind="video",
        duration_s=5,
        resolution="720p",
    )
    media = await orv.OpenRouterVideoProvider().generate(req, CREDS)
    assert media.data == MP4
    assert tries["n"] == 2


# 22. Ambiguous submit is never retried for new models
async def test_ambiguous_submit_never_retried_for_new_models(monkeypatch):
    posts = []

    def submit(request):
        posts.append(request)
        raise httpx.ReadTimeout("slow", request=request)

    _install(monkeypatch, _openrouter([], submit=submit))
    req = GenerationRequest(
        prompt="neon city",
        model=orv.HAILUO_23,
        aspect_ratio="16:9",
        width=1920,
        height=1080,
        kind="video",
        duration_s=6,
        resolution="1080p",
    )
    with pytest.raises(ProviderError) as exc:
        await orv.OpenRouterVideoProvider().generate(req, CREDS)
    assert exc.value.retryable is False
    assert len(posts) == 1


# 23. Default resolution is cheapest
def test_new_models_default_to_cheapest_resolution():
    provider = orv.OpenRouterVideoProvider()
    wan = provider.model(orv.WAN_30)
    assert wan is not None and wan.default_resolution == "480p"
    grok = provider.model(orv.GROK_15)
    assert grok is not None and grok.default_resolution == "480p"
    hailuo = provider.model(orv.HAILUO_23)
    assert hailuo is not None and hailuo.default_resolution == "1080p"
    veo = provider.model(orv.VEO_31)
    assert veo is not None and veo.default_resolution == "720p"
    runway = provider.model(orv.RUNWAY_GEN_45)
    assert runway is not None and runway.default_resolution == "720p"


# 24. Audio capability matching
def test_new_models_audio_flags_match_capabilities():
    provider = orv.OpenRouterVideoProvider()
    assert provider.model(orv.WAN_30).has_audio is True
    assert provider.model(orv.GROK_15).has_audio is True
    assert provider.model(orv.VEO_31).has_audio is True
    assert provider.model(orv.HAPPYHORSE_10).has_audio is False
    assert provider.model(orv.HAILUO_23).has_audio is False
    assert provider.model(orv.RUNWAY_GEN_45).has_audio is False


# 25. MODEL_LICENSES.md contains all models
def test_model_licenses_contains_all_models():
    doc = (
        Path(__file__)
        .resolve()
        .parents[2]
        .joinpath("MODEL_LICENSES.md")
        .read_text(encoding="utf-8")
    )
    for model_id in [
        orv.MINI,
        orv.FLASH,
        orv.PRO,
        orv.SEEDANCE_20,
        orv.SEEDANCE_20_FAST,
        orv.WAN_30,
        orv.WAN_30_PRIME,
        orv.HAPPYHORSE_10,
        orv.HAPPYHORSE_11,
        orv.GROK_15,
        orv.HAILUO_23,
        orv.VEO_31,
        orv.VEO_31_FAST,
        orv.VEO_31_LITE,
        orv.RUNWAY_GEN_45,
    ]:
        assert model_id in doc, f"{model_id} must be recorded in MODEL_LICENSES.md"


# 26. Server key refuses byok_only models
def test_server_key_refuses_byok_only_models():
    provider = orv.OpenRouterVideoProvider()
    assert provider.server_allows(orv.MINI, "480p") is True
    assert provider.server_allows(orv.MINI, "720p") is False
    assert provider.server_allows(orv.PRO, "480p") is False
    assert provider.server_allows(orv.WAN_30, "480p") is False
    assert provider.server_allows(orv.VEO_31, "720p") is False
