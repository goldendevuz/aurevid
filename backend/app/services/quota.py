# SPDX-License-Identifier: AGPL-3.0-or-later
"""Self-learning quota estimator for providers whose limits are undocumented or approximate.

Per (provider, credential scope) we keep:

* ``used_today``: outputs produced in the current UTC day (resets at 00:00 UTC).
* ``est_daily_limit``: estimated daily limit. It starts from a documented prior if one exists,
  then learns:
    - each quota error starting a new streak is an observation "limit ≈ used_today";
      the estimate moves toward it with an EWMA (``ALPHA``), so noise averages out over days;
    - producing more than the estimate without a quota error proves the limit is at least
      ``used_today`` (lower bound), so the estimate is raised immediately.
* ``cooldown_s`` / ``blocked_until``: learned back-off for rate limits. A quota error blocks the
  scope for ``cooldown_s``; repeated errors double it (up to ``MAX_COOLDOWN``); a success after
  a block shrinks it (x ``SHRINK``). Blocks gate new work, so we do not hammer a provider.

The daily estimate is advisory (shown to users and used for warnings); only the cooldown gates
requests. That keeps probing possible, so a wrong (too low) estimate can still be corrected.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ProviderQuota
from app.security import as_utc

ALPHA = 0.5  # weight of a new observation
INITIAL_COOLDOWN = 15.0
MIN_COOLDOWN = 5.0
MAX_COOLDOWN = 6 * 3600.0
SHRINK = 0.75


@dataclass
class QuotaView:
    used_today: int
    estimated_limit: int | None
    remaining: int | None
    source: str  # documented | learned | unknown
    observations: int
    blocked_seconds: int  # 0 when not blocked

    def as_dict(self) -> dict:
        return self.__dict__.copy()


def scope_for(credential_source: str, user_id: str) -> str:
    if credential_source == "user":
        return f"user:{user_id}"
    return "server" if credential_source == "server" else "anon"


def _today(now: datetime) -> str:
    return now.astimezone(UTC).date().isoformat()


async def _row(
    session: AsyncSession, provider: str, scope: str, prior: int | None, now: datetime
) -> ProviderQuota:
    row = (
        await session.execute(
            select(ProviderQuota).where(
                ProviderQuota.provider == provider, ProviderQuota.scope == scope
            )
        )
    ).scalar_one_or_none()
    if row is None:
        row = ProviderQuota(
            provider=provider,
            scope=scope,
            day=_today(now),
            used_today=0,
            hits_today=0,
            est_daily_limit=float(prior) if prior else None,
            est_source="documented" if prior else "unknown",
            observations=0,
            consecutive_hits=0,
            cooldown_s=INITIAL_COOLDOWN,
        )
        try:
            async with session.begin_nested():
                session.add(row)
        except IntegrityError:  # created concurrently
            return await _row(session, provider, scope, prior, now)
    if row.day != _today(now):
        row.day = _today(now)
        row.used_today = 0
        row.hits_today = 0
    return row


def _view(row: ProviderQuota, now: datetime) -> QuotaView:
    est = round(row.est_daily_limit) if row.est_daily_limit is not None else None
    blocked = 0
    if row.blocked_until is not None:
        blocked = max(0, int((as_utc(row.blocked_until) - now).total_seconds()))
    return QuotaView(
        used_today=row.used_today,
        estimated_limit=est,
        remaining=max(0, est - row.used_today) if est is not None else None,
        source=row.est_source,
        observations=row.observations,
        blocked_seconds=blocked,
    )


async def view(
    session: AsyncSession, provider: str, scope: str, prior: int | None, now: datetime | None = None
) -> QuotaView:
    now = now or datetime.now(UTC)
    row = (
        await session.execute(
            select(ProviderQuota).where(
                ProviderQuota.provider == provider, ProviderQuota.scope == scope
            )
        )
    ).scalar_one_or_none()
    if row is None:
        return QuotaView(0, prior, prior, "documented" if prior else "unknown", 0, 0)
    if row.day != _today(now):
        est = round(row.est_daily_limit) if row.est_daily_limit is not None else None
        blocked = _view(row, now).blocked_seconds
        return QuotaView(0, est, est, row.est_source, row.observations, blocked)
    return _view(row, now)


async def record_success(
    session: AsyncSession,
    provider: str,
    scope: str,
    prior: int | None,
    units: int = 1,
    now: datetime | None = None,
) -> QuotaView:
    now = now or datetime.now(UTC)
    row = await _row(session, provider, scope, prior, now)
    row.used_today += units
    if row.est_daily_limit is not None and row.used_today > row.est_daily_limit:
        row.est_daily_limit = float(row.used_today)  # proven lower bound
        row.est_source = "learned"
    if row.consecutive_hits or row.blocked_until is not None:
        row.cooldown_s = max(MIN_COOLDOWN, row.cooldown_s * SHRINK)
    row.consecutive_hits = 0
    row.blocked_until = None
    row.updated_at = now
    await session.flush()
    return _view(row, now)


async def record_quota_hit(
    session: AsyncSession,
    provider: str,
    scope: str,
    prior: int | None,
    now: datetime | None = None,
) -> QuotaView:
    now = now or datetime.now(UTC)
    row = await _row(session, provider, scope, prior, now)
    row.hits_today += 1
    if row.consecutive_hits == 0 and row.used_today > 0:
        observed = float(row.used_today)
        if row.est_daily_limit is None:
            row.est_daily_limit = observed
        else:
            row.est_daily_limit = (1 - ALPHA) * row.est_daily_limit + ALPHA * observed
        row.observations += 1
        row.est_source = "learned"
    elif row.consecutive_hits > 0:
        row.cooldown_s = min(MAX_COOLDOWN, row.cooldown_s * 2)
    row.consecutive_hits += 1
    row.blocked_until = now + timedelta(seconds=row.cooldown_s)
    row.updated_at = now
    await session.flush()
    return _view(row, now)


async def delete_scope(session: AsyncSession, scope: str) -> None:
    from sqlalchemy import delete

    await session.execute(delete(ProviderQuota).where(ProviderQuota.scope == scope))
