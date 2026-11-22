# SPDX-License-Identifier: AGPL-3.0-or-later
"""Scheduling: admission control, round-robin fairness, CPU/provider caps, queue position."""

from datetime import UTC, datetime, timedelta

from app import db
from app.config import get_settings
from app.models import Job, JobStatus
from app.services import queue
from app.worker import claim_next
from tests.conftest import csrf_headers, make_user

T0 = datetime(2026, 11, 17, 9, 0, tzinfo=UTC)


def _job(jid, user, minute, provider="demo", kind="image", upscale=None):
    return Job(
        id=jid, user_id=user, provider=provider, model="m", kind=kind, prompt="p", count=1,
        cost=1, params={"upscale": upscale}, created_at=T0 + timedelta(minutes=minute),
    )  # fmt: skip


def test_round_robin_across_users():
    queued = [_job("a1", "A", 0), _job("a2", "A", 1), _job("a3", "A", 2), _job("b1", "B", 3)]
    assert [j.id for j in queue.fair_order(queued, [])] == ["a1", "b1", "a2", "a3"]
    # A user with work already running goes behind others.
    running = [_job("a0", "A", -5)]
    assert [j.id for j in queue.fair_order(queued, running)][0] == "b1"


def test_cpu_and_provider_caps():
    s = get_settings()
    s.cpu_job_concurrency, s.provider_concurrency = 1, 2
    cpu_running = [_job("u0", "A", 0, provider="local")]
    queued = [_job("u1", "B", 1, provider="local"), _job("g1", "C", 2, upscale="8k"),
              _job("n1", "D", 3)]  # fmt: skip
    assert queue.pick(queued, cpu_running).id == "n1"  # CPU lane full, network job goes first
    net_running = [_job("x", "E", 0), _job("y", "F", 0)]  # demo provider at its cap
    assert queue.pick([_job("n2", "G", 1)], net_running) is None


async def _post(client, n=1):
    return [
        await client.post(
            "/api/jobs",
            json={"provider": "demo", "model": "gradient", "prompt": f"job {i}"},
            headers=csrf_headers(client),
        )
        for i in range(n)
    ]


async def test_global_queue_backpressure(alice, bob):
    get_settings().max_queue_length = 2
    await _post(alice, 2)
    r = (await _post(bob))[0]
    assert r.status_code == 503 and r.json()["detail"]["code"] == "queue_full"


async def test_queue_position_and_eta_shown(alice, bob):
    await _post(alice, 2)
    b = (await _post(bob))[0].json()
    # Round-robin: bob's first job is 2nd, ahead of alice's second.
    assert b["queue_position"] == 2 and b["eta_seconds"] > 0


async def test_worker_claims_fairly(alice):
    carol, _ = await make_user("carol@example.com")
    try:
        await _post(alice, 3)
        c = (await _post(carol))[0].json()
        first, second = await claim_next(), await claim_next()
        assert first.user_id != second.user_id and c["id"] in (first.id, second.id)
    finally:
        await carol.aclose()


async def test_claim_respects_cpu_cap_across_workers(alice):
    get_settings().cpu_job_concurrency = 1
    async with db.session_factory()() as s:
        user_id = (await alice.get("/api/me")).json()["id"]
        s.add(_job("cpu-running", user_id, 0, provider="local"))
        s.add(_job("cpu-queued", user_id, 1, provider="local"))
        await s.flush()
        running = await s.get(Job, "cpu-running")
        running.status = JobStatus.running
        await s.commit()
    assert await claim_next() is None  # the only queued job is CPU-class and the lane is busy


async def _finished(user_id, seconds, *, model="m", upscale=None, kind="video", provider="fal"):
    start = datetime(2026, 11, 17, 9, 0, tzinfo=UTC)
    async with db.session_factory()() as session:
        session.add(
            Job(
                id=f"d{seconds}-{upscale}-{model}", user_id=user_id, provider=provider, model=model,
                kind=kind, prompt="p", count=1, cost=1, params={"upscale": upscale},
                status=JobStatus.done, created_at=start, started_at=start,
                finished_at=start + timedelta(seconds=seconds),
            )
        )  # fmt: skip
        await session.commit()


async def test_typical_run_seconds_uses_median_and_ignores_outliers():
    _, user = await make_user("median@example.com")
    for secs in (100, 110, 120, 130, 4000):  # one stuck job must not skew it
        await _finished(user["id"], secs)
    async with db.session_factory()() as session:
        assert await queue.typical_run_seconds(session, _job("r", "A", 0, "fal", "video")) == 120


async def test_typical_run_seconds_separates_upscaled_and_models():
    _, user = await make_user("separate@example.com")
    await _finished(user["id"], 100)
    await _finished(user["id"], 900, upscale="4k")
    await _finished(user["id"], 30, model="other")
    async with db.session_factory()() as session:
        plain = _job("r1", "A", 0, "fal", "video")
        scaled = _job("r2", "A", 0, "fal", "video", upscale="4k")
        assert await queue.typical_run_seconds(session, plain) == 100
        assert await queue.typical_run_seconds(session, scaled) == 900


async def test_typical_run_seconds_fallbacks_without_history():
    async with db.session_factory()() as session:
        video = _job("r1", "A", 0, "fal", "video")
        scaled = _job("r2", "A", 0, "fal", "video", upscale="8k")
        assert await queue.typical_run_seconds(session, video) == queue.DEFAULT_SECONDS["video"]
        assert (
            await queue.typical_run_seconds(session, scaled) == queue.DEFAULT_UPSCALED_VIDEO_SECONDS
        )


async def test_running_job_exposes_started_at_and_typical_seconds():
    client, user = await make_user("running@example.com")
    now = datetime.now(UTC)
    async with db.session_factory()() as session:
        session.add(
            Job(
                id="run1", user_id=user["id"], provider="fal", model="m", kind="video",
                prompt="p", count=1, cost=1, params={}, status=JobStatus.running,
                created_at=now, started_at=now,
            )
        )  # fmt: skip
        await session.commit()
    body = (await client.get("/api/jobs/run1")).json()
    assert body["started_at"] and body["typical_seconds"] == queue.DEFAULT_SECONDS["video"]
    assert body["queue_position"] is None


async def test_job_exposes_model_label_and_audio_flag():
    client, user = await make_user("labels@example.com")
    now = datetime.now(UTC)
    async with db.session_factory()() as session:
        session.add_all(
            [
                Job(
                    id="lab1", user_id=user["id"], provider="demo", model="gradient", kind="image",
                    prompt="p", count=1, cost=1, params={}, status=JobStatus.done, created_at=now,
                ),
                Job(
                    id="lab2", user_id=user["id"], provider="gone", model="x", kind="image",
                    prompt="p", count=1, cost=1, params={}, status=JobStatus.done, created_at=now,
                ),
            ]
        )  # fmt: skip
        await session.commit()
    known = (await client.get("/api/jobs/lab1")).json()
    assert known["model_label"] and known["provider_name"] and known["has_audio"] is False
    unknown = (await client.get("/api/jobs/lab2")).json()  # provider no longer enabled
    assert unknown["model_label"] is None and unknown["provider_name"] is None
