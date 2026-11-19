# SPDX-License-Identifier: AGPL-3.0-or-later
from sqlalchemy import update

from app import db
from app.models import User
from app.worker import run_once
from tests.conftest import csrf_headers

RUN = "/api/recipes/image-animate-4k/run"
BODY = {
    "prompt": "amber lantern on a table",
    "provider": "demo",
    "model": "gradient",
    "video_provider": "demo",
    "video_model": "loop",
}


async def _run(client, **overrides):
    return await client.post(RUN, json={**BODY, **overrides}, headers=csrf_headers(client))


async def _balance(client) -> int:
    return (await client.get("/api/credits")).json()["balance"]


async def test_chain_runs_and_charges_each_step(alice):
    r = await _run(alice)
    assert r.status_code == 201, r.text
    first = r.json()
    assert first["kind"] == "image" and first["cost"] == 1
    assert first["params"]["recipe"]["next"][0]["model"] == "loop"
    assert await _balance(alice) == 9  # only the first step is charged up front

    await run_once()  # image -> the worker queues the animate step
    first = (await alice.get(f"/api/jobs/{first['id']}")).json()
    assert first["status"] == "done"
    next_id = first["params"]["recipe"]["next_job_id"]
    video = (await alice.get(f"/api/jobs/{next_id}")).json()
    assert video["kind"] == "video" and video["cost"] == 2
    assert video["params"]["image_asset_id"] == first["assets"][0]["id"]
    assert video["params"]["recipe"]["prev_job_id"] == first["id"]
    assert await _balance(alice) == 7

    await run_once()
    video = (await alice.get(f"/api/jobs/{next_id}")).json()
    assert video["status"] == "done" and video["assets"][0]["mime"] == "video/mp4"
    assert "error" not in video["params"]["recipe"]
    assert not await run_once()  # chain ended, nothing else queued


async def test_chain_stops_when_a_step_fails(alice):
    first = (await _run(alice, prompt="broken __fail__ lantern")).json()
    await run_once()
    first = (await alice.get(f"/api/jobs/{first['id']}")).json()
    assert first["status"] == "failed"
    assert first["params"]["recipe"]["error"] == "recipe_step_failed"
    assert "next_job_id" not in first["params"]["recipe"]
    assert not await run_once()
    assert await _balance(alice) == 10  # failed image refunded, video never charged


async def test_chain_stops_without_credits_for_next_step(alice):
    first = (await _run(alice)).json()
    async with db.session_factory()() as s:
        await s.execute(update(User).values(credit_balance=0))
        await s.commit()
    await run_once()
    first = (await alice.get(f"/api/jobs/{first['id']}")).json()
    assert first["status"] == "done"
    assert first["params"]["recipe"]["error"] == "insufficient_credits"
    assert not await run_once()


async def test_recipe_validation(alice):
    r = await alice.post("/api/recipes/nope/run", json=BODY, headers=csrf_headers(alice))
    assert r.status_code == 404
    r = await _run(alice, video_model="gradient")  # not a video model
    assert r.json()["detail"]["code"] == "recipe_step_unavailable"
    r = await _run(alice, aspect_ratio="4:3")  # the video model has no 4:3
    assert r.json()["detail"]["code"] == "aspect_ratio_unsupported"
    r = await _run(alice, upscale="4k")  # demo video model cannot upscale
    assert r.json()["detail"]["code"] == "upscale_unsupported"
    r = await _run(alice, provider="demo", model="loop")  # first step must be an image
    assert r.json()["detail"]["code"] == "unknown_model"
    assert await _balance(alice) == 10


async def test_chain_is_owner_scoped(alice, bob):
    first = (await _run(alice)).json()
    await run_once()
    first = (await alice.get(f"/api/jobs/{first['id']}")).json()
    next_id = first["params"]["recipe"]["next_job_id"]
    assert (await bob.get(f"/api/jobs/{first['id']}")).status_code == 404
    assert (await bob.get(f"/api/jobs/{next_id}")).status_code == 404
    assert (await bob.get("/api/jobs")).json() == []
    assert await _balance(bob) == 10
    assert await _balance(alice) == 7


async def test_recipe_requires_login(anon):
    await anon.get("/api/auth/csrf")
    r = await anon.post(RUN, json=BODY, headers=csrf_headers(anon))
    assert r.status_code == 401
