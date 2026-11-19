# SPDX-License-Identifier: AGPL-3.0-or-later
"""History filters, facets and job deletion: always scoped to the caller's own jobs."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

from app import db
from app.config import get_settings
from app.models import Job, JobStatus
from app.worker import run_once
from tests.conftest import csrf_headers


async def create(client, **body):
    body = {"provider": "demo", "model": "gradient", "prompt": "a red bicycle", **body}
    r = await client.post("/api/jobs", json=body, headers=csrf_headers(client))
    assert r.status_code == 201, r.text
    await run_once()
    return r.json()["id"]


async def ids(client, **params) -> list[str]:
    r = await client.get("/api/jobs", params=params)
    assert r.status_code == 200, r.text
    return [j["id"] for j in r.json()]


async def _seed(client):
    """One done image, one failed image, one done video and a (fake) local upscale."""
    image = await create(client, prompt="Lighthouse at dawn")
    failed = await create(client, prompt="storm __fail__ please")
    video = await create(client, model="loop", prompt="waves loop")
    async with db.session_factory()() as s:
        user_id = (await s.get(Job, image)).user_id
        up = Job(
            user_id=user_id,
            kind="image",
            provider="local",
            model="realesr-general-x4v3",
            prompt="Upscale to 4K",
            params={"upscale": "4k", "aspect_ratio": "1:1"},
            status=JobStatus.done,
            created_at=datetime.now(UTC) - timedelta(days=10),
        )
        s.add(up)
        await s.commit()
        upscale = up.id
    return image, failed, video, upscale


async def test_filters_combine_and_stay_owner_scoped(alice, bob):
    image, failed, video, upscale = await _seed(alice)
    bob_image = await create(bob, prompt="Lighthouse of bob")

    assert set(await ids(alice)) == {image, failed, video, upscale}
    assert set(await ids(alice, kind="image")) == {image, failed}
    assert await ids(alice, kind="video") == [video]
    assert await ids(alice, kind="upscale") == [upscale]
    assert await ids(alice, status="failed") == [failed]
    assert set(await ids(alice, status="done")) == {image, video, upscale}
    assert await ids(alice, status="active") == []
    assert failed not in await ids(alice, hide_failed="true")
    assert await ids(alice, kind="image", status="done") == [image]
    assert await ids(alice, provider="demo", model="loop") == [video]
    assert set(await ids(alice, period="7d")) == {image, failed, video}
    assert upscale in await ids(alice, period="30d")
    assert upscale not in await ids(alice, period="today")
    # Case-insensitive prompt search; LIKE wildcards are literal.
    assert await ids(alice, q="lighthouse") == [image]
    assert await ids(alice, q="%") == []
    assert await ids(alice, q="__fail__") == [failed]

    # Bob's matching job never leaks into Alice's results, and vice versa.
    assert bob_image not in await ids(alice, q="Lighthouse")
    assert await ids(bob, q="Lighthouse") == [bob_image]
    assert await ids(bob, kind="video") == []
    assert await ids(bob, provider="demo", model="loop") == []

    bad = await alice.get("/api/jobs", params={"kind": "audio"})
    assert bad.status_code == 422


async def test_pagination_keeps_filters(alice):
    made = [await create(alice, prompt=f"cat {i}") for i in range(3)]
    await create(alice, prompt="dog")
    first = (await alice.get("/api/jobs", params={"q": "cat", "limit": 2})).json()
    assert [j["id"] for j in first] == [made[2], made[1]]
    rest = await ids(alice, q="cat", limit=2, before=first[-1]["created_at"])
    assert rest == [made[0]]


async def test_facets_count_only_own_jobs(alice, bob):
    await _seed(alice)
    await create(bob, prompt="bob one")
    await create(bob, prompt="bob two")

    facets = (await alice.get("/api/jobs/facets")).json()
    assert facets["total"] == 4
    assert {f["value"]: f["count"] for f in facets["kinds"]} == {
        "image": 2,
        "video": 1,
        "upscale": 1,
    }
    assert {f["value"]: f["count"] for f in facets["statuses"]} == {"done": 3, "failed": 1}
    providers = {f["value"]: f for f in facets["providers"]}
    assert providers["demo"]["count"] == 3 and providers["demo"]["label"] == "Offline demo"
    models = {f["value"]: f for f in facets["models"]}
    assert models["gradient"]["count"] == 2 and models["gradient"]["provider"] == "demo"
    assert models["loop"]["count"] == 1

    bob_facets = (await bob.get("/api/jobs/facets")).json()
    assert bob_facets["total"] == 2
    assert {f["value"]: f["count"] for f in bob_facets["models"]} == {"gradient": 2}
    assert [f["value"] for f in bob_facets["kinds"]] == ["image"]


async def test_delete_job_removes_files_and_is_owner_only(alice, bob):
    job_id = await create(alice, count=2)
    failed = await create(alice, prompt="x __fail__")
    asset_dir = Path(get_settings().asset_dir)
    assert len(list(asset_dir.iterdir())) == 2

    # Bob gets the same 404 as for a missing id.
    r = await bob.delete(f"/api/jobs/{job_id}", headers=csrf_headers(bob))
    missing = await bob.delete("/api/jobs/" + "0" * 32, headers=csrf_headers(bob))
    assert r.status_code == missing.status_code == 404 and r.json() == missing.json()
    assert (await alice.get(f"/api/jobs/{job_id}")).status_code == 200

    for jid in (job_id, failed):
        assert (
            await alice.delete(f"/api/jobs/{jid}", headers=csrf_headers(alice))
        ).status_code == 204
        assert (await alice.get(f"/api/jobs/{jid}")).status_code == 404
    assert list(asset_dir.iterdir()) == []
    assert await ids(alice) == []
    # Credit history stays intact (append-only ledger).
    assert (await alice.get("/api/credits")).json()["balance"] == 8


async def test_cannot_delete_unfinished_job(alice):
    r = await alice.post(
        "/api/jobs",
        json={"provider": "demo", "model": "gradient", "prompt": "still running"},
        headers=csrf_headers(alice),
    )
    job_id = r.json()["id"]
    r = await alice.delete(f"/api/jobs/{job_id}", headers=csrf_headers(alice))
    assert r.status_code == 409 and r.json()["detail"]["code"] == "job_not_finished"
