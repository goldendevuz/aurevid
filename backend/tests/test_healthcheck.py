# SPDX-License-Identifier: AGPL-3.0-or-later
"""Worker healthcheck: healthy only with a fresh heartbeat from this container."""

from datetime import UTC, datetime, timedelta

from app import db
from app.healthcheck import worker_alive
from app.models import WorkerHeartbeat


async def _beat(worker_id: str, age_seconds: int) -> None:
    async with db.session_factory()() as session:
        session.add(
            WorkerHeartbeat(
                id=worker_id,
                slots=2,
                busy=0,
                seen_at=datetime.now(UTC) - timedelta(seconds=age_seconds),
            )
        )
        await session.commit()


async def test_unhealthy_without_any_heartbeat():
    assert await worker_alive("host1") is False


async def test_healthy_with_fresh_heartbeat():
    await _beat("host1:42", 5)
    assert await worker_alive("host1") is True


async def test_unhealthy_when_heartbeat_is_stale():
    await _beat("host1:42", 600)
    assert await worker_alive("host1") is False


async def test_ignores_other_workers_heartbeats():
    await _beat("other:7", 1)
    assert await worker_alive("host1") is False


async def test_hostname_wildcards_are_not_patterns():
    await _beat("hostA:1", 1)
    assert await worker_alive("host%") is False
    assert await worker_alive("host_") is False
