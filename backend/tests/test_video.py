# SPDX-License-Identifier: AGPL-3.0-or-later
from pathlib import Path

import pytest

from app import db
from app.images import InvalidImageError, validate_mp4
from app.models import Job
from app.worker import run_once
from tests.conftest import csrf_headers

DEMO_MP4 = Path(__file__).resolve().parent.parent / "app" / "providers" / "media" / "demo.mp4"
VIDEO = {"provider": "demo", "model": "loop"}


async def _create(client, **overrides):
    body = {**VIDEO, "prompt": "amber lantern flickering", **overrides}
    return await client.post("/api/jobs", json=body, headers=csrf_headers(client))


async def _image_asset(client) -> str:
    job = (
        await client.post(
            "/api/jobs",
            json={"provider": "demo", "model": "gradient", "prompt": "still frame"},
            headers=csrf_headers(client),
        )
    ).json()
    await run_once()
    return (await client.get(f"/api/jobs/{job['id']}")).json()["assets"][0]["id"]


async def test_text_to_video_produces_playable_mp4(alice):
    r = await _create(alice, aspect_ratio="16:9")
    assert r.status_code == 201, r.text
    job = r.json()
    assert job["kind"] == "video" and job["cost"] == 2 and job["params"]["duration"] == 3
    await run_once()
    done = (await alice.get(f"/api/jobs/{job['id']}")).json()
    assert done["status"] == "done"
    asset = done["assets"][0]
    assert asset["mime"] == "video/mp4"
    f = await alice.get(asset["url"])
    assert f.status_code == 200 and f.headers["content-type"] == "video/mp4"
    assert f.content == DEMO_MP4.read_bytes()
    assert ".mp4" in f.headers["content-disposition"]
    # Browsers seek with Range requests.
    part = await alice.get(asset["url"], headers={"Range": "bytes=0-99"})
    assert part.status_code == 206 and len(part.content) == 100


async def test_image_to_video_uses_own_image(alice):
    asset_id = await _image_asset(alice)
    job = (await _create(alice, image_asset_id=asset_id)).json()
    await run_once()
    assert (await alice.get(f"/api/jobs/{job['id']}")).json()["status"] == "done"


async def test_cannot_animate_someone_elses_image(alice, bob):
    asset_id = await _image_asset(alice)
    r = await _create(bob, image_asset_id=asset_id)
    assert r.status_code == 404
    assert (await bob.get("/api/credits")).json()["balance"] == 10


async def test_video_validation_errors(alice):
    assert (await _create(alice, duration=7)).json()["detail"]["code"] == "duration_unsupported"
    assert (await _create(alice, count=2)).json()["detail"]["code"] == "count_too_high"
    r = await alice.post(
        "/api/jobs",
        json={"provider": "demo", "model": "gradient", "prompt": "img", "duration": 3},
        headers=csrf_headers(alice),
    )
    assert r.json()["detail"]["code"] == "duration_unsupported"
    asset_id = await _image_asset(alice)
    r = await alice.post(
        "/api/jobs",
        json={"provider": "demo", "model": "gradient", "prompt": "img", "image_asset_id": asset_id},
        headers=csrf_headers(alice),
    )
    assert r.json()["detail"]["code"] == "image_input_unsupported"


async def test_start_image_deleted_before_processing_refunds(alice):
    asset_id = await _image_asset(alice)
    job = (await _create(alice, image_asset_id=asset_id)).json()
    await alice.delete(f"/api/assets/{asset_id}", headers=csrf_headers(alice))
    await run_once()
    failed = (await alice.get(f"/api/jobs/{job['id']}")).json()
    assert failed["status"] == "failed" and "start image" in failed["error"]
    assert (await alice.get("/api/credits")).json()["balance"] == 9  # only the image job cost


async def test_preset_uses_camera_motion_wording_for_video(alice):
    job = (await _create(alice, preset_id="halo-orbit", prompt="a ceramic teapot")).json()
    async with db.session_factory()() as s:
        row = await s.get(Job, job["id"])
    assert "camera circles smoothly" in row.params["final_prompt"]


def test_mp4_validation():
    validate_mp4(DEMO_MP4.read_bytes())
    data = DEMO_MP4.read_bytes()
    for bad in (
        b"",
        b"<html><script>alert(1)</script></html>",
        data[:200],  # truncated
        data[:8] + b"evil" + data[12:],  # unknown brand
        b"\x00\x00\x00\x10ftypisom\x00\x00\x00\x00",  # no moov/mdat
    ):
        with pytest.raises(InvalidImageError):
            validate_mp4(bad)
