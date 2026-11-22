# SPDX-License-Identifier: AGPL-3.0-or-later
"""Free use of the owner's (server) keys, shared fairly between users.

* Video (Modal, the owner's own GPU): every user gets ``server_free_videos_per_user`` clips in
  total from the server key, used when they have no key of their own or theirs failed.
* Images (providers with a daily free quota, e.g. Cloudflare): the provider's daily limit
  (learned estimate, else the documented prior) is split evenly between all non-blocked users
  in the database, at least 1 output per user per day.

Counting is per output (``Job.count``) on jobs that ran on the server key (``Job.key_source``),
excluding failed jobs (those were refunded and produced nothing).
"""

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import Job, JobStatus, User
from app.providers.base import ImageProvider
from app.services import quota

# Providers whose server key is the owner's paid account: a small lifetime allowance per user.
LIFETIME_PROVIDERS = {"modal_video", "openrouter_video"}


def lifetime_limits(provider_id: str) -> tuple[int, int]:
    """(clips per user in total, clips per UTC month for everyone) on the owner's key."""
    s = get_settings()
    if provider_id == "openrouter_video":
        return s.openrouter_free_clips_per_user, s.openrouter_monthly_cap
    return s.server_free_videos_per_user, s.server_video_monthly_cap


async def _used(
    session: AsyncSession,
    user_id: str,
    provider_id: str,
    since: datetime | None,
    exclude_job_id: str | None = None,
) -> int:
    """Outputs used on the server key. An output counts ``params.quota_weight`` times (a big
    "Publish quality" image costs the provider several times a small one)."""
    stmt = select(Job.count, Job.params).where(
        Job.user_id == user_id,
        Job.provider == provider_id,
        Job.key_source == "server",
        Job.status != JobStatus.failed,
    )
    if since is not None:
        stmt = stmt.where(Job.created_at >= since)
    if exclude_job_id is not None:
        stmt = stmt.where(Job.id != exclude_job_id)
    rows = (await session.execute(stmt)).all()
    return sum(count * max(1, int((params or {}).get("quota_weight", 1))) for count, params in rows)


async def monthly_left(session: AsyncSession, provider_id: str) -> int:
    """Clips left this UTC month on the owner's key, across all users."""
    start = datetime.now(UTC).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    stmt = select(func.coalesce(func.sum(Job.count), 0)).where(
        Job.provider == provider_id,
        Job.key_source == "server",
        Job.status != JobStatus.failed,
        Job.created_at >= start,
    )
    used = int((await session.execute(stmt)).scalar_one())
    return max(0, lifetime_limits(provider_id)[1] - used)


async def users_count(session: AsyncSession) -> int:
    stmt = select(func.count(User.id)).where(User.is_blocked.is_(False))
    return max(1, int((await session.execute(stmt)).scalar_one()))


async def daily_share(session: AsyncSession, provider: ImageProvider) -> int | None:
    """Per-user daily outputs on the server key; None when the provider has no known limit."""
    view = await quota.view(session, provider.info.id, "server", provider.info.daily_quota_prior)
    if view.estimated_limit is None:
        return None
    return max(1, view.estimated_limit // await users_count(session))


async def server_left(
    session: AsyncSession,
    provider: ImageProvider,
    user_id: str,
    exclude_job_id: str | None = None,
) -> int | None:
    """Outputs this user may still run on the server key; None = no per-user cap applies."""
    pid = provider.info.id
    if pid in LIFETIME_PROVIDERS:
        limit = lifetime_limits(pid)[0]
        own = max(0, limit - await _used(session, user_id, pid, None, exclude_job_id))
        return min(own, await monthly_left(session, pid))
    share = await daily_share(session, provider)
    if share is None:
        return None
    start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    return max(0, share - await _used(session, user_id, pid, start, exclude_job_id))
