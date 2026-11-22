# SPDX-License-Identifier: AGPL-3.0-or-later
"""Image "Publish quality": best free commercial model at its largest size, then local upscale."""

import io

import numpy as np
import pytest
from PIL import Image
from sqlalchemy import select

from app import db, upscaler
from app.config import get_settings
from app.models import CreditLedger, Job
from app.providers.cloudflare import KLEIN, SCHNELL, CloudflareProvider
from app.providers.registry import publish_image_model
from app.services import queue
from app.worker import run_once
from tests.conftest import csrf_headers, make_user

PUBLISH = {"provider": "demo", "model": "gradient-hd", "quality": "publish"}


@pytest.fixture(autouse=True)
def only_the_demo_model():
    get_settings().cloudflare_enabled = False  # restored by the conftest fixture


@pytest.fixture
def tiny_targets(monkeypatch):
    # Real 2K/4K costs seconds of CPU per image; tests use tiny sizes through the same code path.
    monkeypatch.setattr(upscaler, "TARGET_LONG_SIDE", {"2k": 640, "4k": 960, "8k": 1280})
    monkeypatch.setattr(upscaler, "PUBLISH_NET_LONG", {"2k": 96, "4k": 128})


async def _post(client, **kw):
    body = {"prompt": "a lantern on a quiet lake", "aspect_ratio": "1:1", **PUBLISH, **kw}
    return await client.post("/api/jobs", json=body, headers=csrf_headers(client))


def test_the_publish_model_is_the_best_free_commercial_one():
    chosen = publish_image_model()
    assert chosen is not None and chosen[1].id == "gradient-hd"
    assert chosen[1].commercial_use == "yes" and chosen[0].info.tier == "free"
    assert chosen[1].publish_max_side == 1920


def test_with_cloudflare_on_it_is_flux2_klein_not_schnell():
    get_settings().cloudflare_enabled = True
    provider, model = publish_image_model()
    assert provider.info.id == "cloudflare" and model.id == KLEIN
    # schnell (4 steps, soft) and any paid or unclear model are never the publish model.
    assert model.id != SCHNELL and model.commercial_use == "yes" and provider.info.tier == "free"


async def test_catalog_marks_exactly_one_publish_model(alice):
    models = [m for p in (await alice.get("/api/providers")).json() for m in p["models"]]
    assert [m["id"] for m in models if m.get("publish_quality")] == ["gradient-hd"]


async def test_job_asks_for_the_largest_size_and_expects_the_upscaled_one(alice):
    r = await _post(alice, aspect_ratio="16:9")
    assert r.status_code == 201, r.text
    job = r.json()
    p = job["params"]
    assert p["quality"] == "publish" and p["upscale"] == "2k"  # 2K unless 4K is chosen
    assert (p["gen_width"], p["gen_height"]) == (1920, 1088)
    assert (p["width"], p["height"]) == (2560, 1451)  # what the finished file will be
    assert job["cost"] == 1 + 1  # model + 2K upscale
    assert (await _post(alice, upscale="4k")).json()["cost"] == 2


async def test_publish_is_a_cpu_job_so_the_cpu_cap_applies(alice):
    job = (await _post(alice)).json()
    async with db.session_factory()() as s:
        row = await s.get(Job, job["id"])
    assert queue.resource_class(row) == queue.CPU


@pytest.mark.parametrize(
    "extra,code",
    [
        ({"count": 2}, "count_too_high"),
        ({"upscale": "8k"}, "upscale_unsupported"),
        ({"model": "gradient"}, "quality_unsupported"),  # not the publish model
        ({"model": "loop", "duration": 3}, "quality_unsupported"),
    ],
)
async def test_publish_rules(alice, extra, code):
    r = await _post(alice, **extra)
    assert r.status_code == 400 and r.json()["detail"]["code"] == code


async def test_publish_quality_cannot_be_used_on_an_edit(alice):
    plain = (
        await alice.post(
            "/api/jobs",
            json={"provider": "demo", "model": "gradient", "prompt": "still frame"},
            headers=csrf_headers(alice),
        )
    ).json()
    await run_once()
    asset_id = (await alice.get(f"/api/jobs/{plain['id']}")).json()["assets"][0]["id"]
    r = await _post(alice, image_asset_id=asset_id)
    assert r.json()["detail"]["code"] == "quality_unsupported"


async def test_end_to_end_the_delivered_asset_is_the_upscaled_one(alice, tiny_targets):
    job = (await _post(alice, aspect_ratio="16:9")).json()
    await run_once()
    done = (await alice.get(f"/api/jobs/{job['id']}")).json()
    assert done["status"] == "done" and len(done["assets"]) == 1  # the original is not kept
    asset = done["assets"][0]
    # The demo model draws a quarter-size 480x272 picture; "2K" is 640 px wide in this test.
    assert (asset["width"], asset["height"]) == (640, 363)
    assert (done["params"]["width"], done["params"]["height"]) == (640, 363)
    img = Image.open(io.BytesIO((await alice.get(asset["url"])).content))
    assert img.size == (640, 363)


async def test_publish_hands_the_network_the_real_render_not_a_shrunken_copy(monkeypatch):
    seen = []
    real = upscaler.ai_x4
    monkeypatch.setattr(
        upscaler, "ai_x4", lambda img, deadline=None: seen.append(img.size) or real(img, deadline)
    )
    monkeypatch.setattr(upscaler, "TARGET_LONG_SIDE", {"2k": 640, "4k": 960})
    src = Image.fromarray(np.random.default_rng(1).integers(0, 255, (60, 80, 3), dtype=np.uint8))
    upscaler.upscale(
        src, "2k"
    )  # classic rule: net input = target/4 = 160 -> upscales the source first
    upscaler.upscale(src, "2k", net_long=1280)  # publish: the source itself (80x60), never blown up
    upscaler.upscale(src, "2k", net_long=40)  # capped: shrunk to the bound
    assert seen == [(160, 120), (80, 60), (40, 30)]


async def test_upscale_timeout_fails_the_job_and_refunds_once(alice, monkeypatch):
    def too_slow(*args, **kwargs):
        raise upscaler.UpscaleTimeout("upscaling took too long")

    monkeypatch.setattr(upscaler, "upscale", too_slow)
    job = (await _post(alice)).json()
    await run_once()
    done = (await alice.get(f"/api/jobs/{job['id']}")).json()
    assert done["status"] == "failed"
    async with db.session_factory()() as s:
        rows = (
            (await s.execute(select(CreditLedger).where(CreditLedger.job_id == job["id"])))
            .scalars()
            .all()
        )
    assert sorted(r.delta for r in rows) == [-2, 2]


async def test_upscaler_disabled_means_no_publish_upscale(alice):
    get_settings().upscaler_enabled = False
    r = await _post(alice, upscale="4k")
    assert r.status_code == 400 and r.json()["detail"]["code"] == "upscale_unsupported"


async def test_2k_is_offered_for_every_image_and_priced(alice):
    r = await alice.post(
        "/api/jobs",
        json={"provider": "demo", "model": "gradient", "prompt": "sharp", "upscale": "2k"},
        headers=csrf_headers(alice),
    )
    assert r.status_code == 201 and r.json()["cost"] == 2


# --- no free-share loophole: a big klein image uses several outputs of the free share ------


def test_klein_neuron_weight_grows_with_pixels():
    p = CloudflareProvider()
    assert p.quota_weight(KLEIN, 1024, 1024) == 1  # what the free share was sized for
    assert p.quota_weight(KLEIN, 512, 512) == 1
    assert p.quota_weight(KLEIN, 1920, 1088) == 2
    assert p.quota_weight(KLEIN, 1920, 1920) == 3
    assert p.quota_weight(SCHNELL, 1024, 1024) == 1


async def test_publish_counts_several_times_against_the_free_share(monkeypatch):
    s = get_settings()
    s.cloudflare_enabled = True
    s.cf_account_id, s.cf_api_token = "a" * 32, "tok"
    s.signup_credits = 50
    info = CloudflareProvider.info.model_copy(update={"daily_quota_prior": 12})
    monkeypatch.setattr(CloudflareProvider, "info", info)
    clients = [(await make_user(f"w{i}@example.com"))[0] for i in range(3)]
    alice = clients[0]  # 12 outputs // 3 users = 4 per user per day
    body = {"provider": "cloudflare", "model": KLEIN, "quality": "publish", "prompt": "a lantern"}
    r = await alice.post("/api/jobs", json=body, headers=csrf_headers(alice))
    assert r.status_code == 201, r.text
    assert r.json()["params"]["quota_weight"] == 3  # 1920x1920 klein
    r = await alice.post("/api/jobs", json=body, headers=csrf_headers(alice))
    assert r.status_code == 429 and r.json()["detail"]["code"] == "free_share_used"  # 3 + 3 > 4
    plain = {"provider": "cloudflare", "model": KLEIN, "prompt": "a lantern", "size": "medium"}
    assert (
        await alice.post("/api/jobs", json=plain, headers=csrf_headers(alice))
    ).status_code == 201
    r = await alice.post("/api/jobs", json=plain, headers=csrf_headers(alice))
    assert r.status_code == 429  # 3 + 1 used the whole share of 4
    for c in clients:
        await c.aclose()
