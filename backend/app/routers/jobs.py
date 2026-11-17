# SPDX-License-Identifier: AGPL-3.0-or-later
"""Generation jobs: create (debits credits), list history, get status (poll or SSE)."""

import asyncio
import json
from datetime import UTC, datetime

from fastapi import APIRouter, Header, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app import db
from app.config import get_settings
from app.deps import CurrentUser, Session, not_found
from app.models import Asset, Job, JobStatus, new_id
from app.moderation import moderator
from app.providers.base import dimensions
from app.providers.registry import get_provider, resolve_credentials
from app.ratelimit import hit
from app.schemas import AssetOut, JobCreateIn, JobOut
from app.services import credits
from app.services.presets import load_presets

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


def asset_out(asset: Asset) -> AssetOut:
    out = AssetOut.model_validate(asset)
    out.url = f"/api/assets/{asset.id}/file"
    return out


async def job_out(session, job: Job) -> JobOut:
    assets = (
        (
            await session.execute(
                select(Asset).where(Asset.job_id == job.id).order_by(Asset.created_at)
            )
        )
        .scalars()
        .all()
    )
    out = JobOut.model_validate(job)
    out.assets = [asset_out(a) for a in assets]
    out.params = {k: v for k, v in (job.params or {}).items() if k != "final_prompt"}
    return out


def _bad(code: str, http: int = status.HTTP_400_BAD_REQUEST) -> HTTPException:
    return HTTPException(http, detail={"code": code})


@router.post("", response_model=JobOut, status_code=201)
async def create_job(
    body: JobCreateIn,
    user: CurrentUser,
    session: Session,
    idempotency_key: str | None = Header(default=None, max_length=64),
):
    hit("jobs-user", user.id, "10/minute")

    if idempotency_key:
        existing = (
            await session.execute(
                select(Job).where(Job.user_id == user.id, Job.client_request_id == idempotency_key)
            )
        ).scalar_one_or_none()
        if existing is not None:
            return await job_out(session, existing)

    verdict = moderator.check_prompt(body.prompt)
    if not verdict.allowed:
        raise _bad("prompt_rejected")

    provider = get_provider(body.provider)
    model = provider.model(body.model) if provider else None
    if provider is None or model is None:
        raise _bad("unknown_model")
    if body.aspect_ratio not in model.aspect_ratios:
        raise _bad("aspect_ratio_unsupported")
    if body.count > model.max_count:
        raise _bad("count_too_high")
    creds = await resolve_credentials(session, provider, user.id)
    if not provider.has_usable_credentials(creds):
        raise _bad("provider_key_required")

    final_prompt = body.prompt
    if body.preset_id:
        preset = load_presets().get(body.preset_id)
        if preset is None:
            raise _bad("unknown_preset")
        final_prompt = preset.render(body.prompt)
    if not moderator.check_prompt(final_prompt).allowed:
        raise _bad("prompt_rejected")

    start_of_day = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    jobs_today = (
        await session.execute(
            select(func.count(Job.id)).where(Job.user_id == user.id, Job.created_at >= start_of_day)
        )
    ).scalar_one()
    if jobs_today >= get_settings().daily_job_limit:
        raise _bad("daily_limit_reached", status.HTTP_429_TOO_MANY_REQUESTS)

    width, height = dimensions(body.aspect_ratio, body.size)
    job_id = new_id()
    cost = model.credit_cost * body.count
    job = Job(
        id=job_id,
        user_id=user.id,
        client_request_id=idempotency_key,
        provider=provider.info.id,
        model=model.id,
        prompt=body.prompt,
        preset_id=body.preset_id,
        count=body.count,
        cost=cost,
        params={
            "aspect_ratio": body.aspect_ratio,
            "size": body.size,
            "width": width,
            "height": height,
            "seed": body.seed,
            "final_prompt": final_prompt,
        },
    )
    session.add(job)
    try:
        await session.flush()
        if cost > 0:
            # Debit and job insert commit together, or not at all.
            await credits.apply(session, user.id, -cost, "generation", f"job:{job_id}", job_id)
        await session.commit()
    except credits.InsufficientCredits:
        await session.rollback()
        raise _bad("insufficient_credits", status.HTTP_402_PAYMENT_REQUIRED) from None
    except IntegrityError:
        await session.rollback()
        raise _bad("duplicate_request", status.HTTP_409_CONFLICT) from None
    return await job_out(session, job)


@router.get("", response_model=list[JobOut])
async def list_jobs(
    user: CurrentUser,
    session: Session,
    limit: int = Query(default=20, ge=1, le=50),
    before: datetime | None = None,
    favorites: bool = False,
):
    stmt = select(Job).where(Job.user_id == user.id)
    if before is not None:
        stmt = stmt.where(Job.created_at < before)
    if favorites:
        fav_jobs = select(Asset.job_id).where(Asset.user_id == user.id, Asset.is_favorite)
        stmt = stmt.where(Job.id.in_(fav_jobs))
    jobs = (await session.execute(stmt.order_by(Job.created_at.desc()).limit(limit))).scalars()
    return [await job_out(session, j) for j in jobs]


async def _owned_job(session, user_id: str, job_id: str) -> Job:
    job = await session.get(Job, job_id)
    if job is None or job.user_id != user_id:
        raise not_found()
    return job


@router.get("/{job_id}", response_model=JobOut)
async def get_job(job_id: str, user: CurrentUser, session: Session):
    return await job_out(session, await _owned_job(session, user.id, job_id))


@router.get("/{job_id}/events")
async def job_events(job_id: str, user: CurrentUser, session: Session):
    """Server-Sent Events stream of job status until it finishes (max ~3 minutes)."""
    await _owned_job(session, user.id, job_id)
    user_id = user.id
    await session.close()  # release the request transaction; the stream opens its own

    async def stream():
        last = None
        for _ in range(180):
            async with db.session_factory()() as s:
                job = await s.get(Job, job_id)
                if job is None or job.user_id != user_id:
                    return
                payload = (await job_out(s, job)).model_dump(mode="json")
            if payload["status"] != last or payload["status"] in (JobStatus.done, JobStatus.failed):
                last = payload["status"]
                yield f"event: job\ndata: {json.dumps(payload)}\n\n"
            if last in (JobStatus.done, JobStatus.failed):
                return
            await asyncio.sleep(1)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )
