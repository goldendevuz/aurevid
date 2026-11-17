# SPDX-License-Identifier: AGPL-3.0-or-later
"""Admin panel API: access control, analytics, user/job management, audit, exports."""

import csv
import io

import pytest
from sqlalchemy import select

from app import db
from app.models import AdminAudit, ModerationEvent, User
from app.worker import run_once
from tests.conftest import csrf_headers, make_user


async def _promote(client) -> str:
    me = (await client.get("/api/me")).json()
    async with db.session_factory()() as s:
        (await s.get(User, me["id"])).is_admin = True
        await s.commit()
    return me["id"]


@pytest.fixture
async def admin(alice):
    await _promote(alice)
    return alice


async def _job(client, prompt="a lamp", **kw):
    return await client.post(
        "/api/jobs",
        json={"provider": "demo", "model": "gradient", "prompt": prompt, **kw},
        headers=csrf_headers(client),
    )


GET_ROUTES = [
    "/api/admin/stats", "/api/admin/funnel", "/api/admin/retention", "/api/admin/cohorts",
    "/api/admin/health", "/api/admin/users", "/api/admin/jobs", "/api/admin/jobs/errors",
    "/api/admin/moderation", "/api/admin/reports", "/api/admin/providers",
    "/api/admin/announcements", "/api/admin/audit", "/api/admin/export/users.csv",
    "/api/admin/export/jobs.csv",
]  # fmt: skip


async def test_non_admins_get_404_everywhere(bob, anon):
    for path in GET_ROUTES:
        assert (await bob.get(path)).status_code == 404, path
        assert (await anon.get(path)).status_code == 401, path


async def test_every_admin_view_loads(admin):
    await _job(admin)
    await run_once()
    for path in GET_ROUTES:
        r = await admin.get(path)
        assert r.status_code == 200, (path, r.text)


async def test_overview_excludes_internal_accounts(admin, bob):
    await _job(bob)
    await run_once()
    bob_id = (await bob.get("/api/me")).json()["id"]
    full = (await admin.get("/api/admin/stats")).json()
    assert full["users"]["total"] == 2 and full["today"]["jobs"] == 1
    r = await admin.post(
        f"/api/admin/users/{bob_id}/internal", json={"value": True}, headers=csrf_headers(admin)
    )
    assert r.json()["is_internal"] is True
    real = (await admin.get("/api/admin/stats")).json()
    assert real["users"]["total"] == 1 and real["today"]["jobs"] == 0
    assert real["users"]["internal"] == 1
    both = (await admin.get("/api/admin/stats?include_internal=true")).json()
    assert both["today"]["jobs"] == 1
    assert len(full["trends"]["daily"]) == 30 and len(full["trends"]["monthly"]) == 12


async def test_users_filters_sort_pagination(admin, bob):
    carol, _ = await make_user("carol@example.com")
    try:
        await _job(bob)
        await run_once()
        await _job(carol, prompt="__fail__ now")
        await run_once()
        get = lambda **p: admin.get("/api/admin/users", params=p)  # noqa: E731
        assert (await get(activity="activated")).json()["items"][0]["email"] == "bob@example.com"
        assert [u["email"] for u in (await get(activity="tried_failed")).json()["items"]] == [
            "carol@example.com"
        ]
        unact = {u["email"] for u in (await get(activity="unactivated")).json()["items"]}
        assert unact == {"alice@example.com"}
        assert (await get(q="CAROL")).json()["total"] == 1
        assert (await get(q="%")).json()["total"] == 0  # wildcards are escaped
        page = (await get(limit=2, page=2)).json()
        assert page["total"] == 3 and len(page["items"]) == 1
        top = (await get(sort="jobs_desc")).json()["items"][0]
        assert top["jobs"] == 1
    finally:
        await carol.aclose()


async def test_user_detail_never_leaks_secrets(admin, bob):
    bob_id = (await bob.get("/api/me")).json()["id"]
    await bob.put(
        "/api/me/keys/cloudflare",
        json={"values": {"account_id": "a" * 32, "api_token": "TOPSECRET-token"}},
        headers=csrf_headers(bob),
    )
    r = await admin.get(f"/api/admin/users/{bob_id}")
    assert r.status_code == 200 and r.json()["provider_keys"] == ["cloudflare"]
    assert "TOPSECRET" not in r.text and "password" not in r.text


async def test_credits_add_deduct_idempotent(admin, bob):
    bob_id = (await bob.get("/api/me")).json()["id"]
    h = csrf_headers(admin)
    url = f"/api/admin/users/{bob_id}/credits"
    assert (await admin.post(url, json={"amount": 5, "note_id": "promo1"}, headers=h)).json()[
        "balance"
    ] == 15
    again = await admin.post(url, json={"amount": 5, "note_id": "promo1"}, headers=h)
    assert again.json()["balance"] == 15  # same note id -> applied once
    r = await admin.post(url, json={"amount": 4, "mode": "deduct", "note_id": "fix1"}, headers=h)
    assert r.json()["balance"] == 11
    r = await admin.post(url, json={"amount": 99, "mode": "deduct", "note_id": "fix2"}, headers=h)
    assert r.status_code == 409  # never negative


async def test_admin_cannot_block_or_demote_self(admin):
    me = (await admin.get("/api/me")).json()["id"]
    h = csrf_headers(admin)
    r = await admin.post(f"/api/admin/users/{me}/block", json={"blocked": True}, headers=h)
    assert r.json()["detail"]["code"] == "cannot_target_self"
    r = await admin.post(f"/api/admin/users/{me}/admin", json={"value": False}, headers=h)
    assert r.status_code == 400


async def test_cancel_and_retry_jobs(admin, bob):
    h = csrf_headers(admin)
    queued = (await _job(bob)).json()
    r = await admin.post(f"/api/admin/jobs/{queued['id']}/cancel", headers=h)
    assert r.status_code == 200
    assert (await bob.get("/api/credits")).json()["balance"] == 10  # refunded
    r = await admin.post(f"/api/admin/jobs/{queued['id']}/cancel", headers=h)
    assert r.status_code == 409
    r = await admin.post(f"/api/admin/jobs/{queued['id']}/retry", headers=h)
    assert r.json()["status"] == "queued"
    await run_once()
    done = (await bob.get(f"/api/jobs/{queued['id']}")).json()
    assert done["status"] == "done"
    assert (await bob.get("/api/credits")).json()["balance"] == 10  # free re-run
    errors = (await admin.get("/api/admin/jobs/errors")).json()
    assert errors == [] or all("error" in e for e in errors)


async def test_job_filters(admin, bob):
    await _job(bob)
    await _job(bob, prompt="__fail__ x")
    await run_once()
    await run_once()
    failed = (await admin.get("/api/admin/jobs", params={"status": "failed"})).json()
    assert failed["total"] == 1 and failed["items"][0]["user_email"] == "bob@example.com"
    assert (await admin.get("/api/admin/jobs", params={"q": "nobody"})).json()["total"] == 0
    assert (await admin.get("/api/admin/jobs", params={"kind": "video"})).json()["total"] == 0


async def test_moderation_events_store_category_not_prompt(admin, bob):
    r = await _job(bob, prompt="explicit nsfw scene of something")
    assert r.status_code == 400
    async with db.session_factory()() as s:
        ev = (await s.execute(select(ModerationEvent))).scalar_one()
    assert ev.category == "sexual" and not hasattr(ev, "prompt")
    m = (await admin.get("/api/admin/moderation")).json()
    assert m["by_category"] == {"sexual": 1} and m["users"][0]["email"] == "bob@example.com"


async def test_funnel_retention_cohorts_shapes(admin, bob):
    await _job(bob)
    await run_once()
    f = (await admin.get("/api/admin/funnel?days=0")).json()
    steps = {s["step"]: s["users"] for s in f["steps"]}
    assert steps["registered"] == 2 and steps["succeeded"] == 1
    r = (await admin.get("/api/admin/retention?days=7")).json()
    assert r["today"]["active"] == 2 and len(r["series"]) == 7  # activity tracked on requests
    c = (await admin.get("/api/admin/cohorts?granularity=monthly&periods=4")).json()
    assert len(c["rows"]) == 4 and c["rows"][-1]["values"][0] == 100.0


async def test_health_reports_components(admin):
    h = (await admin.get("/api/admin/health")).json()
    for key in ("database", "disk", "workers", "queue", "upscaler", "byok", "providers", "config"):
        assert key in h["checks"]
    assert h["checks"]["database"]["status"] == "healthy"


async def test_announcements_flow_and_audit(admin, bob):
    h = csrf_headers(admin)
    a = (
        await admin.post(
            "/api/admin/announcements",
            json={"text_en": "Maintenance at 22:00", "text_uz": "22:00 da texnik ishlar"},
            headers=h,
        )
    ).json()
    shown = (await bob.get("/api/announcements")).json()
    assert shown[0]["text_uz"] == "22:00 da texnik ishlar"
    await admin.patch(f"/api/admin/announcements/{a['id']}", json={"active": False}, headers=h)
    assert (await bob.get("/api/announcements")).json() == []
    r = await bob.post(
        "/api/admin/announcements", json={"text_en": "hack"}, headers=csrf_headers(bob)
    )
    assert r.status_code == 404
    async with db.session_factory()() as s:
        actions = [a.action for a in (await s.execute(select(AdminAudit))).scalars()]
    assert "announcement.create" in actions and "announcement.active" in actions


async def test_csv_export_neutralises_formulas(admin):
    await make_user("=cmd@example.com")  # attacker-controlled cell content
    r = await admin.get("/api/admin/export/users.csv")
    assert r.headers["content-type"].startswith("text/csv")
    rows = list(csv.reader(io.StringIO(r.text)))
    emails = [row[1] for row in rows[1:]]
    assert "'=cmd@example.com" in emails
