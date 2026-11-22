# SPDX-License-Identifier: AGPL-3.0-or-later
"""The landing page lists real models without logging in."""

import httpx

from app.main import app
from app.providers.registry import enabled_providers


async def test_public_models_match_registry_and_need_no_login():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as anon:
        r = await anon.get("/api/catalog/models")
    assert r.status_code == 200
    got = {(m["provider_id"], m["id"]) for m in r.json()}
    want = {
        (p.info.id, m.id)
        for p in enabled_providers().values()
        for m in p.info.models
        if m.kind in ("image", "video") and m.commercial_use == "yes"
    }
    assert got == want and got
    assert set(r.json()[0]) == {"provider_id", "provider", "id", "label", "kind"}
