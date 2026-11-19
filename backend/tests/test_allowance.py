# SPDX-License-Identifier: AGPL-3.0-or-later
"""Free share of the owner's keys: 2 lifetime Modal clips per user, images split by user count."""

from app import db, worker
from app.config import get_settings
from app.models import Job
from app.providers import modal_video as mv
from app.providers.base import Credentials, ProviderError
from app.providers.cloudflare import CloudflareProvider
from app.providers.registry import get_provider
from app.services import allowance
from tests.conftest import csrf_headers, make_user

FLUX = "@cf/black-forest-labs/flux-1-schnell"


def _owner_modal():
    s = get_settings()
    s.modal_video_enabled = True
    s.modal_submit_url = "https://owner--aurevid-wan-submit.modal.run"
    s.modal_token_id = "wk-owner"
    s.modal_token_secret = "ws-owner"
    s.signup_credits = 100


async def _video(client):
    body = {
        "prompt": "waves on a calm beach",
        "provider": "modal_video",
        "model": mv.WAN,
        "aspect_ratio": "16:9",
    }
    return await client.post("/api/jobs", json=body, headers=csrf_headers(client))


async def test_two_free_modal_clips_then_own_key_needed():
    _owner_modal()
    client, _ = await make_user("v@example.com")
    providers = (await client.get("/api/providers")).json()
    modal = next(p for p in providers if p["id"] == "modal_video")
    assert modal["key_source"] == "server" and modal["free_left"] == 2
    assert (await _video(client)).status_code == 201
    assert (await _video(client)).status_code == 201
    r = await _video(client)
    assert r.status_code == 429 and r.json()["detail"]["code"] == "free_share_used"
    await client.aclose()


async def test_failed_free_clip_does_not_count():
    _owner_modal()
    client, _ = await make_user("f@example.com")
    job_id = (await _video(client)).json()["id"]
    async with db.session_factory()() as s:
        job = await s.get(Job, job_id)
        job.status = "failed"
        await s.commit()
        left = await allowance.server_left(s, get_provider("modal_video"), job.user_id)
    assert left == 2
    await client.aclose()


async def test_image_quota_is_split_by_user_count(monkeypatch):
    s = get_settings()
    s.cf_account_id, s.cf_api_token = "acc", "tok"
    info = CloudflareProvider.info.model_copy(update={"daily_quota_prior": 10})
    monkeypatch.setattr(CloudflareProvider, "info", info)
    clients = [(await make_user(f"u{i}@example.com"))[0] for i in range(3)]
    alice = clients[0]
    body = {"prompt": "a red apple", "provider": "cloudflare", "model": FLUX, "count": 3}
    r = await alice.post("/api/jobs", json=body, headers=csrf_headers(alice))
    assert r.status_code == 201, r.text  # 10 // 3 users = 3 per user per day
    body["count"] = 1
    r = await alice.post("/api/jobs", json=body, headers=csrf_headers(alice))
    assert r.status_code == 429 and r.json()["detail"]["code"] == "free_share_used"
    for c in clients:
        await c.aclose()


async def test_worker_falls_back_to_owner_key_when_user_key_fails(monkeypatch):
    _owner_modal()
    client, _ = await make_user("k@example.com")
    job_id = (await _video(client)).json()["id"]
    provider = get_provider("modal_video")
    async with db.session_factory()() as s:
        job = await s.get(Job, job_id)
        job.key_source = "user"
        await s.commit()
    user_key = Credentials({"submit_url": "u", "token_id": "a", "token_secret": "b"}, "user")
    got = await worker._server_fallback(provider, job, user_key, 1)
    assert got is not None and got.source == "server"
    async with db.session_factory()() as s:
        assert (await s.get(Job, job_id)).key_source == "server"
    # Allowance exhausted: no fallback, the user's error stands.
    get_settings().server_free_videos_per_user = 1
    assert (await _video(client)).status_code == 429
    assert await worker._server_fallback(provider, job, user_key, 2) is None
    assert ProviderError  # imported for readers: the worker re-raises the user's error
    await client.aclose()
