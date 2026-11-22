# SPDX-License-Identifier: AGPL-3.0-or-later
"""Generation jobs: create (debits credits), list history, get status (poll or SSE)."""

import asyncio
import json
from datetime import UTC, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Header, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app import db, upscaler
from app.config import get_settings
from app.deps import CurrentUser, Session, not_found
from app.images import delete_stored
from app.models import Asset, Job, JobStatus, ModerationEvent, new_id
from app.moderation import moderator
from app.providers.base import UPSCALE_CREDITS, fit_long_side, output_dimensions
from app.providers.registry import (
    allowed_upscales,
    get_provider,
    publish_image_model,
    resolve_credentials,
)
from app.ratelimit import hit
from app.schemas import AssetOut, FacetOut, JobCreateIn, JobFacetsOut, JobOut
from app.services import allowance, credits, queue, quota
from app.services.presets import load_presets

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


def asset_out(asset: Asset) -> AssetOut:
    out = AssetOut.model_validate(asset)
    out.url = f"/api/assets/{asset.id}/file"
    out.preview_url = f"/api/assets/{asset.id}/preview" if asset.preview_key else out.url
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
    provider = get_provider(job.provider)
    model = provider.model(job.model) if provider else None
    if provider:
        out.provider_name = provider.info.name
    if model:
        out.model_label, out.has_audio = model.label, model.has_audio
    if job.status == JobStatus.queued:
        out.queue_position, out.eta_seconds = await queue.position_and_eta(session, job)
    elif job.status == JobStatus.running:
        out.typical_seconds = await queue.typical_run_seconds(session, job)
    return out


def _bad(code: str, http: int = status.HTTP_400_BAD_REQUEST) -> HTTPException:
    return HTTPException(http, detail={"code": code})


async def _log_rejection(session, user_id: str, category: str | None) -> None:
    """Record the category only (never the prompt) so admins can spot repeat abuse."""
    session.add(ModerationEvent(user_id=user_id, category=category or "other"))
    await session.commit()


async def check_daily_limit(session, user_id: str) -> None:
    start_of_day = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    jobs_today = (
        await session.execute(
            select(func.count(Job.id)).where(Job.user_id == user_id, Job.created_at >= start_of_day)
        )
    ).scalar_one()
    if jobs_today >= get_settings().daily_job_limit:
        raise _bad("daily_limit_reached", status.HTTP_429_TOO_MANY_REQUESTS)


async def enqueue(session, job: Job) -> None:
    """Insert the job and debit its credits in one transaction, or neither."""
    session.add(job)
    try:
        await session.flush()
        if job.cost > 0:
            await credits.apply(
                session, job.user_id, -job.cost, "generation", f"job:{job.id}", job.id
            )
        await session.commit()
    except credits.InsufficientCredits:
        await session.rollback()
        raise _bad("insufficient_credits", status.HTTP_402_PAYMENT_REQUIRED) from None
    except IntegrityError:
        await session.rollback()
        raise _bad("duplicate_request", status.HTTP_409_CONFLICT) from None


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

    job = await prepare_job(session, user.id, body, idempotency_key)
    await enqueue(session, job)
    return await job_out(session, job)


async def prepare_job(
    session, user_id: str, body: JobCreateIn, client_request_id: str | None = None
) -> Job:
    """Validate a request with every user check (moderation, limits, keys, free share) and
    build the Job, unsaved. Raises HTTPException with a {"code": ...} detail when refused.
    Shared by POST /api/jobs and recipe chains (the worker creates the next step with it)."""
    verdict = moderator.check_prompt(body.prompt)
    if not verdict.allowed:
        await _log_rejection(session, user_id, verdict.category)
        raise _bad("prompt_rejected")

    provider = get_provider(body.provider)
    model = provider.model(body.model) if provider else None
    if provider is None or model is None:
        raise _bad("unknown_model")
    if body.aspect_ratio not in model.aspect_ratios:
        raise _bad("aspect_ratio_unsupported")
    if body.count > model.max_count:
        raise _bad("count_too_high")
    duration = None
    if model.kind == "video":
        duration = body.duration or model.durations[0]
        if duration not in model.durations:
            raise _bad("duration_unsupported")
    elif body.duration is not None:
        raise _bad("duration_unsupported")

    if body.upscale and body.upscale not in allowed_upscales(model):
        raise _bad("upscale_unsupported")

    resolution = None
    if model.resolutions:
        resolution = body.resolution or model.default_resolution or model.resolutions[0]
        if resolution not in model.resolutions:
            raise _bad("resolution_unsupported")
    elif body.resolution:
        raise _bad("resolution_unsupported")

    # "Publish quality": the best free, commercially allowed image model at its largest size,
    # then the local upscaler. One image at a time (CPU and free-share bounds).
    publish = body.quality == "publish"
    upscale = body.upscale
    if publish:
        chosen = publish_image_model()
        if (
            model.kind != "image"
            or body.image_asset_id
            or chosen is None
            or (provider.info.id, model.id) != (chosen[0].info.id, chosen[1].id)
        ):
            raise _bad("quality_unsupported")
        if body.count != 1:
            raise _bad("count_too_high")
        upscale = upscale or "2k"
        if upscale not in ("2k", "4k"):
            raise _bad("upscale_unsupported")

    if body.image_asset_id:
        if not model.accepts_image:
            raise _bad("image_input_unsupported")
        source = await session.get(Asset, body.image_asset_id)
        # Only the caller's own images can be animated (IDOR): not-yours looks like not-found.
        if source is None or source.user_id != user_id or not source.mime.startswith("image/"):
            raise not_found()
    elif model.requires_image:
        raise _bad("image_required")

    creds = await resolve_credentials(session, provider, user_id)
    if not provider.has_usable_credentials(creds):
        raise _bad("provider_key_required")
    if model.commercial_use == "byok_only" and creds.source != "user":
        raise _bad("provider_key_required")
    # What the provider really renders (not the Size label): what the UI shows and what we store.
    if publish:
        gen_w, gen_h = fit_long_side(body.aspect_ratio, model.publish_max_side or 1024)
    else:
        gen_w, gen_h = output_dimensions(model, body.aspect_ratio, body.size, resolution)
    width, height = gen_w, gen_h
    if (
        model.kind == "image"
        and upscale
        and upscaler.target_size((gen_w, gen_h), upscale)[0] > gen_w
    ):
        width, height = upscaler.target_size((gen_w, gen_h), upscale)
    weight = provider.quota_weight(model.id, gen_w, gen_h) if model.kind == "image" else 1
    if creds.source == "server":
        # The owner's key is shared: each user gets a fair free share (services/allowance.py).
        if not provider.server_allows(model.id, resolution):
            raise _bad("server_key_draft_only")
        needed = body.count * weight
        if provider.info.id in allowance.LIFETIME_PROVIDERS:
            if needed > await allowance.monthly_left(session, provider.info.id):
                raise _bad("free_month_used", status.HTTP_429_TOO_MANY_REQUESTS)
        left = await allowance.server_left(session, provider, user_id)
        if left is not None and needed > left:
            raise _bad("free_share_used", status.HTTP_429_TOO_MANY_REQUESTS)
    if provider.info.track_quota:
        q = await quota.view(
            session,
            provider.info.id,
            quota.scope_for(creds.source, user_id),
            provider.info.daily_quota_prior,
        )
        if q.blocked_seconds > 30:
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                detail={"code": "provider_cooldown", "retry_after": q.blocked_seconds},
                headers={"Retry-After": str(q.blocked_seconds)},
            )

    final_prompt = body.prompt
    if body.preset_id:
        preset = load_presets().get(body.preset_id)
        if preset is None:
            raise _bad("unknown_preset")
        final_prompt = preset.render(body.prompt, model.kind)
    preset_verdict = moderator.check_prompt(final_prompt)
    if not preset_verdict.allowed:
        await _log_rejection(session, user_id, preset_verdict.category)
        raise _bad("prompt_rejected")

    await check_daily_limit(session, user_id)
    await queue.admit(session, user_id)

    job_id = new_id()
    per_output = model.credit_cost + model.resolution_credits.get(resolution or "", 0)
    if upscale:
        per_output += UPSCALE_CREDITS[model.kind][upscale]
    cost = per_output * body.count
    estimated_usd = None
    if resolution and duration:
        rate = provider.usd_per_second(model.id, resolution, body.aspect_ratio)
        estimated_usd = round(rate * duration, 4) if rate is not None else None
    job = Job(
        id=job_id,
        user_id=user_id,
        client_request_id=client_request_id,
        kind=model.kind,
        provider=provider.info.id,
        model=model.id,
        prompt=body.prompt,
        preset_id=body.preset_id,
        count=body.count,
        cost=cost,
        key_source=creds.source,
        params={
            "aspect_ratio": body.aspect_ratio,
            "size": body.size,
            # Expected real output size; the worker replaces it with the file's own size.
            "width": width,
            "height": height,
            "gen_width": gen_w,  # what the provider is asked for (before any upscaling)
            "gen_height": gen_h,
            "seed": body.seed,
            "duration": duration,
            "image_asset_id": body.image_asset_id,
            "upscale": upscale,
            "final_prompt": final_prompt,
            **({"resolution": resolution} if resolution else {}),
            **({"quality": "publish"} if publish else {}),
            **({"quota_weight": weight} if weight > 1 else {}),
            **({"estimated_usd": estimated_usd} if estimated_usd is not None else {}),
        },
    )
    return job


HistoryKind = Literal["image", "video", "upscale"]
HistoryStatus = Literal["done", "failed", "active"]
HistoryPeriod = Literal["today", "7d", "30d", "all"]
ACTIVE = (JobStatus.queued, JobStatus.running)
PERIOD_DAYS = {"7d": 7, "30d": 30}


def _history_kind(provider: str, kind: str) -> str:
    """Local upscales are image jobs in the table but their own kind in History."""
    return "upscale" if provider == queue.LOCAL_PROVIDER else kind


def _history_status(job_status: str) -> str:
    return "active" if job_status in ACTIVE else str(job_status)


def _by_count(counts: dict) -> list:
    return sorted(counts.items(), key=lambda kv: (-kv[1], str(kv[0])))


def _like_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


@router.get("", response_model=list[JobOut])
async def list_jobs(
    user: CurrentUser,
    session: Session,
    limit: int = Query(default=20, ge=1, le=50),
    before: datetime | None = None,
    favorites: bool = False,
    kind: HistoryKind | None = None,
    job_status: HistoryStatus | None = Query(default=None, alias="status"),
    provider: str | None = Query(default=None, max_length=32),
    model: str | None = Query(default=None, max_length=64),
    period: HistoryPeriod | None = None,
    q: str | None = Query(default=None, max_length=200),
    hide_failed: bool = False,
):
    """Your history, newest first. Every filter is optional, combinable and owner-scoped."""
    # Scenes of a multi-scene video are shown through their story (routers/stories.py).
    stmt = select(Job).where(Job.user_id == user.id, Job.story_id.is_(None))
    if before is not None:
        stmt = stmt.where(Job.created_at < before)
    if favorites:
        fav_jobs = select(Asset.job_id).where(Asset.user_id == user.id, Asset.is_favorite)
        stmt = stmt.where(Job.id.in_(fav_jobs))
    if kind == "upscale":
        stmt = stmt.where(Job.provider == queue.LOCAL_PROVIDER)
    elif kind is not None:
        stmt = stmt.where(Job.kind == kind, Job.provider != queue.LOCAL_PROVIDER)
    if job_status == "active":
        stmt = stmt.where(Job.status.in_(ACTIVE))
    elif job_status is not None:
        stmt = stmt.where(Job.status == JobStatus(job_status))
    if hide_failed:
        stmt = stmt.where(Job.status != JobStatus.failed)
    if provider:
        stmt = stmt.where(Job.provider == provider)
    if model:
        stmt = stmt.where(Job.model == model)
    if period == "today":
        start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        stmt = stmt.where(Job.created_at >= start)
    elif period in PERIOD_DAYS:
        stmt = stmt.where(Job.created_at >= datetime.now(UTC) - timedelta(days=PERIOD_DAYS[period]))
    if q and q.strip():
        stmt = stmt.where(Job.prompt.ilike(f"%{_like_escape(q.strip())}%", escape="\\"))
    jobs = (await session.execute(stmt.order_by(Job.created_at.desc()).limit(limit))).scalars()
    return [await job_out(session, j) for j in jobs]


@router.get("/facets", response_model=JobFacetsOut)
async def job_facets(user: CurrentUser, session: Session):
    """Filter options built from your own jobs only, with counts."""
    rows = (
        await session.execute(
            select(Job.provider, Job.model, Job.kind, Job.status, func.count(Job.id))
            .where(Job.user_id == user.id, Job.story_id.is_(None))
            .group_by(Job.provider, Job.model, Job.kind, Job.status)
        )
    ).all()
    kinds: dict[str, int] = {}
    statuses: dict[str, int] = {}
    providers: dict[str, int] = {}
    models: dict[tuple[str, str], int] = {}
    for prov, mod, kind, st, n in rows:
        kinds[_history_kind(prov, kind)] = kinds.get(_history_kind(prov, kind), 0) + n
        statuses[_history_status(st)] = statuses.get(_history_status(st), 0) + n
        providers[prov] = providers.get(prov, 0) + n
        models[(prov, mod)] = models.get((prov, mod), 0) + n

    def provider_label(pid: str) -> str:
        p = get_provider(pid)
        return p.info.name if p else pid

    def model_label(pid: str, mid: str) -> str:
        p = get_provider(pid)
        m = p.model(mid) if p else None
        return m.label if m else mid.split("/")[-1]

    return JobFacetsOut(
        total=sum(statuses.values()),
        kinds=[FacetOut(value=k, count=n) for k, n in _by_count(kinds)],
        statuses=[FacetOut(value=k, count=n) for k, n in _by_count(statuses)],
        providers=[
            FacetOut(value=k, label=provider_label(k), count=n) for k, n in _by_count(providers)
        ],
        models=[
            FacetOut(value=m, provider=p, label=model_label(p, m), count=n)
            for (p, m), n in _by_count(models)
        ],
    )


async def _owned_job(session, user_id: str, job_id: str) -> Job:
    job = await session.get(Job, job_id)
    if job is None or job.user_id != user_id:
        raise not_found()
    return job


@router.get("/{job_id}", response_model=JobOut)
async def get_job(job_id: str, user: CurrentUser, session: Session):
    return await job_out(session, await _owned_job(session, user.id, job_id))


@router.delete("/{job_id}", status_code=204)
async def delete_job(job_id: str, user: CurrentUser, session: Session) -> None:
    """Remove one of your finished jobs together with its files (credits history is kept)."""
    job = await _owned_job(session, user.id, job_id)
    if job.status in ACTIVE:
        raise _bad("job_not_finished", status.HTTP_409_CONFLICT)
    if job.story_id:  # a scene belongs to its story: delete the story instead
        raise _bad("job_in_story", status.HTTP_409_CONFLICT)
    assets = (
        (
            await session.execute(
                select(Asset).where(Asset.job_id == job.id, Asset.user_id == user.id)
            )
        )
        .scalars()
        .all()
    )
    keys = [(a.storage_key, a.preview_key) for a in assets]
    for a in assets:
        await session.delete(a)
    await session.delete(job)
    await session.commit()
    for storage_key, preview_key in keys:
        delete_stored(storage_key, preview_key)


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
