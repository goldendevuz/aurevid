# SPDX-License-Identifier: AGPL-3.0-or-later
"""Admin panel API.

Overview, users, jobs, funnel, retention, cohorts, moderation, system health, provider limits,
announcements, audit log and CSV exports. Every route requires an admin; non-admins get 404 so
the panel's existence is not revealed. Every state change is written to ``admin_audit``.
Analytics exclude internal (team/test) accounts unless ``include_internal=true``.
"""

import csv
import io
import logging
from datetime import UTC, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Select, case, delete, func, or_, select, update

from app.deps import AdminUser, CurrentUser, Session, not_found
from app.images import asset_path, delete_stored
from app.models import (
    AdminAudit,
    Announcement,
    Asset,
    CreditLedger,
    Job,
    JobStatus,
    ModerationEvent,
    PaymentOrder,
    PaymentStatus,
    ProviderKey,
    ProviderQuota,
    RefreshToken,
    Report,
    User,
    UserActivity,
    utcnow,
)
from app.schemas import UTCDateTime
from app.security import as_utc
from app.services import analytics, credits, quota
from app.timeutil import local_midnight_utc, today_local

router = APIRouter(prefix="/api/admin", tags=["admin"])
public = APIRouter(prefix="/api", tags=["announcements"])
log = logging.getLogger("aurevid.audit")

Range = Literal["today", "7d", "30d", "90d", "all"]


class _In(BaseModel):
    model_config = ConfigDict(extra="forbid")


class BlockIn(_In):
    blocked: bool


class FlagIn(_In):
    value: bool


class CreditsIn(_In):
    amount: int = Field(ge=1, le=100_000)
    mode: Literal["add", "deduct"] = "add"
    note_id: str = Field(min_length=4, max_length=40)  # idempotency: retries never double-apply


class AnnouncementIn(_In):
    level: Literal["info", "warning", "success"] = "info"
    text_en: str = Field(min_length=3, max_length=500)
    text_uz: str | None = Field(default=None, max_length=500)
    text_ru: str | None = Field(default=None, max_length=500)
    ends_at: datetime | None = None


class AnnouncementPatch(_In):
    active: bool


class UserRow(BaseModel):
    id: str
    email: str
    is_admin: bool
    is_blocked: bool
    is_internal: bool
    credit_balance: int
    jobs: int
    done: int
    last_job_at: UTCDateTime | None
    last_active: str | None
    created_at: UTCDateTime


class JobRow(BaseModel):
    id: str
    user_id: str
    user_email: str | None
    kind: str
    provider: str
    model: str
    status: str
    count: int
    cost: int
    attempts: int
    upscale: str | None
    error: str | None
    created_at: UTCDateTime
    seconds: float | None


async def _audit(session, admin: User, action: str, target: str | None, **details) -> None:
    session.add(AdminAudit(admin_id=admin.id, action=action, target=target, details=details))
    log.info("admin=%s action=%s target=%s", admin.id, action, target)


def _since(range_: Range) -> datetime | None:
    if range_ == "all":
        return None
    if range_ == "today":
        return local_midnight_utc(today_local())
    return datetime.now(UTC) - timedelta(days=int(range_[:-1]))


def _like(q: str) -> str:
    escaped = q.strip().lower().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


# --- analytics ---------------------------------------------------------------------------------


@router.get("/stats")
async def stats(_: AdminUser, session: Session, include_internal: bool = False):
    return await analytics.overview(session, include_internal)


@router.get("/funnel")
async def funnel(
    _: AdminUser,
    session: Session,
    days: int = Query(30, ge=0, le=730),
    include_internal: bool = False,
):
    return await analytics.funnel(session, days, include_internal)


@router.get("/retention")
async def retention(
    _: AdminUser,
    session: Session,
    days: int = Query(14, ge=1, le=90),
    include_internal: bool = False,
):
    return await analytics.retention(session, days, include_internal)


@router.get("/cohorts")
async def cohorts(
    _: AdminUser,
    session: Session,
    granularity: Literal["weekly", "monthly"] = "weekly",
    periods: int = Query(8, ge=4, le=24),
    metric: Literal["activity", "jobs"] = "activity",
    include_internal: bool = False,
):
    return await analytics.cohorts(session, granularity, periods, metric, include_internal)


@router.get("/health")
async def health(_: AdminUser, session: Session):
    return await analytics.health(session)


# --- users -------------------------------------------------------------------------------------

UserFilter = Literal["all", "customers", "internal", "blocked", "admins"]
Activity = Literal["all", "activated", "unactivated", "tried_failed"]
UserSort = Literal["newest", "oldest", "balance_desc", "balance_asc", "jobs_desc", "last_active"]


def _users_query(q: str, filter_: UserFilter, activity: Activity, range_: Range) -> Select:
    jobs = (
        select(
            Job.user_id.label("uid"),
            func.count(Job.id).label("jobs"),
            func.sum(case((Job.status == JobStatus.done, 1), else_=0)).label("done"),
            func.max(Job.created_at).label("last_job"),
        )
        .group_by(Job.user_id)
        .subquery()
    )
    act = (
        select(UserActivity.user_id.label("uid"), func.max(UserActivity.day).label("last_day"))
        .group_by(UserActivity.user_id)
        .subquery()
    )
    stmt = (
        select(
            User,
            func.coalesce(jobs.c.jobs, 0).label("jobs"),
            func.coalesce(jobs.c.done, 0).label("done"),
            jobs.c.last_job,
            act.c.last_day,
        )
        .outerjoin(jobs, jobs.c.uid == User.id)
        .outerjoin(act, act.c.uid == User.id)
    )
    if q.strip():
        stmt = stmt.where(or_(User.email.like(_like(q), escape="\\"), User.id == q.strip()))
    if filter_ == "customers":
        stmt = stmt.where(User.is_internal.is_(False))
    elif filter_ == "internal":
        stmt = stmt.where(User.is_internal.is_(True))
    elif filter_ == "blocked":
        stmt = stmt.where(User.is_blocked.is_(True))
    elif filter_ == "admins":
        stmt = stmt.where(User.is_admin.is_(True))
    if activity == "activated":
        stmt = stmt.where(func.coalesce(jobs.c.done, 0) > 0)
    elif activity == "unactivated":
        stmt = stmt.where(func.coalesce(jobs.c.jobs, 0) == 0)
    elif activity == "tried_failed":
        stmt = stmt.where(func.coalesce(jobs.c.jobs, 0) > 0, func.coalesce(jobs.c.done, 0) == 0)
    since = _since(range_)
    if since is not None:
        stmt = stmt.where(User.created_at >= since)
    return stmt


def _user_sort(stmt: Select, sort: UserSort) -> Select:
    cols = stmt.selected_columns
    order = {
        "newest": User.created_at.desc(),
        "oldest": User.created_at.asc(),
        "balance_desc": User.credit_balance.desc(),
        "balance_asc": User.credit_balance.asc(),
        "jobs_desc": cols.jobs.desc(),
        "last_active": cols.last_day.desc(),
    }[sort]
    return stmt.order_by(order, User.id)


def _user_row(user: User, jobs: int, done: int, last_job, last_day) -> UserRow:
    return UserRow(
        id=user.id,
        email=user.email,
        is_admin=user.is_admin,
        is_blocked=user.is_blocked,
        is_internal=user.is_internal,
        credit_balance=user.credit_balance,
        jobs=int(jobs),
        done=int(done),
        last_job_at=last_job,
        last_active=last_day,
        created_at=user.created_at,
    )


@router.get("/users")
async def list_users(
    _: AdminUser,
    session: Session,
    q: str = Query("", max_length=100),
    filter: UserFilter = "all",  # noqa: A002 - public query name
    activity: Activity = "all",
    range: Range = "all",  # noqa: A002
    sort: UserSort = "newest",
    page: int = Query(1, ge=1, le=10_000),
    limit: int = Query(25, ge=1, le=100),
):
    base = _users_query(q, filter, activity, range)
    total = (await session.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
    rows = await session.execute(_user_sort(base, sort).limit(limit).offset((page - 1) * limit))
    return {"total": total, "page": page, "items": [_user_row(*r) for r in rows.all()]}


@router.get("/users/{user_id}")
async def user_detail(user_id: str, _: AdminUser, session: Session):
    user = await session.get(User, user_id)
    if user is None:
        raise not_found()
    jobs = (
        await session.execute(
            select(Job).where(Job.user_id == user_id).order_by(Job.created_at.desc()).limit(20)
        )
    ).scalars()
    ledger = (
        await session.execute(
            select(CreditLedger)
            .where(CreditLedger.user_id == user_id)
            .order_by(CreditLedger.created_at.desc())
            .limit(20)
        )
    ).scalars()
    moderation = dict(
        (
            await session.execute(
                select(ModerationEvent.category, func.count(ModerationEvent.id))
                .where(ModerationEvent.user_id == user_id)
                .group_by(ModerationEvent.category)
            )
        ).all()
    )
    days = (
        await session.execute(
            select(func.count(UserActivity.id), func.max(UserActivity.day)).where(
                UserActivity.user_id == user_id
            )
        )
    ).one()
    keys = (
        await session.execute(select(ProviderKey.provider).where(ProviderKey.user_id == user_id))
    ).scalars()
    assets = (
        await session.execute(
            select(func.count(Asset.id), func.coalesce(func.sum(Asset.size_bytes), 0)).where(
                Asset.user_id == user_id
            )
        )
    ).one()
    return {
        "user": {
            "id": user.id,
            "email": user.email,
            "locale": user.locale,
            "is_admin": user.is_admin,
            "is_blocked": user.is_blocked,
            "is_internal": user.is_internal,
            "credit_balance": user.credit_balance,
            "created_at": user.created_at,
        },
        "active_days": days[0],
        "last_active": days[1],
        "provider_keys": list(keys),  # names only, never the secrets
        "assets": {"count": assets[0], "bytes": int(assets[1])},
        "moderation": moderation,
        "jobs": [_job_row(j, user.email).model_dump(mode="json") for j in jobs],
        "ledger": [
            {
                "delta": e.delta,
                "reason": e.reason,
                "balance_after": e.balance_after,
                "created_at": e.created_at,
            }
            for e in ledger
        ],
    }


async def _target(session, admin: User, user_id: str, allow_self: bool = False) -> User:
    target = await session.get(User, user_id)
    if target is None:
        raise not_found()
    if target.id == admin.id and not allow_self:
        # Never lock yourself out (or demote yourself) from the panel.
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail={"code": "cannot_target_self"})
    return target


@router.post("/users/{user_id}/block")
async def block_user(user_id: str, body: BlockIn, admin: AdminUser, session: Session):
    target = await _target(session, admin, user_id)
    target.is_blocked = body.blocked
    if body.blocked:
        await session.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=utcnow())
        )
    await _audit(session, admin, "user.block", user_id, blocked=body.blocked)
    await session.commit()
    return {"id": target.id, "blocked": target.is_blocked}


@router.post("/users/{user_id}/admin")
async def set_admin(user_id: str, body: FlagIn, admin: AdminUser, session: Session):
    target = await _target(session, admin, user_id)
    target.is_admin = body.value
    await _audit(session, admin, "user.admin", user_id, admin=body.value)
    await session.commit()
    return {"id": target.id, "is_admin": target.is_admin}


@router.post("/users/{user_id}/internal")
async def set_internal(user_id: str, body: FlagIn, admin: AdminUser, session: Session):
    target = await _target(session, admin, user_id, allow_self=True)
    target.is_internal = body.value
    await _audit(session, admin, "user.internal", user_id, internal=body.value)
    await session.commit()
    return {"id": target.id, "is_internal": target.is_internal}


@router.post("/users/{user_id}/credits")
async def change_credits(user_id: str, body: CreditsIn, admin: AdminUser, session: Session):
    if await session.get(User, user_id) is None:
        raise not_found()
    delta = body.amount if body.mode == "add" else -body.amount
    reason = "admin_grant" if delta > 0 else "admin_deduct"
    try:
        entry = await credits.apply(
            session, user_id, delta, reason, f"admin:{user_id}:{body.mode}:{body.note_id}"
        )
    except credits.InsufficientCredits:
        await session.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail={"code": "insufficient_credits"}
        ) from None
    await _audit(session, admin, f"credits.{body.mode}", user_id, amount=body.amount)
    await session.commit()
    return {"balance": entry.balance_after}


# --- payments (read-only) ---------------------------------------------------------------------


@router.get("/payments")
async def list_payments(
    _: AdminUser,
    session: Session,
    status_filter: PaymentStatus | None = Query(None, alias="status"),
    q: str = Query("", max_length=100),
    page: int = Query(1, ge=1, le=10_000),
    limit: int = Query(25, ge=1, le=100),
):
    """Payment orders + revenue totals (paid orders only). No changes possible from here."""
    stmt = select(PaymentOrder, User.email).outerjoin(User, User.id == PaymentOrder.user_id)
    if status_filter is not None:
        stmt = stmt.where(PaymentOrder.status == status_filter)
    if q.strip():
        stmt = stmt.where(or_(User.email.like(_like(q), escape="\\"), PaymentOrder.id == q.strip()))
    total = (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    rows = await session.execute(
        stmt.order_by(PaymentOrder.created_at.desc()).limit(limit).offset((page - 1) * limit)
    )
    items = [
        {
            "id": o.id,
            "user_email": email,
            "pack_id": o.pack_id,
            "credits": o.credits,
            "amount_uzs": o.amount_uzs,
            "provider": o.provider,
            "provider_order_id": o.provider_order_id,
            "provider_txn_id": o.provider_txn_id,
            "status": o.status,
            "created_at": as_utc(o.created_at),
            "paid_at": as_utc(o.paid_at) if o.paid_at else None,
        }
        for o, email in rows.all()
    ]

    async def revenue(since: datetime | None) -> dict:
        r = select(
            func.count(PaymentOrder.id),
            func.coalesce(func.sum(PaymentOrder.amount_uzs), 0),
            func.coalesce(func.sum(PaymentOrder.credits), 0),
        ).where(PaymentOrder.status == PaymentStatus.paid)
        if since is not None:
            r = r.where(PaymentOrder.paid_at >= since)
        n, amount, credits_ = (await session.execute(r)).one()
        return {"orders": n, "amount_uzs": int(amount), "credits": int(credits_)}

    by_status = dict(
        (
            await session.execute(
                select(PaymentOrder.status, func.count(PaymentOrder.id)).group_by(
                    PaymentOrder.status
                )
            )
        ).all()
    )
    return {
        "total": total,
        "page": page,
        "items": items,
        "revenue": {
            "today": await revenue(_since("today")),
            "30d": await revenue(_since("30d")),
            "all": await revenue(None),
        },
        "by_status": by_status,
    }


# --- jobs --------------------------------------------------------------------------------------


def _job_row(job: Job, email: str | None) -> JobRow:
    seconds = None
    if job.started_at and job.finished_at:
        seconds = round((as_utc(job.finished_at) - as_utc(job.started_at)).total_seconds(), 1)
    return JobRow(
        id=job.id,
        user_id=job.user_id,
        user_email=email,
        kind="upscale" if job.provider == "local" else job.kind,
        provider=job.provider,
        model=job.model,
        status=str(job.status),
        count=job.count,
        cost=job.cost,
        attempts=job.attempts,
        upscale=(job.params or {}).get("upscale"),
        error=job.error,
        created_at=job.created_at,
        seconds=seconds,
    )


def _jobs_query(
    status_: JobStatus | None,
    kind: str | None,
    provider: str | None,
    q: str,
    range_: Range,
    include_internal: bool,
) -> Select:
    stmt = select(Job, User.email).outerjoin(User, User.id == Job.user_id)
    if status_ is not None:
        stmt = stmt.where(Job.status == status_)
    if kind == "upscale":
        stmt = stmt.where(Job.provider == "local")
    elif kind:
        stmt = stmt.where(Job.kind == kind, Job.provider != "local")
    if provider:
        stmt = stmt.where(Job.provider == provider)
    if q.strip():
        stmt = stmt.where(or_(User.email.like(_like(q), escape="\\"), Job.id == q.strip()))
    since = _since(range_)
    if since is not None:
        stmt = stmt.where(Job.created_at >= since)
    if not include_internal:
        stmt = stmt.where(or_(User.is_internal.is_(False), User.id.is_(None)))
    return stmt


@router.get("/jobs")
async def list_jobs(
    _: AdminUser,
    session: Session,
    status_filter: JobStatus | None = Query(None, alias="status"),
    kind: Literal["image", "video", "upscale"] | None = None,
    provider: str | None = Query(None, max_length=32),
    q: str = Query("", max_length=100),
    range: Range = "7d",  # noqa: A002
    include_internal: bool = False,
    page: int = Query(1, ge=1, le=10_000),
    limit: int = Query(25, ge=1, le=100),
):
    base = _jobs_query(status_filter, kind, provider, q, range, include_internal)
    total = (await session.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
    rows = await session.execute(
        base.order_by(Job.created_at.desc()).limit(limit).offset((page - 1) * limit)
    )
    return {"total": total, "page": page, "items": [_job_row(j, e) for j, e in rows.all()]}


@router.get("/jobs/errors")
async def job_errors(_: AdminUser, session: Session, days: int = Query(7, ge=1, le=90)):
    """Most frequent failure reasons, to spot a broken provider or bad config quickly."""
    rows = await session.execute(
        select(Job.provider, Job.error, func.count(Job.id), func.max(Job.created_at))
        .where(
            Job.error.is_not(None),
            Job.created_at >= datetime.now(UTC) - timedelta(days=days),
        )
        .group_by(Job.provider, Job.error)
        .order_by(func.count(Job.id).desc())
        .limit(20)
    )
    return [
        {"provider": p, "error": e, "count": n, "last_at": last} for p, e, n, last in rows.all()
    ]


@router.post("/jobs/{job_id}/cancel")
async def cancel_job(job_id: str, admin: AdminUser, session: Session):
    """Cancel a queued job and refund it. Running jobs finish (or time out) on their own."""
    job = await session.get(Job, job_id)
    if job is None:
        raise not_found()
    result = await session.execute(
        update(Job)
        .where(Job.id == job_id, Job.status == JobStatus.queued)
        .values(
            status=JobStatus.failed, error="Cancelled by an administrator", finished_at=utcnow()
        )
    )
    if result.rowcount != 1:
        await session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, detail={"code": "job_not_queued"})
    if job.cost > 0:
        await credits.apply(
            session, job.user_id, job.cost, "refund", f"refund:{job.id}", job_id=job.id
        )
    await _audit(session, admin, "job.cancel", job_id)
    await session.commit()
    return {"id": job_id, "status": "failed"}


@router.post("/jobs/{job_id}/retry")
async def retry_job(job_id: str, admin: AdminUser, session: Session):
    """Re-queue a failed job for free (it was already refunded)."""
    result = await session.execute(
        update(Job)
        .where(Job.id == job_id, Job.status == JobStatus.failed)
        .values(status=JobStatus.queued, error=None, started_at=None, finished_at=None, cost=0)
    )
    if result.rowcount != 1:
        await session.rollback()
        if await session.get(Job, job_id) is None:
            raise not_found()
        raise HTTPException(status.HTTP_409_CONFLICT, detail={"code": "job_not_failed"})
    await _audit(session, admin, "job.retry", job_id)
    await session.commit()
    return {"id": job_id, "status": "queued"}


# --- moderation & reports ----------------------------------------------------------------------


@router.get("/moderation")
async def moderation(_: AdminUser, session: Session, days: int = Query(30, ge=1, le=365)):
    since = datetime.now(UTC) - timedelta(days=days)
    by_category = dict(
        (
            await session.execute(
                select(ModerationEvent.category, func.count(ModerationEvent.id))
                .where(ModerationEvent.created_at >= since)
                .group_by(ModerationEvent.category)
            )
        ).all()
    )
    top = await session.execute(
        select(
            ModerationEvent.user_id,
            User.email,
            User.is_blocked,
            func.count(ModerationEvent.id),
            func.max(ModerationEvent.created_at),
            func.sum(case((ModerationEvent.category == "minors", 1), else_=0)),
        )
        .join(User, User.id == ModerationEvent.user_id)
        .where(ModerationEvent.created_at >= since)
        .group_by(ModerationEvent.user_id, User.email, User.is_blocked)
        .order_by(func.count(ModerationEvent.id).desc())
        .limit(25)
    )
    return {
        "days": days,
        "by_category": by_category,
        "users": [
            {
                "user_id": uid,
                "email": email,
                "blocked": blocked,
                "events": n,
                "minors_events": int(minors or 0),
                "last_at": last,
            }
            for uid, email, blocked, n, last, minors in top.all()
        ],
    }


@router.get("/reports")
async def list_reports(_: AdminUser, session: Session):
    rows = (
        await session.execute(
            select(Report, Asset.user_id, Asset.mime, User.email)
            .outerjoin(Asset, Asset.id == Report.asset_id)
            .outerjoin(User, User.id == Asset.user_id)
            .where(Report.status == "open")
            .order_by(Report.created_at)
            .limit(100)
        )
    ).all()
    return [
        {
            "id": r.id,
            "asset_id": r.asset_id,
            "asset_owner_id": owner,
            "asset_owner_email": email,
            "asset_mime": mime,
            "asset_url": f"/api/admin/assets/{r.asset_id}/file" if r.asset_id else None,
            "reason": r.reason,
            "details": r.details,
            "created_at": r.created_at,
        }
        for r, owner, mime, email in rows
    ]


@router.post("/reports/{report_id}/dismiss")
async def dismiss_report(report_id: str, admin: AdminUser, session: Session):
    report = await session.get(Report, report_id)
    if report is None:
        raise not_found()
    report.status = "dismissed"
    await _audit(session, admin, "report.dismiss", report_id)
    await session.commit()
    return {"id": report_id, "status": "dismissed"}


@router.get("/assets/{asset_id}/file")
async def admin_asset_file(asset_id: str, _: AdminUser, session: Session):
    """Lets moderators view reported content (owner-only elsewhere)."""
    asset = await session.get(Asset, asset_id)
    if asset is None:
        raise not_found()
    path = asset_path(asset.preview_key or asset.storage_key)
    if not path.exists():
        raise not_found()
    return FileResponse(path, media_type=asset.mime, headers={"Cache-Control": "no-store"})


@router.delete("/assets/{asset_id}", status_code=204)
async def remove_asset(asset_id: str, admin: AdminUser, session: Session) -> None:
    asset = await session.get(Asset, asset_id)
    if asset is None:
        raise not_found()
    keys = (asset.storage_key, asset.preview_key)
    await session.execute(
        update(Report).where(Report.asset_id == asset_id).values(status="actioned")
    )
    await session.delete(asset)
    await _audit(session, admin, "asset.remove", asset_id)
    await session.commit()
    delete_stored(*keys)


# --- providers ---------------------------------------------------------------------------------


@router.get("/providers")
async def provider_limits(_: AdminUser, session: Session):
    """Learned limits for shared scopes (server key, anonymous); per-user rows are counted."""
    rows = (await session.execute(select(ProviderQuota))).scalars().all()
    now = datetime.now(UTC)
    shared = [r for r in rows if not r.scope.startswith("user:")]
    return {
        "shared": [
            {
                "provider": r.provider,
                "scope": r.scope,
                "day": r.day,
                "used_today": r.used_today,
                "hits_today": r.hits_today,
                "estimated_limit": round(r.est_daily_limit) if r.est_daily_limit else None,
                "source": r.est_source,
                "observations": r.observations,
                "cooldown_s": round(r.cooldown_s),
                "blocked_seconds": max(0, int((as_utc(r.blocked_until) - now).total_seconds()))
                if r.blocked_until
                else 0,
            }
            for r in shared
        ],
        "user_scopes": len(rows) - len(shared),
    }


@router.post("/providers/{provider}/{scope}/reset")
async def reset_provider_cooldown(provider: str, scope: str, admin: AdminUser, session: Session):
    """Clear a learned cooldown (e.g. after upgrading a plan). The daily estimate is kept."""
    result = await session.execute(
        update(ProviderQuota)
        .where(ProviderQuota.provider == provider, ProviderQuota.scope == scope)
        .values(blocked_until=None, consecutive_hits=0, cooldown_s=quota.INITIAL_COOLDOWN)
    )
    if result.rowcount != 1:
        raise not_found()
    await _audit(session, admin, "provider.reset", f"{provider}:{scope}")
    await session.commit()
    return {"provider": provider, "scope": scope, "reset": True}


# --- announcements -----------------------------------------------------------------------------


def _announcement(a: Announcement) -> dict:
    return {
        "id": a.id,
        "level": a.level,
        "text_en": a.text_en,
        "text_uz": a.text_uz,
        "text_ru": a.text_ru,
        "active": a.active,
        "ends_at": a.ends_at,
        "created_at": a.created_at,
    }


@router.get("/announcements")
async def list_announcements(_: AdminUser, session: Session):
    rows = await session.execute(
        select(Announcement).order_by(Announcement.created_at.desc()).limit(50)
    )
    return [_announcement(a) for a in rows.scalars()]


@router.post("/announcements", status_code=201)
async def create_announcement(body: AnnouncementIn, admin: AdminUser, session: Session):
    a = Announcement(**body.model_dump(), created_by=admin.id)
    session.add(a)
    await session.flush()
    await _audit(session, admin, "announcement.create", a.id, level=body.level)
    await session.commit()
    return _announcement(a)


@router.patch("/announcements/{announcement_id}")
async def update_announcement(
    announcement_id: str, body: AnnouncementPatch, admin: AdminUser, session: Session
):
    a = await session.get(Announcement, announcement_id)
    if a is None:
        raise not_found()
    a.active = body.active
    await _audit(session, admin, "announcement.active", a.id, active=body.active)
    await session.commit()
    return _announcement(a)


@router.delete("/announcements/{announcement_id}", status_code=204)
async def delete_announcement(announcement_id: str, admin: AdminUser, session: Session) -> None:
    result = await session.execute(delete(Announcement).where(Announcement.id == announcement_id))
    if result.rowcount != 1:
        raise not_found()
    await _audit(session, admin, "announcement.delete", announcement_id)
    await session.commit()


@public.get("/announcements")
async def active_announcements(_: CurrentUser, session: Session):
    """Banners for signed-in users (React escapes the text; no HTML is rendered)."""
    now = datetime.now(UTC)
    rows = await session.execute(
        select(Announcement)
        .where(Announcement.active.is_(True))
        .order_by(Announcement.created_at.desc())
        .limit(3)
    )
    out = []
    for a in rows.scalars():
        if a.ends_at is None or as_utc(a.ends_at) > now:
            out.append(
                {k: v for k, v in _announcement(a).items() if k not in ("active", "created_at")}
            )
    return out


# --- audit & exports ---------------------------------------------------------------------------


@router.get("/audit")
async def audit_log(_: AdminUser, session: Session, limit: int = Query(100, ge=1, le=500)):
    rows = await session.execute(
        select(AdminAudit, User.email)
        .outerjoin(User, User.id == AdminAudit.admin_id)
        .order_by(AdminAudit.created_at.desc())
        .limit(limit)
    )
    return [
        {
            "id": a.id,
            "admin_email": email,
            "action": a.action,
            "target": a.target,
            "details": a.details,
            "created_at": a.created_at,
        }
        for a, email in rows.all()
    ]


def _csv_cell(value) -> str:
    """Neutralise spreadsheet formulas (CSV injection): =, +, -, @, tab, CR."""
    text = "" if value is None else str(value)
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


def _csv_response(name: str, header: list[str], rows: list[list]) -> StreamingResponse:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(header)
    for row in rows:
        writer.writerow([_csv_cell(v) for v in row])
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M")
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="aurevid-{name}-{stamp}.csv"'},
    )


@router.get("/export/users.csv")
async def export_users(
    admin: AdminUser,
    session: Session,
    filter: UserFilter = "all",  # noqa: A002
    activity: Activity = "all",
):
    rows = await session.execute(
        _user_sort(_users_query("", filter, activity, "all"), "newest").limit(50_000)
    )
    await _audit(session, admin, "export.users", None, filter=filter, activity=activity)
    await session.commit()
    data = [
        [
            u.id,
            u.email,
            u.created_at,
            u.credit_balance,
            jobs,
            done,
            last_day,
            u.is_internal,
            u.is_blocked,
            u.is_admin,
        ]  # fmt: skip
        for u, jobs, done, _last_job, last_day in rows.all()
    ]
    return _csv_response(
        "users",
        [
            "id",
            "email",
            "created_at",
            "balance",
            "jobs",
            "done",
            "last_active",
            "internal",
            "blocked",
            "admin",
        ],  # fmt: skip
        data,
    )


@router.get("/export/jobs.csv")
async def export_jobs(
    admin: AdminUser,
    session: Session,
    range: Range = "30d",
    include_internal: bool = False,  # noqa: A002
):
    rows = await session.execute(
        _jobs_query(None, None, None, "", range, include_internal)
        .order_by(Job.created_at.desc())
        .limit(50_000)
    )
    await _audit(session, admin, "export.jobs", None, range=range)
    await session.commit()
    data = []
    for job, email in rows.all():
        r = _job_row(job, email)
        data.append([r.id, r.created_at, r.user_email, r.kind, r.provider, r.model, r.status,
                     r.cost, r.upscale, r.seconds, r.error])  # fmt: skip
    return _csv_response(
        "jobs",
        [
            "id",
            "created_at",
            "user",
            "kind",
            "provider",
            "model",
            "status",
            "cost",
            "upscale",
            "seconds",
            "error",
        ],  # fmt: skip
        data,
    )
