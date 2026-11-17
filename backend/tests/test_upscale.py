# SPDX-License-Identifier: AGPL-3.0-or-later
"""Local AI upscaling (Real-ESRGAN, ONNX/CPU), previews and the upscale endpoint."""

import io

import numpy as np
import pytest
from PIL import Image

from app import upscaler
from app.worker import run_once
from tests.conftest import csrf_headers


@pytest.fixture
def small_targets(monkeypatch):
    # Real 4K/8K takes seconds of CPU per image; tests use tiny "4K"/"8K" sizes, same code path.
    monkeypatch.setattr(upscaler, "TARGET_LONG_SIDE", {"4k": 512, "8k": 1280})


def _photo(w=96, h=64) -> Image.Image:
    yy, xx = np.mgrid[0:h, 0:w]
    arr = np.stack([(xx * 255 / w), (yy * 255 / h), ((xx + yy) % 32) * 8], axis=-1)
    return Image.fromarray(arr.astype(np.uint8), "RGB")


def test_model_file_present_and_real_x4():
    assert upscaler.available()
    out = upscaler.ai_x4(_photo(40, 24))
    assert out.size == (160, 96)


def test_tiling_matches_single_pass(monkeypatch):
    img = _photo(100, 70)
    monkeypatch.setattr(upscaler, "TILE", 1000)
    whole = np.asarray(upscaler.ai_x4(img), dtype=np.int16)
    monkeypatch.setattr(upscaler, "TILE", 32)
    tiled = np.asarray(upscaler.ai_x4(img), dtype=np.int16)
    assert np.abs(whole - tiled).mean() < 1.0  # seams hidden by tile padding


def test_upscale_targets_keep_aspect_and_handle_alpha(small_targets):
    img = _photo(96, 64)
    assert upscaler.upscale(img, "4k").size == (512, 341)
    eight = upscaler.upscale(img.convert("RGBA"), "8k")  # > 4x: Lanczos pre-step + AI 4x
    assert eight.size == (1280, 853) and eight.mode == "RGBA"
    big = _photo(600, 300)
    assert upscaler.upscale(big, "4k") is big  # never downscales


async def test_generate_with_upscale_and_preview(alice, small_targets):
    r = await alice.post(
        "/api/jobs",
        json={"provider": "demo", "model": "gradient", "prompt": "sharp", "upscale": "8k"},
        headers=csrf_headers(alice),
    )
    assert r.status_code == 201 and r.json()["cost"] == 4  # 1 + 3 for 8K
    await run_once()
    asset = (await alice.get(f"/api/jobs/{r.json()['id']}")).json()["assets"][0]
    assert (asset["width"], asset["height"]) == (1280, 1280)
    assert asset["preview_url"].endswith("/preview")
    full = Image.open(io.BytesIO((await alice.get(asset["url"])).content))
    preview = Image.open(io.BytesIO((await alice.get(asset["preview_url"])).content))
    assert full.size == (1280, 1280) and max(preview.size) == 1024


async def test_upscale_existing_image_endpoint(alice, bob, small_targets):
    job = (
        await alice.post(
            "/api/jobs",
            json={"provider": "demo", "model": "gradient", "prompt": "base", "size": "small"},
            headers=csrf_headers(alice),
        )
    ).json()
    await run_once()
    asset_id = (await alice.get(f"/api/jobs/{job['id']}")).json()["assets"][0]["id"]
    # Not yours -> 404, and bob pays nothing.
    r = await bob.post(
        f"/api/assets/{asset_id}/upscale", json={"target": "4k"}, headers=csrf_headers(bob)
    )
    assert r.status_code == 404
    r = await alice.post(
        f"/api/assets/{asset_id}/upscale", json={"target": "4k"}, headers=csrf_headers(alice)
    )
    assert r.status_code == 201, r.text
    up = r.json()
    assert up["provider"] == "local" and up["cost"] == 1
    await run_once()
    done = (await alice.get(f"/api/jobs/{up['id']}")).json()
    assert done["status"] == "done" and done["assets"][0]["width"] == 512


async def test_upscale_option_validated(alice):
    r = await alice.post(
        "/api/jobs",
        json={"provider": "demo", "model": "loop", "prompt": "clip", "upscale": "4k"},
        headers=csrf_headers(alice),
    )
    assert r.json()["detail"]["code"] == "upscale_unsupported"  # demo video has no upscaler


def test_work_is_bounded_whatever_the_input(small_targets, monkeypatch):
    seen = []
    real = upscaler.ai_x4
    monkeypatch.setattr(
        upscaler, "ai_x4", lambda img, deadline=None: seen.append(img.size) or real(img)
    )
    upscaler.upscale(_photo(900, 600), "8k")  # big source: network still gets final/4 only
    assert seen == [(320, 213)]


def test_deadline_stops_long_runs(monkeypatch):
    monkeypatch.setattr(upscaler, "TILE", 8)
    with pytest.raises(upscaler.UpscaleTimeout):
        upscaler.ai_x4(_photo(64, 64), deadline=0.0)


def test_video_upscale_on_by_default_and_switchable():
    from app.config import Settings, get_settings
    from app.providers.fal import FalProvider
    from app.providers.registry import allowed_upscales

    assert Settings.model_fields["fal_video_upscale_enabled"].default is True
    assert Settings.model_fields["fal_enabled"].default is True
    t2v = FalProvider().model("fal-ai/wan/v2.2-5b/text-to-video")
    assert allowed_upscales(t2v) == ["4k", "8k"]
    get_settings().fal_video_upscale_enabled = False
    assert allowed_upscales(t2v) == []
