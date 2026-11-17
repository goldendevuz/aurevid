# SPDX-License-Identifier: AGPL-3.0-or-later
"""Authorization: a user must never reach another user's jobs, assets or reports."""

from app.worker import run_once
from tests.conftest import csrf_headers


async def _alice_job_and_asset(alice):
    job = (
        await alice.post(
            "/api/jobs",
            json={"provider": "demo", "model": "gradient", "prompt": "private sketch"},
            headers=csrf_headers(alice),
        )
    ).json()
    await run_once()
    asset = (await alice.get(f"/api/jobs/{job['id']}")).json()["assets"][0]
    return job["id"], asset["id"]


async def test_bob_cannot_touch_alice_resources(alice, bob):
    job_id, asset_id = await _alice_job_and_asset(alice)
    h = csrf_headers(bob)
    checks = [
        await bob.get(f"/api/jobs/{job_id}"),
        await bob.get(f"/api/jobs/{job_id}/events"),
        await bob.get(f"/api/assets/{asset_id}/file"),
        await bob.post(f"/api/assets/{asset_id}/favorite", json={"favorite": True}, headers=h),
        await bob.delete(f"/api/assets/{asset_id}", headers=h),
        await bob.post("/api/reports", json={"asset_id": asset_id, "reason": "other"}, headers=h),
    ]
    assert [r.status_code for r in checks] == [404] * len(checks)
    # Not-yours looks exactly like not-found (no id probing).
    missing = await bob.get("/api/jobs/" + "0" * 32)
    assert checks[0].json() == missing.json()
    assert (await bob.get("/api/jobs")).json() == []
    # Alice still has everything.
    assert (await alice.get(f"/api/assets/{asset_id}/file")).status_code == 200


async def test_non_admin_cannot_use_admin_api(alice, bob):
    me = (await alice.get("/api/me")).json()
    h = csrf_headers(bob)
    assert (await bob.get("/api/admin/reports")).status_code == 404
    r = await bob.post(f"/api/admin/users/{me['id']}/block", json={"blocked": True}, headers=h)
    assert r.status_code == 404
    r = await bob.post(
        f"/api/admin/users/{me['id']}/credits", json={"amount": 5, "note_id": "abcd"}, headers=h
    )
    assert r.status_code == 404
