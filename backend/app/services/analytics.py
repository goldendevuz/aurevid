# SPDX-License-Identifier: AGPL-3.0-or-later
"""Admin analytics: overview, funnel, retention, cohorts and system health.

Days are business days in the configured UTC offset (Asia/Tashkent by default). Bucketing runs in
Python over bounded windows so the same code works on SQLite and PostgreSQL. Internal (team/test)
accounts are excluded unless ``include_internal`` is set.
"""

import shutil
import time
from collections import Counter, defaultdict
from datetime import UTC, date, datetime, timedelta
from statistics import median

from sqlalchemy import case, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app import upscaler
from app.config import get_settings
from app.crypto import byok_available
from app.images import asset_root
from app.models import (
    Asset,
    CreditLedger,
    Job,
    JobStatus,
    ModerationEvent,
    ProviderKey,
    ProviderQuota,
    Report,
    User,
    UserActivity,
    WorkerHeartbeat,
)
from app.providers.registry import enabled_providers
from app.security import as_utc
from app.timeutil import local_day, local_midnight_utc, today_local

MAX_WINDOW_DAYS = 400


def _external_users(include_internal: bool):
    return (
        select(User.id) if include_internal else select(User.id).where(User.is_internal.is_(False))
    )


async def _users(session: AsyncSession, include_internal: bool) -> list[User]:
    stmt = select(User)
    if not include_internal:
        stmt = stmt.where(User.is_internal.is_(False))
    return list((await session.execute(stmt)).scalars().all())


async def _jobs_since(session: AsyncSession, since: datetime, include_internal: bool) -> list[Job]:
    stmt = select(Job).where(Job.created_at >= since)
    if not include_internal:
        stmt = stmt.where(Job.user_id.in_(_external_users(False)))
    return list((await session.execute(stmt)).scalars().all())


def _pct(part: int, whole: int) -> float:
    return round(100.0 * part / whole, 1) if whole else 0.0


# --- overview ----------------------------------------------------------------------------------


async def overview(session: AsyncSession, include_internal: bool) -> dict:
    now = datetime.now(UTC)
    today = today_local()
    users = await _users(session, include_internal)
    jobs = await _jobs_since(session, now - timedelta(days=MAX_WINDOW_DAYS), include_internal)
    emails = {u.id: u.email for u in users}

    def count_users(day_from: date, day_to: date) -> int:
        return sum(1 for u in users if day_from <= local_day(u.created_at) <= day_to)

    def jobs_between(day_from: date, day_to: date) -> list[Job]:
        return [j for j in jobs if day_from <= local_day(j.created_at) <= day_to]

    yesterday = today - timedelta(days=1)
    month_start = today.replace(day=1)
    last_month_end = month_start - timedelta(days=1)
    last_month_start = last_month_end.replace(day=1)

    spent = await session.execute(
        select(CreditLedger.created_at, CreditLedger.delta).where(
            CreditLedger.delta < 0,
            CreditLedger.created_at >= local_midnight_utc(yesterday),
            CreditLedger.user_id.in_(_external_users(include_internal)),
        )
    )
    spent_by_day: Counter[date] = Counter()
    for created, delta in spent.all():
        spent_by_day[local_day(created)] += -delta

    def period(day_from: date, day_to: date) -> dict:
        js = jobs_between(day_from, day_to)
        return {
            "users": count_users(day_from, day_to),
            "jobs": len(js),
            "failed": sum(j.status == JobStatus.failed for j in js),
            "videos": sum(j.kind == "video" for j in js),
        }

    # Daily (30 days) and monthly (12 months) series.
    daily = []
    for i in range(29, -1, -1):
        d = today - timedelta(days=i)
        p = period(d, d)
        daily.append({"date": d.isoformat(), **p})
    monthly = []
    cursor = month_start
    months = []
    for _ in range(12):
        months.append(cursor)
        cursor = (cursor - timedelta(days=1)).replace(day=1)
    for m in reversed(months):
        nxt = (m + timedelta(days=32)).replace(day=1)
        p = period(m, nxt - timedelta(days=1))
        monthly.append({"date": m.strftime("%Y-%m"), **p})

    last7 = [j for j in jobs if as_utc(j.created_at) >= now - timedelta(days=7)]
    finished7 = [j for j in last7 if j.status in (JobStatus.done, JobStatus.failed)]
    queued = [j for j in jobs if j.status == JobStatus.queued]
    oldest_wait = (
        int((now - min(as_utc(j.created_at) for j in queued)).total_seconds()) if queued else 0
    )
    storage = (
        await session.execute(
            select(func.count(Asset.id), func.coalesce(func.sum(Asset.size_bytes), 0))
        )
    ).one()
    recent_failures = sorted(
        (j for j in jobs if j.status == JobStatus.failed), key=lambda j: as_utc(j.created_at)
    )[-8:]
    return {
        "generated_at": now,
        "users": {
            "total": len(users),
            "last_24h": sum(1 for u in users if as_utc(u.created_at) >= now - timedelta(days=1)),
            "last_7d": sum(1 for u in users if as_utc(u.created_at) >= now - timedelta(days=7)),
            "blocked": sum(u.is_blocked for u in users),
            "internal": await _count(session, select(func.count(User.id)).where(User.is_internal)),
        },
        "today": {**period(today, today), "credits_spent": spent_by_day[today]},
        "yesterday": {**period(yesterday, yesterday), "credits_spent": spent_by_day[yesterday]},
        "this_month": period(month_start, today),
        "last_month": period(last_month_start, last_month_end),
        "jobs": {
            "by_status": dict(Counter(str(j.status) for j in jobs)),
            "by_kind": dict(Counter(j.kind if j.provider != "local" else "upscale" for j in jobs)),
            "by_provider": dict(Counter(j.provider for j in jobs)),
            "failure_rate_7d": _pct(
                sum(j.status == JobStatus.failed for j in finished7), len(finished7)
            ),
            "queued": len(queued),
            "running": sum(j.status == JobStatus.running for j in jobs),
            "oldest_queued_seconds": oldest_wait,
        },
        "storage": {"assets": storage[0], "bytes": int(storage[1])},
        "open_reports": await _count(
            session, select(func.count(Report.id)).where(Report.status == "open")
        ),
        "moderation_7d": await _count(
            session,
            select(func.count(ModerationEvent.id)).where(
                ModerationEvent.created_at >= now - timedelta(days=7)
            ),
        ),
        "trends": {"daily": daily, "monthly": monthly},
        "recent_users": [
            {"id": u.id, "email": u.email, "created_at": u.created_at}
            for u in sorted(users, key=lambda u: as_utc(u.created_at))[-8:][::-1]
        ],
        "recent_failures": [
            {
                "id": j.id,
                "email": emails.get(j.user_id),
                "provider": j.provider,
                "model": j.model,
                "error": j.error,
                "created_at": j.created_at,
            }
            for j in recent_failures[::-1]
        ],
    }


async def _count(session: AsyncSession, stmt) -> int:
    return int((await session.execute(stmt)).scalar_one() or 0)


# --- per-user job stats (shared by funnel / users list) -----------------------------------------


async def job_stats_by_user(session: AsyncSession) -> dict[str, dict]:
    rows = await session.execute(
        select(
            Job.user_id,
            func.count(Job.id),
            func.sum(case((Job.status == JobStatus.done, 1), else_=0)),
            func.max(Job.created_at),
            func.min(Job.created_at),
        ).group_by(Job.user_id)
    )
    out: dict[str, dict] = {}
    for user_id, total, done, last, first in rows.all():
        out[user_id] = {"jobs": int(total), "done": int(done or 0), "last": last, "first": first}
    return out


# --- funnel ------------------------------------------------------------------------------------


async def funnel(session: AsyncSession, days: int, include_internal: bool) -> dict:
    users = await _users(session, include_internal)
    if days > 0:
        since = datetime.now(UTC) - timedelta(days=days)
        users = [u for u in users if as_utc(u.created_at) >= since]
    ids = {u.id for u in users}
    stats = await job_stats_by_user(session)
    video_users = set(
        (await session.execute(select(Job.user_id).where(Job.kind == "video").distinct()))
        .scalars()
        .all()
    )
    hires_users = {
        j.user_id
        for j in (await session.execute(select(Job).where(Job.provider == "local"))).scalars()
    } | {
        j.user_id
        for j in (await session.execute(select(Job).where(Job.kind == "image"))).scalars()
        if (j.params or {}).get("upscale")
    }
    byok_users = set((await session.execute(select(ProviderKey.user_id).distinct())).scalars())
    attempted = {u for u in ids if stats.get(u, {}).get("jobs", 0) > 0}
    succeeded = {u for u in ids if stats.get(u, {}).get("done", 0) > 0}
    activated = {u for u in ids if stats.get(u, {}).get("done", 0) >= 2}
    power = activated & (video_users | hires_users | byok_users)
    steps = [
        ("registered", len(ids)),
        ("attempted", len(attempted)),
        ("succeeded", len(succeeded)),
        ("activated", len(activated)),
        ("power", len(power)),
    ]
    out = []
    for i, (key, n) in enumerate(steps):
        prev = steps[i - 1][1] if i else n
        out.append(
            {"step": key, "users": n, "of_previous": _pct(n, prev), "of_total": _pct(n, len(ids))}
        )
    tried_failed = len(attempted - succeeded)
    return {"days": days, "steps": out, "tried_but_failed": tried_failed}


# --- retention ---------------------------------------------------------------------------------


async def retention(session: AsyncSession, days: int, include_internal: bool) -> dict:
    users = {u.id: u for u in await _users(session, include_internal)}
    rows = (await session.execute(select(UserActivity.user_id, UserActivity.day))).all()
    by_user: dict[str, set[date]] = defaultdict(set)
    for user_id, day in rows:
        if user_id in users:
            by_user[user_id].add(date.fromisoformat(day))
    signup = {uid: local_day(u.created_at) for uid, u in users.items()}
    today = today_local()

    def day_stats(d: date) -> dict:
        active = {uid for uid, ds in by_user.items() if d in ds}
        new = {uid for uid in active if signup[uid] == d}
        return {
            "date": d.isoformat(),
            "active": len(active),
            "new": len(new),
            "returning": len(active) - len(new),
        }

    series = [day_stats(today - timedelta(days=i)) for i in range(max(1, days) - 1, -1, -1)]
    buckets = Counter()
    for ds in by_user.values():
        n = len(ds)
        key = (
            "1" if n == 1 else "2-3" if n <= 3 else "4-6" if n <= 6 else "7-14" if n <= 14
            else "15-30" if n <= 30 else "30+"
        )  # fmt: skip
        buckets[key] += 1
    returned = sum(1 for ds in by_user.values() if len(ds) >= 2)

    def streak(ds: set[date]) -> int:
        n, d = 0, max(ds)
        while d in ds:
            n, d = n + 1, d - timedelta(days=1)
        return n

    recent = sorted(by_user.items(), key=lambda kv: max(kv[1]), reverse=True)[:20]
    return {
        "today": day_stats(today),
        "yesterday": day_stats(today - timedelta(days=1)),
        "users_total": len(users),
        "returned_users": returned,
        "returning_rate": _pct(returned, len(users)),
        "series": series,
        "frequency": [
            {"bucket": b, "users": buckets.get(b, 0)}
            for b in ("1", "2-3", "4-6", "7-14", "15-30", "30+")
        ],
        "recent": [
            {
                "id": uid,
                "email": users[uid].email,
                "last_active": max(ds).isoformat(),
                "active_days": len(ds),
                "streak": streak(ds),
            }
            for uid, ds in recent
        ],
    }


# --- cohorts -----------------------------------------------------------------------------------


def _period_start(d: date, granularity: str) -> date:
    if granularity == "monthly":
        return d.replace(day=1)
    return d - timedelta(days=d.weekday())  # Monday


def _shift(d: date, granularity: str, k: int) -> date:
    if granularity == "monthly":
        y, m = divmod(d.month - 1 + k, 12)
        return date(d.year + y, m + 1, 1)
    return d + timedelta(weeks=k)


def _label(d: date, granularity: str) -> str:
    if granularity == "monthly":
        return d.strftime("%Y-%m")
    iso = d.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


async def cohorts(
    session: AsyncSession, granularity: str, periods: int, metric: str, include_internal: bool
) -> dict:
    users = await _users(session, include_internal)
    today = today_local()
    current = _period_start(today, granularity)
    first = _shift(current, granularity, -(periods - 1))
    members: dict[date, set[str]] = defaultdict(set)
    for u in users:
        p = _period_start(local_day(u.created_at), granularity)
        if p >= first:
            members[p].add(u.id)
    ids = {u.id for u in users}
    events: dict[str, set[date]] = defaultdict(set)
    if metric == "jobs":
        for user_id, created in (await session.execute(select(Job.user_id, Job.created_at))).all():
            if user_id in ids:
                events[user_id].add(_period_start(local_day(created), granularity))
    else:
        for user_id, day in await session.execute(select(UserActivity.user_id, UserActivity.day)):
            if user_id in ids:
                events[user_id].add(_period_start(date.fromisoformat(day), granularity))
    rows = []
    for k in range(periods):
        start = _shift(first, granularity, k)
        cohort = members.get(start, set())
        values: list[float | None] = []
        for offset in range(periods):
            target = _shift(start, granularity, offset)
            if target > current:
                values.append(None)
                continue
            active = sum(1 for uid in cohort if target in events[uid])
            values.append(_pct(active, len(cohort)) if cohort else None)
        rows.append({"cohort": _label(start, granularity), "size": len(cohort), "values": values})

    stats = await job_stats_by_user(session)
    hours = [
        (as_utc(stats[u.id]["first"]) - as_utc(u.created_at)).total_seconds() / 3600
        for u in users
        if u.id in stats and stats[u.id]["first"]
    ]
    return {
        "granularity": granularity,
        "metric": metric,
        "rows": rows,
        "time_to_first_job_hours": {
            "median": round(median(hours), 1) if hours else None,
            "mean": round(sum(hours) / len(hours), 1) if hours else None,
            "users": len(hours),
        },
    }


# --- system health -----------------------------------------------------------------------------

_RANK = {"healthy": 0, "disabled": 0, "warning": 1, "unhealthy": 2}


async def health(session: AsyncSession) -> dict:
    s = get_settings()
    now = datetime.now(UTC)
    checks: dict[str, dict] = {}

    t = time.perf_counter()
    try:
        await session.execute(text("SELECT 1"))
        checks["database"] = {
            "status": "healthy",
            "latency_ms": round((time.perf_counter() - t) * 1000, 1),
            "engine": s.database_url.split(":", 1)[0],
        }
    except Exception as exc:  # noqa: BLE001
        checks["database"] = {"status": "unhealthy", "error": type(exc).__name__}

    if s.rate_limit_storage.startswith("redis"):
        from app.ratelimit import _limiter

        try:
            ok = _limiter().storage.check()
            checks["redis"] = {"status": "healthy" if ok else "unhealthy"}
        except Exception as exc:  # noqa: BLE001
            checks["redis"] = {"status": "unhealthy", "error": type(exc).__name__}
    else:
        checks["redis"] = {
            "status": "warning" if s.app_env == "prod" else "disabled",
            "note": "in-memory rate limits (single process only)",
        }

    usage = shutil.disk_usage(asset_root())
    free_pct = 100 * usage.free / usage.total
    checks["disk"] = {
        "status": "healthy" if free_pct > 15 else "warning" if free_pct > 5 else "unhealthy",
        "free_gb": round(usage.free / 1e9, 1),
        "total_gb": round(usage.total / 1e9, 1),
        "free_percent": round(free_pct, 1),
    }

    beats = (await session.execute(select(WorkerHeartbeat))).scalars().all()
    alive = [b for b in beats if now - as_utc(b.seen_at) < timedelta(seconds=60)]
    checks["workers"] = {
        "status": "healthy" if alive else "unhealthy",
        "alive": len(alive),
        "slots": sum(b.slots for b in alive),
        "busy": sum(b.busy for b in alive),
        "workers": [{"id": b.id, "busy": b.busy, "slots": b.slots} for b in alive],
    }

    queued = (
        await session.execute(
            select(func.count(Job.id), func.min(Job.created_at)).where(
                Job.status == JobStatus.queued
            )
        )
    ).one()
    wait = int((now - as_utc(queued[1])).total_seconds()) if queued[1] else 0
    stale_after = max(s.job_timeout_seconds * 5, s.video_timeout_seconds * 2)
    stuck = await _count(
        session,
        select(func.count(Job.id)).where(
            Job.status == JobStatus.running,
            Job.started_at < now - timedelta(seconds=stale_after),
        ),
    )
    checks["queue"] = {
        "status": "healthy" if wait < 600 and not stuck else "warning",
        "queued": queued[0],
        "oldest_wait_seconds": wait,
        "stuck_running": stuck,
        "capacity": f"{queued[0]}/{s.max_queue_length}",
    }

    hour = await session.execute(
        select(Job.status).where(
            Job.finished_at >= now - timedelta(hours=1),
            Job.status.in_([JobStatus.done, JobStatus.failed]),
        )
    )
    statuses = [st for (st,) in hour.all()]
    fail = _pct(sum(st == JobStatus.failed for st in statuses), len(statuses))
    checks["failures_1h"] = {
        "status": "healthy" if fail < 20 or len(statuses) < 5 else "warning",
        "failure_percent": fail,
        "finished": len(statuses),
    }

    checks["upscaler"] = {
        "status": "healthy" if upscaler.available() else "disabled",
        "model": upscaler.MODEL_PATH.name,
        "cpu_lanes": s.cpu_job_concurrency,
    }
    checks["byok"] = {
        "status": "healthy" if byok_available() else "warning",
        "note": None if byok_available() else "BYOK_ENCRYPTION_KEY not set: users cannot save keys",
    }

    quotas = {
        (q.provider, q.scope): q
        for q in (await session.execute(select(ProviderQuota))).scalars().all()
    }
    providers = []
    for p in enabled_providers().values():
        server = p.server_credentials()
        q = quotas.get((p.info.id, "server")) or quotas.get((p.info.id, "anon"))
        blocked = bool(q and q.blocked_until and as_utc(q.blocked_until) > now)
        providers.append(
            {
                "id": p.info.id,
                "tier": p.info.tier,
                "server_key": server.source == "server",
                "needs_user_key": p.info.requires_key and server.source != "server",
                "cooldown": blocked,
            }
        )
    checks["providers"] = {
        "status": "warning" if any(p["cooldown"] for p in providers) else "healthy",
        "items": providers,
    }

    warnings = []
    if s.app_env != "prod":
        warnings.append("APP_ENV is not prod")
    if not s.cookie_secure:
        warnings.append("COOKIE_SECURE is false (HTTPS cookies off)")
    if s.mock_provider_enabled:
        warnings.append("Offline demo provider is enabled")
    if not s.turnstile_secret:
        warnings.append("Captcha (Turnstile) is not configured")
    checks["config"] = {
        "status": "warning" if warnings and s.app_env == "prod" else "healthy",
        "warnings": warnings,
        "env": s.app_env,
    }
    overall = max((c["status"] for c in checks.values()), key=lambda st: _RANK.get(st, 1))
    return {"status": overall, "checked_at": now, "checks": checks}
