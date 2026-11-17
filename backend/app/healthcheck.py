# SPDX-License-Identifier: AGPL-3.0-or-later
"""Container healthcheck for the worker, which serves no HTTP.

Healthy means: this container's worker wrote a heartbeat (see worker._heartbeat, every 15 s)
within the last `MAX_AGE_SECONDS`. The worker's id is "<hostname>:<pid>"; the check runs in the
same container, so the hostname matches while the pid differs.

Run as: python -m app.healthcheck   (exit 0 = healthy, 1 = unhealthy)
"""

import asyncio
import socket
import sys
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select

from app import db
from app.models import WorkerHeartbeat

MAX_AGE_SECONDS = 60


async def worker_alive(hostname: str, max_age: int = MAX_AGE_SECONDS) -> bool:
    cutoff = datetime.now(UTC) - timedelta(seconds=max_age)
    prefix = hostname.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    async with db.session_factory()() as session:
        fresh = await session.scalar(
            select(func.count())
            .select_from(WorkerHeartbeat)
            .where(
                WorkerHeartbeat.id.like(f"{prefix}:%", escape="\\"),
                WorkerHeartbeat.seen_at >= cutoff,
            )
        )
    return bool(fresh)


def main() -> int:
    try:
        return 0 if asyncio.run(worker_alive(socket.gethostname())) else 1
    except Exception as exc:  # noqa: BLE001 - any failure means "not healthy"
        print(f"healthcheck failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
