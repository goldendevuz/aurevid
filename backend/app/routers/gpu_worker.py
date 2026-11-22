# SPDX-License-Identifier: AGPL-3.0-or-later
"""Bring-your-own-GPU: a remote worker (deploy/gpu-worker) claims and finishes video jobs.

Not a user API. It is authenticated by one shared bearer token (GPU_WORKER_TOKEN, compared in
constant time), exempt from the cookie CSRF check (see main.py) and rate limited per IP. The
worker is trusted with prompts and start images of jobs it claims, which is why only the owner's
machine should hold the token. A claim is a lease (``gpu_worker_lease_seconds`` from
``Job.started_at``): when it runs out, worker.requeue_expired_leases() puts the job back.
"""

import hmac
import logging
import secrets
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import select, update

from app.config import get_settings
from app.deps import Session
from app.images import (
    InvalidImageError,
    delete_stored,
    image_for_provider,
    store_video_file,
    tmp_dir,
)
from app.models import Asset, Job, JobStatus
from app.providers import gpu_worker as gw
from app.ratelimit import client_ip, hit
from app.services import recipes, stories
from app.worker import finish_job, requeue_expired_leases

log = logging.getLogger("aurevid.gpu_worker")

PREFIX = "/api/gpu-worker"
MAX_FAIL_LOG_CHARS = 300


def authenticate(request: Request, authorization: str | None = Header(default=None)) -> None:
    """Off (404) without a configured token; otherwise a constant-time bearer check."""
    token = get_settings().gpu_worker_token
    if not token:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    ip = client_ip(request)
    hit("gpu-worker", f"ip:{ip}", "300/minute")
    scheme, _, given = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not hmac.compare_digest(
        given.strip().encode(), token.encode()
    ):
        hit("gpu-worker-auth-fail", f"ip:{ip}", "10/minute")  # slows token guessing
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail={"code": "unauthorized"},
            headers={"WWW-Authenticate": "Bearer"},
        )


router = APIRouter(prefix=PREFIX, tags=["gpu-worker"], dependencies=[Depends(authenticate)])


class FailIn(BaseModel):
    message: str = Field(default="", max_length=2000)


def _lease_until(job: Job) -> datetime:
    started = job.started_at or datetime.now(UTC)
    return started + timedelta(seconds=get_settings().gpu_worker_lease_seconds)


async def _running_job(session, job_id: str) -> Job:
    job = await session.get(Job, job_id)
    if job is None or job.provider != gw.PROVIDER_ID:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"code": "not_found"})
    if job.status != JobStatus.running:
        raise HTTPException(status.HTTP_409_CONFLICT, detail={"code": "not_running"})
    return job


@router.post("/claim")
async def claim(session: Session):
    """Lease the oldest queued job; 204 when there is nothing to do."""
    await requeue_expired_leases()
    for _ in range(3):  # another worker may win the race for the same row
        job = (
            await session.execute(
                select(Job)
                .where(Job.provider == gw.PROVIDER_ID, Job.status == JobStatus.queued)
                .order_by(Job.created_at)
                .limit(1)
            )
        ).scalar_one_or_none()
        if job is None:
            return Response(status_code=status.HTTP_204_NO_CONTENT)
        won = await session.execute(
            update(Job)
            .where(Job.id == job.id, Job.status == JobStatus.queued)
            .values(
                status=JobStatus.running, started_at=datetime.now(UTC), attempts=Job.attempts + 1
            )
        )
        await session.commit()
        if won.rowcount == 1:
            await session.refresh(job)
            return _claim_body(job)
        session.expire_all()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _claim_body(job: Job) -> dict:
    params = job.params or {}
    width, height = gw.SIZES.get(params.get("aspect_ratio", ""), gw.SIZES["16:9"])
    seed = params.get("seed")
    return {
        "job_id": job.id,
        "prompt": params.get("final_prompt", job.prompt),
        "width": width,
        "height": height,
        "frames": gw.FRAMES.get(params.get("duration") or 5, gw.FRAMES[5]),
        "fps": gw.FPS,
        "seed": seed if isinstance(seed, int) else secrets.randbelow(2**31),
        "image_url": f"{PREFIX}/{job.id}/image" if params.get("image_asset_id") else None,
        "lease_until": _lease_until(job).isoformat(),
    }


@router.get("/{job_id}/image")
async def start_image(job_id: str, session: Session):
    """The start frame (JPEG) of a job this worker currently holds; gone once the lease ends."""
    job = await _running_job(session, job_id)
    asset_id = (job.params or {}).get("image_asset_id")
    asset = await session.get(Asset, asset_id) if asset_id else None
    if asset is None or asset.user_id != job.user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"code": "not_found"})
    try:
        data = image_for_provider(asset.storage_key)
    except (OSError, InvalidImageError):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"code": "not_found"}) from None
    return Response(data, media_type="image/jpeg", headers={"Cache-Control": "no-store"})


@router.post("/{job_id}/complete", status_code=201)
async def complete(job_id: str, file: UploadFile, session: Session):
    """Receive the finished mp4: same checks and storage as any provider's video."""
    job = await _running_job(session, job_id)
    max_bytes = get_settings().max_video_bytes
    part = tmp_dir() / f"{secrets.token_hex(8)}.part"
    size = 0
    try:
        with part.open("wb") as out:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > max_bytes:
                    raise HTTPException(
                        status.HTTP_413_CONTENT_TOO_LARGE, detail={"code": "file_too_large"}
                    )
                out.write(chunk)
        params = job.params or {}
        try:
            stored = store_video_file(part, params["width"], params["height"])
        except InvalidImageError:
            raise HTTPException(
                status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail={"code": "invalid_video"}
            ) from None
    finally:
        part.unlink(missing_ok=True)
    # Conditional flip: if the lease expired and the job moved on meanwhile, this loses cleanly.
    won = await session.execute(
        update(Job)
        .where(Job.id == job.id, Job.status == JobStatus.running)
        .values(status=JobStatus.done, error=None, finished_at=datetime.now(UTC))
    )
    if won.rowcount != 1:
        await session.rollback()
        delete_stored(stored.storage_key, stored.preview_key)
        raise HTTPException(status.HTTP_409_CONFLICT, detail={"code": "not_running"})
    # The clip's own size replaces the expected one (what the UI shows is what the file is).
    job.params = {**(job.params or {}), "width": stored.width, "height": stored.height}
    session.add(
        Asset(
            user_id=job.user_id,
            job_id=job.id,
            source="generated",
            storage_key=stored.storage_key,
            mime=stored.mime,
            width=stored.width,
            height=stored.height,
            size_bytes=stored.size_bytes,
            preview_key=stored.preview_key,
        )
    )
    await session.commit()
    log.info("gpu job=%s done bytes=%d", job.id, stored.size_bytes)
    try:
        await recipes.advance(job.id)  # next step of a recipe chain, if any
    except Exception:  # noqa: BLE001 - a broken chain must not fail the upload
        log.exception("recipe advance failed job=%s", job.id)
    try:
        await stories.settle_for_job(job.id)  # last scene of a multi-scene video: join the clips
    except Exception:  # noqa: BLE001 - the janitor retries stories that were missed
        log.exception("story settle failed job=%s", job.id)
    return {"status": "done"}


@router.post("/{job_id}/fail")
async def fail(job_id: str, body: FailIn, session: Session):
    """The worker could not make the video: fail the job and refund through the normal path."""
    await _running_job(session, job_id)
    log.warning("gpu job=%s failed: %s", job_id, body.message[:MAX_FAIL_LOG_CHARS])
    await session.rollback()  # release our read transaction: finish_job writes in its own session
    # The worker's text is logged, never shown: users get a fixed, safe message.
    await finish_job(job_id, 0, "The GPU worker could not make this video")
    return {"status": "failed"}
