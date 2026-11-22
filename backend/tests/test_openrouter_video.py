# SPDX-License-Identifier: AGPL-3.0-or-later
"""OpenRouter (Seedance) video adapter against a fake OpenRouter: no network, no real key."""

import json
import shutil
import subprocess
from pathlib import Path

import httpx
import pytest
from sqlalchemy import select

from app import db
from app.config import get_settings
from app.models import CreditLedger, Job
from app.providers import openrouter_video as orv
from app.providers.base import Credentials, GenerationRequest, ProviderError
from app.providers.registry import get_provider
from app.services import stitch
from app.worker import _generate_with_retry, run_once
from tests.conftest import csrf_headers, make_user

KEY = "sk-or-v1-" + "k" * 40
CREDS = Credentials({"api_key": KEY}, "user")
DEMO_MP4 = Path(__file__).resolve().parent.parent / "app" / "providers" / "media" / "demo.mp4"
MP4 = DEMO_MP4.read_bytes()


def _req(model=orv.MINI, resolution="480p", **kw):
    base = dict(
        prompt="a lantern on a quiet lake",
        model=model,
        aspect_ratio="16:9",
        width=854,
        height=480,
        seed=7,
        kind="video",
        duration_s=5,
        resolution=resolution,
    )
    return GenerationRequest(**{**base, **kw})


def _install(monkeypatch, handler):
    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(
        orv, "_http", lambda timeout: httpx.AsyncClient(transport=transport, timeout=timeout)
    )
    monkeypatch.setattr(orv, "POLL_SECONDS", 0)
    monkeypatch.setattr(orv, "SUBMIT_429_BACKOFF", 0)


def _openrouter(seen, *, final="completed", pending=1, cost=0.1421, error=None, submit=None):
    """A fake OpenRouter: submit -> `pending` polls in progress -> final status -> content."""
    state = {"polls": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        path = request.url.path
        if request.method == "POST":
            if submit is not None:
                return submit(request)
            return httpx.Response(
                202,
                json={
                    "id": "vid_1",
                    "generation_id": "g1",
                    "polling_url": "x",
                    "status": "pending",
                },
            )
        if path.endswith("/content"):
            return httpx.Response(200, content=MP4, headers={"content-type": "video/mp4"})
        state["polls"] += 1
        if state["polls"] <= pending:
            return httpx.Response(200, json={"id": "vid_1", "status": "in_progress"})
        body = {"id": "vid_1", "status": final, "unsigned_urls": ["https://x/y.mp4"]}
        if final == "completed":
            body["usage"] = {"cost": cost}
        if error:
            body["error"] = error
        return httpx.Response(200, json=body)

    return handler


async def test_submit_poll_download_with_the_key_only_to_openrouter(monkeypatch):
    seen = []
    _install(monkeypatch, _openrouter(seen))
    media = await orv.OpenRouterVideoProvider().generate(_req(), CREDS)
    assert media.data == MP4 and media.mime == "video/mp4"
    assert media.meta["usd_cost"] == pytest.approx(0.1421)
    post = seen[0]
    assert post.method == "POST" and post.url.path == "/api/v1/videos"
    body = json.loads(post.content)
    assert body == {
        "model": orv.MINI,
        "prompt": "a lantern on a quiet lake",
        "duration": 5,
        "resolution": "480p",
        "aspect_ratio": "16:9",
        "generate_audio": True,
        "seed": 7,
    }
    assert [r.url.path for r in seen[1:]] == [
        "/api/v1/videos/vid_1",
        "/api/v1/videos/vid_1",
        "/api/v1/videos/vid_1/content",
    ]
    # The key is sent on every call (the download needs it) and only to openrouter.ai.
    assert all(r.headers["authorization"] == f"Bearer {KEY}" for r in seen)
    assert {r.url.host for r in seen} == {"openrouter.ai"}


async def test_download_streams_to_disk_with_a_workdir(monkeypatch, tmp_path):
    _install(monkeypatch, _openrouter([]))
    media = await orv.OpenRouterVideoProvider().generate(_req(workdir=tmp_path), CREDS)
    assert media.path is not None and media.path.read_bytes() == MP4


async def test_start_image_becomes_the_first_frame(monkeypatch):
    seen = []
    _install(monkeypatch, _openrouter(seen, pending=0))
    await orv.OpenRouterVideoProvider().generate(_req(image=b"\xff\xd8jpeg"), CREDS)
    frames = json.loads(seen[0].content)["frame_images"]
    assert frames[0]["frame_type"] == "first_frame" and frames[0]["type"] == "image_url"
    assert frames[0]["image_url"]["url"].startswith("data:image/jpeg;base64,")


@pytest.mark.parametrize(
    "final,error,expect",
    [
        ("failed", "content policy", "OpenRouter video failed: content policy"),
        ("expired", None, "OpenRouter video expired"),
        ("cancelled", None, "OpenRouter video was cancelled"),
    ],
)
async def test_failed_expired_and_cancelled_are_clean_errors(monkeypatch, final, error, expect):
    seen = []
    _install(monkeypatch, _openrouter(seen, final=final, error=error))
    with pytest.raises(ProviderError) as exc:
        await orv.OpenRouterVideoProvider().generate(_req(), CREDS)
    assert exc.value.public == expect and not exc.value.retryable
    assert not any(r.url.path.endswith("/content") for r in seen)  # nothing to download


async def test_the_key_never_appears_in_an_error(monkeypatch):
    _install(monkeypatch, _openrouter([], final="failed", error=f"bad key {KEY} given"))
    with pytest.raises(ProviderError) as exc:
        await orv.OpenRouterVideoProvider().generate(_req(), CREDS)
    assert KEY not in exc.value.public and "***" in exc.value.public


async def test_402_means_no_credits_and_is_not_retried(monkeypatch):
    seen = []
    _install(monkeypatch, _openrouter(seen, submit=lambda r: httpx.Response(402, json={})))
    with pytest.raises(ProviderError) as exc:
        await orv.OpenRouterVideoProvider().generate(_req(), CREDS)
    assert "credits" in exc.value.public and not exc.value.retryable
    assert len(seen) == 1


async def test_429_is_retried_with_backoff_then_succeeds(monkeypatch):
    seen, tries = [], {"n": 0}

    def submit(request):
        tries["n"] += 1
        if tries["n"] < 3:
            return httpx.Response(429, json={})
        return httpx.Response(202, json={"id": "vid_1", "status": "pending"})

    sleeps = []

    async def fake_sleep(s):
        sleeps.append(s)

    _install(monkeypatch, _openrouter(seen, pending=0, submit=submit))
    monkeypatch.setattr(orv, "SUBMIT_429_BACKOFF", 2.0)
    monkeypatch.setattr(orv.asyncio, "sleep", fake_sleep)
    media = await orv.OpenRouterVideoProvider().generate(_req(), CREDS)
    assert media.data == MP4 and tries["n"] == 3
    assert sleeps[:2] == [2.0, 4.0]  # exponential backoff


async def test_429_every_time_gives_up_with_a_quota_error(monkeypatch):
    seen = []
    _install(monkeypatch, _openrouter(seen, submit=lambda r: httpx.Response(429, json={})))
    with pytest.raises(ProviderError) as exc:
        await orv.OpenRouterVideoProvider().generate(_req(), CREDS)
    assert exc.value.quota and len(seen) == orv.SUBMIT_429_RETRIES + 1


@pytest.mark.parametrize("failure", ["timeout", "5xx"])
async def test_ambiguous_submit_is_never_retried(monkeypatch, failure):
    seen = []

    def submit(request):
        if failure == "timeout":
            raise httpx.ReadTimeout("slow", request=request)
        return httpx.Response(502, json={})

    _install(monkeypatch, _openrouter(seen, submit=submit))
    with pytest.raises(ProviderError) as exc:
        await orv.OpenRouterVideoProvider().generate(_req(), CREDS)
    assert exc.value.retryable is False and "billed" in exc.value.public
    # Even through the worker's retry wrapper: the job is submitted exactly once.
    posts = []
    _install(monkeypatch, _openrouter(posts, submit=submit))
    with pytest.raises(ProviderError):
        await _generate_with_retry(orv.OpenRouterVideoProvider(), _req(), CREDS)
    assert [r.method for r in posts] == ["POST"]


async def test_poll_giving_up_is_not_retryable(monkeypatch):
    # Still running when time is up: the clip may yet be made and billed, so no second submit.
    _install(monkeypatch, _openrouter([], pending=10**6))
    monkeypatch.setattr(get_settings(), "video_timeout_seconds", 0)
    monkeypatch.setattr(orv, "DEADLINE_MARGIN", 0)
    monkeypatch.setattr(orv.time, "monotonic", iter(range(0, 10**6, 100)).__next__)
    with pytest.raises(ProviderError) as exc:
        await orv.OpenRouterVideoProvider().generate(_req(), CREDS)
    assert "too long" in exc.value.public and not exc.value.retryable


async def test_transient_poll_errors_are_tolerated(monkeypatch):
    state = {"n": 0}
    seen = []
    base = _openrouter(seen, pending=0)

    def handler(request):
        if request.method == "GET" and not request.url.path.endswith("/content"):
            state["n"] += 1
            if state["n"] <= 3:
                return httpx.Response(503, json={})
        return base(request)

    _install(monkeypatch, handler)
    media = await orv.OpenRouterVideoProvider().generate(_req(), CREDS)
    assert media.data == MP4


async def test_download_is_fetched_again_when_it_hiccups(monkeypatch):
    state = {"n": 0}
    base = _openrouter([], pending=0)

    def handler(request):
        if request.url.path.endswith("/content"):
            state["n"] += 1
            if state["n"] == 1:
                return httpx.Response(503)
        return base(request)

    _install(monkeypatch, handler)
    assert (await orv.OpenRouterVideoProvider().generate(_req(), CREDS)).data == MP4
    assert state["n"] == 2


async def test_a_missing_key_is_refused_before_any_request(monkeypatch):
    seen = []
    _install(monkeypatch, _openrouter(seen))
    with pytest.raises(ProviderError):
        await orv.OpenRouterVideoProvider().generate(_req(), Credentials())
    assert seen == []


# --- cost estimate ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "model,res,seconds,cents",
    [  # the owner's figures (per 5 s, 16:9, 7% margin included), 2026-11-22
        (orv.MINI, "480p", 5, 18),
        (orv.MINI, "720p", 5, 40),
        (orv.FLASH, "480p", 5, 36),
        (orv.FLASH, "720p", 5, 81),
        (orv.PRO, "720p", 5, 124),
        (orv.PRO, "1080p", 5, 304),
        (orv.MINI, "480p", 4, 14),
        (orv.PRO, "1080p", 4, 243),
    ],
)
def test_estimate_matches_the_published_prices_plus_margin(model, res, seconds, cents):
    usd = orv.estimate_usd(model, res, "16:9", seconds)
    assert round(usd * 100) == cents


def test_estimate_unknown_combinations_are_none():
    assert orv.estimate_usd(orv.MINI, "1080p", "16:9", 5) is None
    assert orv.estimate_usd("nope", "480p", "16:9", 5) is None


# --- through the API: keys, credits, resolution, refunds ----------------------------------------


async def _key(client, provider="openrouter_video"):
    r = await client.put(
        f"/api/me/keys/{provider}", json={"values": {"api_key": KEY}}, headers=csrf_headers(client)
    )
    assert r.status_code == 200, r.text


async def _job(client, **kw):
    body = {
        "prompt": "a lantern on a quiet lake",
        "provider": "openrouter_video",
        "model": orv.MINI,
        "aspect_ratio": "16:9",
        "duration": 5,
        **kw,
    }
    return await client.post("/api/jobs", json=body, headers=csrf_headers(client))


async def test_models_are_offered_and_priced_in_the_catalog(alice):
    providers = (await alice.get("/api/providers")).json()
    p = next(x for x in providers if x["id"] == "openrouter_video")
    assert p["byok"] and p["key_source"] == "none" and p["available"] is False
    pro = next(m for m in p["models"] if m["id"] == orv.PRO)
    assert pro["commercial_use"] == "yes" and pro["resolutions"] == ["480p", "720p", "1080p"]
    assert pro["default_resolution"] == "720p"  # 1080p is never the silent default
    assert round(pro["usd_per_second"]["1080p"]["16:9"] * 5, 2) == 3.04
    assert pro["resolution_sizes"]["1080p"]["16:9"] == [1920, 1080]


async def test_without_a_key_nothing_runs(alice):
    r = await _job(alice)
    assert r.status_code == 400 and r.json()["detail"]["code"] == "provider_key_required"


async def _rich_user(email="rich@example.com"):
    get_settings().signup_credits = 100
    client, _ = await make_user(email)
    await _key(client)
    return client


async def test_job_records_resolution_estimate_and_charges_credits():
    alice = await _rich_user()
    r = await _job(alice, model=orv.PRO, resolution="1080p")
    assert r.status_code == 201, r.text
    job = r.json()
    assert job["cost"] == 10 + 12
    p = job["params"]
    assert p["resolution"] == "1080p" and (p["width"], p["height"]) == (1920, 1080)
    assert p["estimated_usd"] == pytest.approx(3.04, abs=0.01)
    assert job["has_audio"] is True


async def test_default_resolution_is_the_cheap_standard_one():
    alice = await _rich_user()
    job = (await _job(alice, model=orv.PRO)).json()
    assert job["params"]["resolution"] == "720p" and job["cost"] == 10 + 4
    mini = (await _job(alice)).json()  # Standard: Mini 720p
    assert mini["params"]["resolution"] == "720p"
    assert mini["params"]["estimated_usd"] == pytest.approx(0.4, abs=0.01)


async def test_unsupported_resolution_is_refused(alice):
    await _key(alice)
    r = await _job(alice, model=orv.MINI, resolution="1080p")
    assert r.status_code == 400 and r.json()["detail"]["code"] == "resolution_unsupported"
    r = await _job(alice, provider="demo", model="loop", resolution="720p", duration=3)
    assert r.json()["detail"]["code"] == "resolution_unsupported"


async def test_successful_job_stores_the_real_size_and_the_billed_cost(alice, monkeypatch):
    await _key(alice)
    seen = []
    _install(monkeypatch, _openrouter(seen, pending=0, cost=0.1421))
    job = (await _job(alice, resolution="480p")).json()
    await run_once()
    done = (await alice.get(f"/api/jobs/{job['id']}")).json()
    assert done["status"] == "done"
    asset = done["assets"][0]
    # The demo clip stands in for the provider file: its own size (320x320), not the label's.
    assert (asset["width"], asset["height"]) == (320, 320)
    assert (done["params"]["width"], done["params"]["height"]) == (320, 320)
    assert done["params"]["usd_cost"] == pytest.approx(0.1421)
    assert done["params"]["resolution"] == "480p"


async def test_failed_job_refunds_credits_exactly_once(alice, monkeypatch):
    await _key(alice)
    _install(monkeypatch, _openrouter([], final="failed", error="no"))
    job = (await _job(alice, resolution="480p")).json()
    assert job["cost"] == 3
    await run_once()
    await run_once()  # nothing left to run; a second pass must not refund again
    done = (await alice.get(f"/api/jobs/{job['id']}")).json()
    assert done["status"] == "failed" and "OpenRouter video failed" in done["error"]
    async with db.session_factory()() as s:
        rows = (
            (await s.execute(select(CreditLedger).where(CreditLedger.job_id == job["id"])))
            .scalars()
            .all()
        )
    assert sorted(r.delta for r in rows) == [-3, 3]
    assert (await alice.get("/api/me")).json()["credit_balance"] == 10


async def test_insufficient_credits_402_fails_clearly_and_refunds(alice, monkeypatch):
    await _key(alice)
    _install(monkeypatch, _openrouter([], submit=lambda r: httpx.Response(402, json={})))
    job = (await _job(alice, resolution="480p")).json()
    await run_once()
    done = (await alice.get(f"/api/jobs/{job['id']}")).json()
    assert done["status"] == "failed" and "credits are used up" in done["error"]
    assert (await alice.get("/api/me")).json()["credit_balance"] == 10


async def test_ambiguous_submit_through_the_worker_posts_once(alice, monkeypatch):
    await _key(alice)
    posts = []

    def submit(request):
        raise httpx.ConnectTimeout("lost", request=request)

    _install(monkeypatch, _openrouter(posts, submit=submit))
    job = (await _job(alice, resolution="480p")).json()
    await run_once()
    done = (await alice.get(f"/api/jobs/{job['id']}")).json()
    assert done["status"] == "failed" and "billed" in done["error"]
    assert len(posts) == 1


# --- the owner's key is optional, off by default, and only buys drafts ----------------------------


async def test_owner_key_is_off_by_default_and_never_used_for_free_users(alice):
    s = get_settings()
    s.openrouter_api_key = "sk-or-owner-" + "o" * 30
    # No allowance configured (0 clips per user): the owner's key is not usable at all.
    p = get_provider("openrouter_video")
    assert p.has_usable_credentials(p.server_credentials()) is False
    r = await _job(alice, resolution="480p")
    assert r.status_code == 400 and r.json()["detail"]["code"] == "provider_key_required"


async def test_owner_key_allowance_is_480p_mini_only_and_counted(alice):
    s = get_settings()
    s.openrouter_api_key = "sk-or-owner-" + "o" * 30
    s.openrouter_free_clips_per_user = 1
    s.openrouter_monthly_cap = 5
    r = await _job(alice, model=orv.PRO, resolution="480p")
    assert r.json()["detail"]["code"] == "server_key_draft_only"
    r = await _job(alice, resolution="720p")
    assert r.json()["detail"]["code"] == "server_key_draft_only"
    assert (await _job(alice, resolution="480p")).status_code == 201
    r = await _job(alice, resolution="480p")
    assert r.status_code == 429 and r.json()["detail"]["code"] == "free_share_used"


# --- multi-scene stories with the new models ------------------------------------------------------


async def test_story_scenes_carry_the_resolution_and_are_charged_each(alice):
    await _key(alice)
    body = {
        "provider": "openrouter_video",
        "model": orv.MINI,
        "aspect_ratio": "16:9",
        "resolution": "480p",
        "scenes": ["a lantern at dawn", "the lantern at dusk"],
    }
    s = get_settings()
    s.max_active_jobs_per_user = 4
    r = await alice.post("/api/stories", json=body, headers=csrf_headers(alice))
    assert r.status_code == 201, r.text
    story = r.json()
    assert story["cost"] == 6
    assert [sc["job"]["params"]["resolution"] for sc in story["scenes"]] == ["480p", "480p"]
    assert all(sc["job"]["params"]["duration"] == 5 for sc in story["scenes"])
    async with db.session_factory()() as s2:
        assert len((await s2.execute(select(Job))).scalars().all()) == 2


HAVE_FFMPEG = stitch.available()
needs_ffmpeg = pytest.mark.skipif(not HAVE_FFMPEG, reason="ffmpeg/ffprobe not installed")


def _clip(path: Path, size: str) -> None:
    ffmpeg = shutil.which("ffmpeg")
    cmd = [
        ffmpeg, "-v", "error", "-y", "-f", "lavfi", "-i", f"testsrc=s={size}:d=1:r=24",
        "-pix_fmt", "yuv420p", "-c:v", "libx264", str(path),
    ]  # fmt: skip
    subprocess.run(cmd, check=True)  # noqa: S603


@needs_ffmpeg
@pytest.mark.parametrize(
    "sizes,joined", [(("1280x720", "1280x720"), (1280, 720)), (("854x480", "1280x720"), (854, 480))]
)
async def test_stitching_is_resolution_aware(tmp_path, sizes, joined):
    clips = []
    for i, size in enumerate(sizes):
        clips.append(tmp_path / f"c{i}.mp4")
        _clip(clips[-1], size)
    info = await stitch.concat_clips(clips, tmp_path / "out.mp4")
    # Same layout: lossless copy. Different sizes: re-encode to the first clip's size.
    assert (info.width, info.height) == joined
