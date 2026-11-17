# SPDX-License-Identifier: AGPL-3.0-or-later
"""Self-learning quota estimator: priors, learning, lower bounds, back-off, daily reset."""

from datetime import UTC, datetime, timedelta

from app import db
from app.providers.base import ProviderError
from app.providers.mock import MockProvider
from app.services import quota
from app.worker import run_once
from tests.conftest import csrf_headers

T0 = datetime(2026, 11, 17, 8, 0, tzinfo=UTC)


async def _hit(s, prior=None, now=T0):
    return await quota.record_quota_hit(s, "svc", "server", prior, now=now)


async def _ok(s, n=1, prior=None, now=T0):
    return await quota.record_success(s, "svc", "server", prior, units=n, now=now)


async def test_unknown_limit_is_learned_from_first_quota_error():
    async with db.session_factory()() as s:
        v = await quota.view(s, "svc", "server", None, now=T0)
        assert v.estimated_limit is None and v.source == "unknown"
        await _ok(s, 40)
        v = await _hit(s)
        assert v.estimated_limit == 40 and v.source == "learned" and v.observations == 1
        assert v.remaining == 0 and v.blocked_seconds == quota.INITIAL_COOLDOWN


async def test_estimate_converges_toward_real_limit_over_days():
    """True limit 100/day; prior wrong (300). Daily observations pull the estimate in."""
    async with db.session_factory()() as s:
        est = []
        for day in range(6):
            now = T0 + timedelta(days=day)
            await _ok(s, 100, prior=300, now=now)
            v = await _hit(s, prior=300, now=now)
            est.append(v.estimated_limit)
        assert est[0] == 200  # 0.5*300 + 0.5*100
        assert all(a >= b for a, b in zip(est, est[1:], strict=False))
        assert abs(est[-1] - 100) <= 5


async def test_success_beyond_estimate_raises_it_immediately():
    async with db.session_factory()() as s:
        await _ok(s, 10)
        await _hit(s)  # estimate 10 (maybe it was only a burst limit)
        v = await _ok(s, 5, now=T0 + timedelta(minutes=5))
        assert v.estimated_limit == 15 and v.used_today == 15


async def test_cooldown_doubles_on_repeated_hits_and_shrinks_after_success():
    async with db.session_factory()() as s:
        await _ok(s, 3)
        first = await _hit(s)
        second = await _hit(s, now=T0 + timedelta(seconds=20))
        third = await _hit(s, now=T0 + timedelta(seconds=60))
        assert (first.blocked_seconds, second.blocked_seconds, third.blocked_seconds) == (
            15,
            30,
            60,
        )
        # Only the first hit of a streak counts as a limit observation.
        assert third.observations == 1
        await _ok(s, now=T0 + timedelta(minutes=5))
        row_view = await _hit(s, now=T0 + timedelta(minutes=6))
        assert row_view.blocked_seconds == 45  # 60 * 0.75


async def test_counters_reset_each_utc_day_but_estimate_persists():
    async with db.session_factory()() as s:
        await _ok(s, 50)
        await _hit(s)
        v = await quota.view(s, "svc", "server", None, now=T0 + timedelta(days=1))
        assert v.used_today == 0 and v.estimated_limit == 50 and v.remaining == 50


async def test_documented_prior_shown_before_any_use(alice):
    s_providers = {p["id"]: p for p in (await alice.get("/api/providers")).json()}
    cf = s_providers["cloudflare"]["quota"]
    assert cf["estimated_limit"] == 170 and cf["source"] == "documented"


async def test_worker_learns_and_api_blocks_during_cooldown(alice, monkeypatch):
    calls = {"n": 0}
    original = MockProvider.generate

    async def limited(self, req, creds):
        calls["n"] += 1
        if calls["n"] > 2:
            raise ProviderError("demo quota", quota=True)
        return await original(self, req, creds)

    monkeypatch.setattr(MockProvider, "generate", limited)
    monkeypatch.setattr(quota, "INITIAL_COOLDOWN", 120.0)
    h = csrf_headers(alice)
    body = {"provider": "demo", "model": "gradient", "prompt": "quota probe", "count": 3}
    job = (await alice.post("/api/jobs", json=body, headers=h)).json()
    await run_once()
    done = (await alice.get(f"/api/jobs/{job['id']}")).json()
    assert len(done["assets"]) == 2 and done["error"]

    demo = {p["id"]: p for p in (await alice.get("/api/providers")).json()}["demo"]["quota"]
    assert demo["estimated_limit"] == 2 and demo["used_today"] == 2
    assert demo["source"] == "learned" and demo["blocked_seconds"] > 30

    r = await alice.post("/api/jobs", json={**body, "count": 1}, headers=h)
    assert r.status_code == 429 and r.json()["detail"]["code"] == "provider_cooldown"
    assert int(r.headers["retry-after"]) > 30
    # The rejected request cost nothing: 10 - 3 + 1 refund = 8.
    assert (await alice.get("/api/credits")).json()["balance"] == 8
