# SPDX-License-Identifier: AGPL-3.0-or-later
from pathlib import Path

from app.config import get_settings
from app.worker import run_once
from tests.conftest import csrf_headers

DEMO = {"provider": "demo", "model": "gradient"}


async def create(client, **overrides):
    body = {**DEMO, "prompt": "a red bicycle by the sea", **overrides}
    return await client.post("/api/jobs", json=body, headers=csrf_headers(client))


async def test_catalog_marks_free_and_key_requirements(alice):
    providers = {p["id"]: p for p in (await alice.get("/api/providers")).json()}
    assert providers["demo"]["tier"] == "free" and providers["demo"]["available"]
    assert providers["cloudflare"]["requires_key"] and not providers["cloudflare"]["available"]
    assert providers["cloudflare"]["key_source"] == "none"
    assert "api_token" not in str(providers["cloudflare"].get("key_source"))
    presets = (await alice.get("/api/presets")).json()
    assert len(presets) >= 3


async def test_job_lifecycle_debits_and_produces_assets(alice):
    r = await create(alice, count=2, aspect_ratio="16:9")
    assert r.status_code == 201, r.text
    job = r.json()
    assert job["status"] == "queued" and job["cost"] == 2
    assert "final_prompt" not in job["params"]
    assert (await alice.get("/api/credits")).json()["balance"] == 8

    assert await run_once()
    done = (await alice.get(f"/api/jobs/{job['id']}")).json()
    assert done["status"] == "done" and len(done["assets"]) == 2
    f = await alice.get(done["assets"][0]["url"])
    assert f.status_code == 200 and f.headers["content-type"] == "image/webp"
    assert f.content[:4] == b"RIFF"
    assert f.headers["x-content-type-options"] == "nosniff"

    history = (await alice.get("/api/jobs")).json()
    assert [j["id"] for j in history] == [job["id"]]


async def test_failed_job_is_refunded(alice):
    job = (await create(alice, prompt="please __fail__ now", count=3)).json()
    assert (await alice.get("/api/credits")).json()["balance"] == 7
    await run_once()
    failed = (await alice.get(f"/api/jobs/{job['id']}")).json()
    assert failed["status"] == "failed" and failed["error"]
    usage = (await alice.get("/api/credits")).json()
    assert usage["balance"] == 10
    reasons = [e["reason"] for e in usage["ledger"]]
    assert reasons.count("refund") == 1


async def test_insufficient_credits(alice):
    for _ in range(2):
        assert (await create(alice, count=4)).status_code == 201
    r = await create(alice, count=4)
    assert r.status_code == 402 and r.json()["detail"]["code"] == "insufficient_credits"
    assert (await alice.get("/api/credits")).json()["balance"] == 2


async def test_daily_limit(alice):
    get_settings().daily_job_limit = 2
    assert (await create(alice)).status_code == 201
    assert (await create(alice)).status_code == 201
    r = await create(alice)
    assert r.status_code == 429 and r.json()["detail"]["code"] == "daily_limit_reached"


async def test_idempotency_key_prevents_double_charge(alice):
    h = {**csrf_headers(alice), "Idempotency-Key": "req-123"}
    body = {**DEMO, "prompt": "same request twice"}
    a = await alice.post("/api/jobs", json=body, headers=h)
    b = await alice.post("/api/jobs", json=body, headers=h)
    assert a.json()["id"] == b.json()["id"]
    assert (await alice.get("/api/credits")).json()["balance"] == 9


async def test_input_validation(alice):
    assert (await create(alice, prompt="x" * 1001)).status_code == 422
    assert (await create(alice, prompt="ok\x00prompt")).status_code == 422
    assert (await create(alice, count=5)).status_code == 422
    assert (await create(alice, aspect_ratio="21:9")).status_code == 422
    assert (await create(alice, model="nope")).json()["detail"]["code"] == "unknown_model"
    assert (await create(alice, preset_id="nope")).json()["detail"]["code"] == "unknown_preset"


async def test_moderation_rejects_prompt(alice):
    r = await create(alice, prompt="nude photo of a teenager")
    assert r.status_code == 400 and r.json()["detail"]["code"] == "prompt_rejected"
    assert (await alice.get("/api/credits")).json()["balance"] == 10


async def test_key_required_provider_and_unsupported_ratio(alice):
    cf = {"provider": "cloudflare", "model": "@cf/black-forest-labs/flux-1-schnell"}
    r = await create(alice, **cf, aspect_ratio="16:9")
    assert r.json()["detail"]["code"] == "aspect_ratio_unsupported"
    r = await create(alice, **cf)
    assert r.json()["detail"]["code"] == "provider_key_required"


async def test_preset_is_applied_server_side(alice):
    job = (await create(alice, preset_id="halo-orbit", prompt="a ceramic teapot")).json()
    assert job["preset_id"] == "halo-orbit" and job["prompt"] == "a ceramic teapot"
    from app import db
    from app.models import Job

    async with db.session_factory()() as s:
        row = await s.get(Job, job["id"])
    assert row.params["final_prompt"].startswith("a ceramic teapot. Three-quarter angle")


async def test_sse_stream_reports_completion(alice):
    job = (await create(alice)).json()
    await run_once()
    r = await alice.get(f"/api/jobs/{job['id']}/events")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/event-stream")
    assert '"status": "done"' in r.text


async def test_favorites_and_delete(alice):
    job = (await create(alice)).json()
    await run_once()
    asset = (await alice.get(f"/api/jobs/{job['id']}")).json()["assets"][0]
    r = await alice.post(
        f"/api/assets/{asset['id']}/favorite", json={"favorite": True}, headers=csrf_headers(alice)
    )
    assert r.json()["is_favorite"] is True
    favs = (await alice.get("/api/jobs?favorites=true")).json()
    assert [j["id"] for j in favs] == [job["id"]]
    files = list(Path(get_settings().asset_dir).iterdir())
    assert len(files) == 1
    r = await alice.delete(f"/api/assets/{asset['id']}", headers=csrf_headers(alice))
    assert r.status_code == 204
    assert list(Path(get_settings().asset_dir).iterdir()) == []


async def test_timestamps_are_explicit_utc(alice):
    job = (await create(alice)).json()
    listed = (await alice.get("/api/jobs")).json()[0]
    for value in (job["created_at"], listed["created_at"]):
        assert value.endswith("Z") or value.endswith("+00:00"), value


async def test_history_pagination_with_utc_cursor(alice):
    for i in range(3):
        assert (await create(alice, prompt=f"page item {i}")).status_code == 201
    first = (await alice.get("/api/jobs", params={"limit": 2})).json()
    assert len(first) == 2
    rest = (
        await alice.get("/api/jobs", params={"limit": 2, "before": first[-1]["created_at"]})
    ).json()
    assert [j["prompt"] for j in rest] == ["page item 0"]


async def test_partial_result_refunds_only_missing_images(alice):
    job = (await create(alice, prompt="__partial__ please", count=2, seed=100)).json()
    await run_once()
    done = (await alice.get(f"/api/jobs/{job['id']}")).json()
    assert done["status"] == "done" and len(done["assets"]) == 1 and done["error"]
    assert (await alice.get("/api/credits")).json()["balance"] == 9


async def test_retryable_provider_error_is_retried_once(alice, monkeypatch):
    from app import worker
    from app.providers.base import ProviderError
    from app.providers.mock import MockProvider

    monkeypatch.setattr(worker, "RETRY_DELAY_SECONDS", 0)
    original = MockProvider.generate
    calls = {"n": 0}

    async def flaky(self, req, creds):
        calls["n"] += 1
        if calls["n"] == 1:
            raise ProviderError("busy", retryable=True)
        return await original(self, req, creds)

    monkeypatch.setattr(MockProvider, "generate", flaky)
    job = (await create(alice)).json()
    await run_once()
    done = (await alice.get(f"/api/jobs/{job['id']}")).json()
    assert done["status"] == "done" and calls["n"] == 2
