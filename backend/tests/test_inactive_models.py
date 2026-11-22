# SPDX-License-Identifier: AGPL-3.0-or-later
"""Tests for inactive models: endpoint, signed-in requirement, isolation, and pricing."""

import httpx

from app.config import get_settings
from app.main import app
from app.providers import openrouter_video as orv
from tests.conftest import csrf_headers


async def test_inactive_models_requires_signed_in_user():
    """Anonymous access must be rejected with 401."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as anon:
        r = await anon.get("/api/catalog/inactive-models")
    assert r.status_code == 401


async def test_signed_in_user_sees_inactive_models(alice):
    """Signed-in user without key sees byok_only models in inactive list when server key set."""
    get_settings().openrouter_api_key = "sk-or-server-key"
    get_settings().openrouter_free_clips_per_user = 3
    r = await alice.get("/api/catalog/inactive-models")
    assert r.status_code == 200
    models = r.json()
    model_ids = {m["id"] for m in models}

    # Wan 3.0, Veo 3.1, Grok 1.5, Runway are byok_only and inactive without user key
    assert orv.WAN_30 in model_ids
    assert orv.VEO_31 in model_ids
    assert orv.GROK_15 in model_ids
    assert orv.RUNWAY_GEN_45 in model_ids

    # Commercial 'yes' models with server key (Seedance Mini / 2.0) are NOT inactive
    assert orv.MINI not in model_ids
    assert orv.SEEDANCE_20 not in model_ids

    # Check model row schema
    wan = next(m for m in models if m["id"] == orv.WAN_30)
    assert wan["provider_id"] == "openrouter_video"
    assert wan["provider_name"] == "OpenRouter"
    assert wan["commercial_use"] == "byok_only"
    assert wan["reason"] == "Needs your OpenRouter key"
    assert wan["price_text"] == "from ≈ 5¢ / s"
    assert wan["price_cents"] == 5
    assert wan["settings_path"] == "/settings"
    assert wan["key_url"] == "https://openrouter.ai/settings/keys"


async def test_inactive_models_when_provider_has_no_server_key(alice):
    """When provider has no server key, all its models appear in inactive list."""
    get_settings().openrouter_api_key = ""
    r = await alice.get("/api/catalog/inactive-models")
    assert r.status_code == 200
    models = r.json()
    model_ids = {m["id"] for m in models}

    # All openrouter models are inactive because provider has no credentials
    assert orv.MINI in model_ids
    assert orv.SEEDANCE_20 in model_ids
    assert orv.WAN_30 in model_ids


async def test_inactive_models_never_leaks_other_users_keys_or_state(alice, bob):
    """Alice adding a key removes models from Alice's inactive list, but never Bob's."""
    get_settings().openrouter_api_key = "sk-or-server-key"

    # Alice adds her OpenRouter key
    r = await alice.put(
        "/api/me/keys/openrouter_video",
        json={"values": {"api_key": "sk-or-alice"}},
        headers=csrf_headers(alice),
    )
    assert r.status_code == 200

    # Alice's inactive models: Wan 3.0 and Veo 3.1 are no longer inactive
    r_alice = await alice.get("/api/catalog/inactive-models")
    assert r_alice.status_code == 200
    alice_model_ids = {m["id"] for m in r_alice.json()}
    assert orv.WAN_30 not in alice_model_ids
    assert orv.VEO_31 not in alice_model_ids

    # Bob has no key: Bob STILL sees Wan 3.0 and Veo 3.1 in his inactive models
    r_bob = await bob.get("/api/catalog/inactive-models")
    assert r_bob.status_code == 200
    bob_model_ids = {m["id"] for m in r_bob.json()}
    assert orv.WAN_30 in bob_model_ids
    assert orv.VEO_31 in bob_model_ids


async def test_providers_endpoint_includes_inactive_models(alice):
    """The /api/providers endpoint includes inactive_models matching the catalog."""
    get_settings().openrouter_api_key = "sk-or-server-key"
    r = await alice.get("/api/providers")
    assert r.status_code == 200
    providers = r.json()
    or_p = next(p for p in providers if p["id"] == "openrouter_video")
    assert "inactive_models" in or_p
    inactive_ids = {m["id"] for m in or_p["inactive_models"]}
    assert orv.WAN_30 in inactive_ids
    assert orv.VEO_31 in inactive_ids


async def test_public_models_never_includes_inactive_models():
    """Public catalog /api/catalog/models never includes inactive / byok_only models."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as anon:
        r = await anon.get("/api/catalog/models")
    assert r.status_code == 200
    public_model_ids = {m["id"] for m in r.json()}
    assert orv.WAN_30 not in public_model_ids
    assert orv.VEO_31 not in public_model_ids
    assert orv.SEEDANCE_20 in public_model_ids
