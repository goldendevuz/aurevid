# SPDX-License-Identifier: AGPL-3.0-or-later
"""Bring-your-own-GPU: provider gating, bearer auth, claim/complete/fail, lease expiry."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest

from app import db
from app.config import Settings, get_settings
from app.models import Job, JobStatus
from app.providers.registry import enabled_providers
from app.worker import requeue_expired_leases, run_once
from tests.conftest import _client, csrf_headers

DEMO_MP4 = Path(__file__).resolve().parent.parent / "app" / "providers" / "media" / "demo.mp4"
TOKEN = "gpu-test-token-" + "x" * 32
BASE = "/api/gpu-worker"


@pytest.fixture(autouse=True)
def token_on():
    get_settings().gpu_worker_token = TOKEN


@pytest.fixture
async def gpu():
    """The remote worker: no cookies, only the bearer token."""
    async with _client() as c:
        c.headers["Authorization"] = f"Bearer {TOKEN}"
        yield c


async def _create(client, **overrides):
    body = {
        "provider": "gpu_worker",
        "model": "wan-2.2-ti2v-5b",
        "prompt": "amber lantern flickering",
        "aspect_ratio": "16:9",
        **overrides,
    }
    return await client.post("/api/jobs", json=body, headers=csrf_headers(client))


async def _job(job_id: str) -> Job:
    async with db.session_factory()() as s:
        return await s.get(Job, job_id)


async def _balance(client) -> int:
    return (await client.get("/api/credits")).json()["balance"]


async def test_hidden_and_inert_when_token_unset(alice, anon):
    get_settings().gpu_worker_token = ""
    assert "gpu_worker" not in enabled_providers()
    ids = [p["id"] for p in (await alice.get("/api/providers")).json()]
    assert "gpu_worker" not in ids
    assert (await _create(alice)).status_code == 400  # unknown_model
    r = await anon.post(f"{BASE}/claim", headers={"Authorization": f"Bearer {TOKEN}"})
    assert r.status_code == 404


async def test_listed_as_free_video_when_token_set(alice):
    providers = {p["id"]: p for p in (await alice.get("/api/providers")).json()}
    p = providers["gpu_worker"]
    assert p["tier"] == "free" and p["available"] is True
    (m,) = p["models"]
    assert m["credit_cost"] == 0 and m["kind"] == "video" and m["has_audio"] is False


@pytest.mark.parametrize("auth", [None, "Bearer wrong", "Basic " + TOKEN, "Bearer", TOKEN])
async def test_auth_required(anon, auth):
    headers = {"Authorization": auth} if auth else {}
    for method, path in [
        ("POST", f"{BASE}/claim"),
        ("GET", f"{BASE}/abc/image"),
        ("POST", f"{BASE}/abc/fail"),
    ]:
        r = await anon.request(method, path, headers=headers, json={} if method == "POST" else None)
        assert r.status_code == 401, (method, path, auth)


async def test_failed_auth_is_rate_limited(anon):
    codes = [
        (await anon.post(f"{BASE}/claim", headers={"Authorization": "Bearer nope"})).status_code
        for _ in range(12)
    ]
    assert codes[:10] == [401] * 10 and 429 in codes[10:]


async def test_claim_complete_happy_path_costs_nothing(alice, gpu):
    start = await _balance(alice)
    job = (await _create(alice, aspect_ratio="9:16", duration=3, seed=7)).json()
    assert job["cost"] == 0 and await _balance(alice) == start

    assert await run_once() is False  # the server worker never takes remote jobs
    assert (await _job(job["id"])).status == JobStatus.queued

    r = await gpu.post(f"{BASE}/claim")  # no CSRF cookie or header needed
    assert r.status_code == 200, r.text
    c = r.json()
    assert c["job_id"] == job["id"] and c["prompt"] == "amber lantern flickering"
    assert (c["width"], c["height"], c["frames"], c["seed"]) == (480, 832, 73, 7)
    assert c["image_url"] is None and c["lease_until"]
    assert (await _job(job["id"])).status == JobStatus.running
    assert (await gpu.post(f"{BASE}/claim")).status_code == 204  # nothing else queued

    up = await gpu.post(
        f"{BASE}/{job['id']}/complete",
        files={"file": ("out.mp4", DEMO_MP4.read_bytes(), "video/mp4")},
    )
    assert up.status_code == 201, up.text
    done = (await alice.get(f"/api/jobs/{job['id']}")).json()
    assert done["status"] == "done" and done["assets"][0]["mime"] == "video/mp4"
    f = await alice.get(done["assets"][0]["url"])
    assert f.status_code == 200 and f.content == DEMO_MP4.read_bytes()
    assert await _balance(alice) == start

    again = await gpu.post(
        f"{BASE}/{job['id']}/complete", files={"file": ("o.mp4", DEMO_MP4.read_bytes())}
    )
    assert again.status_code == 409  # no double completion


async def test_claim_serves_oldest_first(alice, bob, gpu):
    first = (await _create(alice)).json()
    second = (await _create(bob)).json()
    assert (await gpu.post(f"{BASE}/claim")).json()["job_id"] == first["id"]
    assert (await gpu.post(f"{BASE}/claim")).json()["job_id"] == second["id"]


async def test_invalid_video_is_rejected_and_job_stays_leased(alice, gpu):
    job = (await _create(alice)).json()
    await gpu.post(f"{BASE}/claim")
    r = await gpu.post(
        f"{BASE}/{job['id']}/complete", files={"file": ("x.mp4", b"not a video at all, sorry")}
    )
    assert r.status_code == 415
    assert (await _job(job["id"])).status == JobStatus.running


async def test_complete_needs_a_claimed_gpu_job(alice, gpu):
    queued = (await _create(alice)).json()
    files = {"file": ("o.mp4", DEMO_MP4.read_bytes())}
    assert (await gpu.post(f"{BASE}/{queued['id']}/complete", files=files)).status_code == 409
    assert (await gpu.post(f"{BASE}/nope/complete", files=files)).status_code == 404
    other = (
        await alice.post(
            "/api/jobs",
            json={"provider": "demo", "model": "loop", "prompt": "lantern"},
            headers=csrf_headers(alice),
        )
    ).json()
    assert (await gpu.post(f"{BASE}/{other['id']}/fail", json={})).status_code == 404


async def test_start_image_served_only_while_leased(alice, gpu):
    img = (
        await alice.post(
            "/api/jobs",
            json={"provider": "demo", "model": "gradient", "prompt": "still frame"},
            headers=csrf_headers(alice),
        )
    ).json()
    await run_once()
    asset_id = (await alice.get(f"/api/jobs/{img['id']}")).json()["assets"][0]["id"]
    job = (await _create(alice, image_asset_id=asset_id)).json()
    assert (await gpu.get(f"{BASE}/{job['id']}/image")).status_code == 409  # not claimed yet
    claim = (await gpu.post(f"{BASE}/claim")).json()
    assert claim["image_url"] == f"{BASE}/{job['id']}/image"
    r = await gpu.get(claim["image_url"])
    assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg"
    assert r.content[:2] == b"\xff\xd8"


async def test_fail_refunds_through_the_normal_path_and_hides_worker_text(alice, gpu):
    job = (await _create(alice)).json()
    await gpu.post(f"{BASE}/claim")
    r = await gpu.post(f"{BASE}/{job['id']}/fail", json={"message": "CUDA OOM at /secret/path"})
    assert r.status_code == 200
    out = (await alice.get(f"/api/jobs/{job['id']}")).json()
    assert out["status"] == "failed" and "secret" not in (out["error"] or "")
    assert (await gpu.post(f"{BASE}/{job['id']}/fail", json={})).status_code == 409


async def _age_lease(job_id: str, seconds: int) -> None:
    async with db.session_factory()() as s:
        job = await s.get(Job, job_id)
        job.started_at = datetime.now(UTC) - timedelta(seconds=seconds)
        await s.commit()


async def test_expired_lease_returns_job_to_queue(alice, gpu):
    job = (await _create(alice)).json()
    await gpu.post(f"{BASE}/claim")
    assert await requeue_expired_leases() == 0  # lease still valid
    await _age_lease(job["id"], get_settings().gpu_worker_lease_seconds + 5)
    assert await requeue_expired_leases() == 1
    row = await _job(job["id"])
    assert row.status == JobStatus.queued and row.started_at is None
    r = await gpu.post(f"{BASE}/claim")  # claimable again
    assert r.json()["job_id"] == job["id"] and (await _job(job["id"])).attempts == 2


async def test_late_upload_after_requeue_is_refused(alice, gpu):
    job = (await _create(alice)).json()
    await gpu.post(f"{BASE}/claim")
    await _age_lease(job["id"], get_settings().gpu_worker_lease_seconds + 5)
    await requeue_expired_leases()
    r = await gpu.post(
        f"{BASE}/{job['id']}/complete", files={"file": ("o.mp4", DEMO_MP4.read_bytes())}
    )
    assert r.status_code == 409


async def test_claim_reaps_expired_leases_itself(alice, gpu):
    job = (await _create(alice)).json()
    await gpu.post(f"{BASE}/claim")
    await _age_lease(job["id"], get_settings().gpu_worker_lease_seconds + 5)
    r = await gpu.post(f"{BASE}/claim")  # a restarted worker gets its own job back
    assert r.status_code == 200 and r.json()["job_id"] == job["id"]


async def test_job_that_keeps_expiring_fails_after_max_attempts(alice, gpu):
    job = (await _create(alice)).json()
    for _ in range(get_settings().gpu_worker_max_attempts):
        assert (await gpu.post(f"{BASE}/claim")).status_code == 200
        await _age_lease(job["id"], get_settings().gpu_worker_lease_seconds + 5)
        await requeue_expired_leases()
    row = await _job(job["id"])
    assert row.status == JobStatus.failed and "credits refunded" in row.error
    assert (await gpu.post(f"{BASE}/claim")).status_code == 204


async def test_gpu_jobs_still_count_against_daily_limit(alice):
    get_settings().daily_job_limit = 1
    assert (await _create(alice)).status_code == 201
    r = await _create(alice)
    assert r.status_code == 429 and r.json()["detail"]["code"] == "daily_limit_reached"


async def test_commercial_rule_still_holds_with_gpu_worker_on():
    s = get_settings()
    s.fal_enabled = True
    providers = enabled_providers()
    assert "gpu_worker" in providers
    for p in providers.values():
        assert all(m.commercial_use == "yes" for m in p.info.models), p.info.id
    model = providers["gpu_worker"].info.models[0]
    assert model.license == "Apache-2.0" and not model.has_audio
    assert (
        "gpu_worker"
        in Path(__file__).resolve().parents[2].joinpath("MODEL_LICENSES.md").read_text()
    )


def test_prod_requires_a_long_token():
    base = dict(
        app_env="prod",
        jwt_secret="x" * 40,
        byok_encryption_key="k",
        cookie_secure=True,
        mock_provider_enabled=False,
    )
    with pytest.raises(ValueError, match="GPU_WORKER_TOKEN"):
        Settings(**base, gpu_worker_token="short")
    Settings(**base, gpu_worker_token="t" * 32)
    Settings(**base)  # off is fine


async def test_wrong_http_client_cookie_user_cannot_use_worker_api(alice):
    r = await alice.post(f"{BASE}/claim", headers=csrf_headers(alice))
    assert r.status_code == 401  # a logged-in user is not a worker
    assert isinstance(alice, httpx.AsyncClient)
