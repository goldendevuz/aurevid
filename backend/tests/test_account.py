# SPDX-License-Identifier: AGPL-3.0-or-later
from pathlib import Path

from sqlalchemy import func, select

from app import db
from app.config import get_settings
from app.models import Asset, CreditLedger, Job, User
from app.worker import run_once
from tests.conftest import csrf_headers


async def test_export_contains_own_data(alice):
    await alice.post(
        "/api/jobs",
        json={"provider": "demo", "model": "gradient", "prompt": "export me"},
        headers=csrf_headers(alice),
    )
    data = (await alice.get("/api/me/export")).json()
    assert data["user"]["email"] == "alice@example.com"
    assert data["jobs"][0]["prompt"] == "export me"
    assert "password_hash" not in str(data)


async def test_delete_account_erases_everything(alice, bob):
    await alice.post(
        "/api/jobs",
        json={"provider": "demo", "model": "gradient", "prompt": "to be erased"},
        headers=csrf_headers(alice),
    )
    await run_once()
    assert any(Path(get_settings().asset_dir).iterdir())

    wrong = await alice.request(
        "DELETE", "/api/me", json={"password": "wrong"}, headers=csrf_headers(alice)
    )
    assert wrong.status_code == 401
    r = await alice.request(
        "DELETE", "/api/me", json={"password": "correct horse battery"}, headers=csrf_headers(alice)
    )
    assert r.status_code == 204
    assert (await alice.get("/api/me")).status_code == 401
    assert list(Path(get_settings().asset_dir).iterdir()) == []
    async with db.session_factory()() as s:
        for model in (Job, Asset, CreditLedger):
            assert (await s.execute(select(func.count()).select_from(model))).scalar_one() in (
                0,
                1,  # bob's signup ledger row remains
            )
        emails = (await s.execute(select(User.email))).scalars().all()
    assert emails == ["bob@example.com"]
