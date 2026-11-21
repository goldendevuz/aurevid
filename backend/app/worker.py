# SPDX-License-Identifier: AGPL-3.0-or-later
"""DB-backed job queue worker. Works on SQLite and PostgreSQL without Redis.

Claiming is a conditional UPDATE (status='queued' -> 'running'), so two workers can never
process the same job. Run standalone with `python -m app.worker`, or inside the API process
(RUN_WORKER_IN_API=true) for single-container free hosting.
"""

import asyncio
import logging
import os
import secrets
import socket
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update

from app import db, upscaler
from app.config import get_settings
from app.images import (
    InvalidImageError,
    StoredImage,
    decode_image,
    delete_stored,
    image_for_provider,
    load_stored_image,
    save_image,
    store_video,
    store_video_file,
    tmp_dir,
)
from app.models import Asset, Job, JobStatus, WorkerHeartbeat
from app.providers.base import GenerationRequest, ProviderError
from app.providers.registry import get_provider, resolve_credentials
from app.services import allowance, credits, describe, queue, quota, recipes, stories
from app.services.payments import orders as payment_orders

log = logging.getLogger("aurevid.worker")


async def claim_next() -> Job | None:
    """Claim the next job in fair order that fits the resource caps (see services/queue.py)."""
    async with db.session_factory()() as session:
        queued = await queue.load(session, JobStatus.queued, limit=200, server_only=True)
        if not queued:
            return None
        running = await queue.load(session, JobStatus.running)
        job = queue.pick(queued, running)
        if job is None:
            return None  # everything waiting is blocked by a cap; try again shortly
        result = await session.execute(
            update(Job)
            .where(Job.id == job.id, Job.status == JobStatus.queued)
            .values(
                status=JobStatus.running, started_at=datetime.now(UTC), attempts=Job.attempts + 1
            )
        )
        await session.commit()
        if result.rowcount != 1:
            return None  # another worker won the race
        # Another worker may have claimed a job of the same class at the same moment.
        running = await queue.load(session, JobStatus.running)
        if queue.over_capacity(job, running):
            await session.execute(
                update(Job)
                .where(Job.id == job.id, Job.status == JobStatus.running)
                .values(status=JobStatus.queued, started_at=None, attempts=Job.attempts - 1)
            )
            await session.commit()
            return None
        await session.refresh(job)
        return job


async def finish_job(job_id: str, produced: int, error: str | None) -> None:
    async with db.session_factory()() as session:
        job = await session.get(Job, job_id)
        if job is None:
            return
        per_image = job.cost // max(1, job.count)
        unused = job.count - produced
        if unused > 0 and per_image > 0:
            await credits.apply(
                session,
                job.user_id,
                unused * per_image,
                "refund",
                f"refund:{job.id}",
                job_id=job.id,
            )
        job.status = JobStatus.done if produced > 0 else JobStatus.failed
        job.error = error  # kept for partial results too, so the UI can explain the refund
        job.finished_at = datetime.now(UTC)
        await session.commit()
    try:
        await recipes.advance(job_id)  # next step of a recipe chain, if any
    except Exception:  # noqa: BLE001 - a broken chain must not stop the worker
        log.exception("recipe advance failed job=%s", job_id)
    try:
        await stories.settle_for_job(job_id)  # last scene of a multi-scene video: join the clips
    except Exception:  # noqa: BLE001 - the janitor retries stories that were missed
        log.exception("story settle failed job=%s", job_id)


RETRY_DELAY_SECONDS = 6.0  # free tiers (e.g. Pollinations) throttle back-to-back requests


async def _generate_with_retry(provider, req: GenerationRequest, creds):
    s = get_settings()
    timeout = s.video_timeout_seconds if req.kind == "video" else s.job_timeout_seconds
    try:
        return await asyncio.wait_for(provider.generate(req, creds), timeout=timeout)
    except ProviderError as exc:
        if not exc.retryable:
            raise
        await asyncio.sleep(RETRY_DELAY_SECONDS)
        return await asyncio.wait_for(provider.generate(req, creds), timeout=timeout)


async def _quota_event(provider, scope: str, *, hit: bool) -> None:
    if not provider.info.track_quota:
        return
    async with db.session_factory()() as session:
        args = (session, provider.info.id, scope, provider.info.daily_quota_prior)
        if hit:
            await quota.record_quota_hit(*args)
        else:
            await quota.record_success(*args)
        await session.commit()


async def _wait_for_cooldown(provider, scope: str) -> bool:
    """Short cooldowns are waited out; long ones fail the job (credits refunded)."""
    if not provider.info.track_quota:
        return True
    async with db.session_factory()() as session:
        q = await quota.view(session, provider.info.id, scope, provider.info.daily_quota_prior)
    if q.blocked_seconds > MAX_COOLDOWN_WAIT:
        return False
    if q.blocked_seconds:
        await asyncio.sleep(q.blocked_seconds)
    return True


MAX_COOLDOWN_WAIT = 30
LOCAL_UPSCALE_PROVIDER = queue.LOCAL_PROVIDER
LOCAL_UPSCALE_MODEL = "realesr-general-x4v3"


async def _start_frame(job: Job) -> bytes | None:
    asset_id = (job.params or {}).get("image_asset_id")
    if not asset_id:
        return None
    async with db.session_factory()() as session:
        asset = await session.get(Asset, asset_id)
    if asset is None or asset.user_id != job.user_id:
        raise ProviderError("The start image was deleted")
    try:
        return image_for_provider(asset.storage_key)
    except (OSError, InvalidImageError) as exc:
        raise ProviderError("The start image could not be read") from exc


def _video_dims(width: int, height: int, target: str | None) -> tuple[int, int]:
    if not target:
        return width, height
    short = {"4k": 2160, "8k": 4320}[target]
    scale = short / min(width, height)
    return round(width * scale), round(height * scale)


async def _store_output(media, req: GenerationRequest, target: str | None) -> StoredImage:
    """Validate by content and store. Images are re-encoded (and upscaled locally if asked)."""
    if req.kind == "video":
        w, h = _video_dims(req.width, req.height, target)
        if media.path is not None:
            return await asyncio.to_thread(store_video_file, media.path, w, h)
        return store_video(media.data, w, h)
    img = decode_image(media.data, get_settings().max_provider_image_bytes)
    if target:
        img = await asyncio.to_thread(  # CPU-bound, off the event loop, with a hard deadline
            upscaler.upscale, img, target, get_settings().upscaler_timeout_seconds
        )
    return await asyncio.to_thread(save_image, img)


async def _process_local_upscale(job: Job) -> None:
    """Upscale-only job for an existing image (free, local Real-ESRGAN)."""
    params = job.params or {}
    error = None
    stored = None
    async with db.session_factory()() as session:
        source = await session.get(Asset, params.get("source_asset_id", ""))
    if source is None or source.user_id != job.user_id or not source.mime.startswith("image/"):
        error = "The source image was deleted"
    else:
        try:
            img = await asyncio.to_thread(load_stored_image, source.storage_key)
            img = await asyncio.to_thread(
                upscaler.upscale, img, params["upscale"], get_settings().upscaler_timeout_seconds
            )
            stored = await asyncio.to_thread(save_image, img)
        except upscaler.UpscaleTimeout:
            error = "Upscaling took too long, credits refunded"
        except (OSError, InvalidImageError, MemoryError):
            log.exception("local upscale failed job=%s", job.id)
            error = "Upscaling failed"
    if stored is not None:
        async with db.session_factory()() as session:
            if await session.get(Job, job.id) is None:
                delete_stored(stored.storage_key, stored.preview_key)
                return
            session.add(
                Asset(
                    user_id=job.user_id,
                    job_id=job.id,
                    source="generated",
                    storage_key=stored.storage_key,
                    preview_key=stored.preview_key,
                    mime=stored.mime,
                    width=stored.width,
                    height=stored.height,
                    size_bytes=stored.size_bytes,
                )
            )
            await session.commit()
    await finish_job(job.id, 1 if stored else 0, error)


async def _server_fallback(provider, job: Job, creds, remaining: int):
    """Server credentials when the user's own key failed and their free share covers the rest."""
    if creds.source != "user":
        return None
    server = provider.server_credentials()
    if server.source != "server" or not provider.has_usable_credentials(server):
        return None
    async with db.session_factory()() as session:
        row = await session.get(Job, job.id)
        if row is None:
            return None
        left = await allowance.server_left(session, provider, job.user_id, exclude_job_id=job.id)
        if left is not None and remaining > left:
            return None
        row.key_source = "server"  # from now on this job counts against the free share
        await session.commit()
    return server


async def process(job: Job) -> None:
    if job.provider == LOCAL_UPSCALE_PROVIDER:
        await _process_local_upscale(job)
        return
    provider = get_provider(job.provider)
    if provider is None:
        await finish_job(job.id, 0, "Provider is not available")
        return
    params = job.params or {}
    async with db.session_factory()() as session:
        creds = await resolve_credentials(session, provider, job.user_id)
    scope = quota.scope_for(creds.source, job.user_id)
    try:
        start_frame = await _start_frame(job)
    except ProviderError as exc:
        await finish_job(job.id, 0, exc.public)
        return
    produced = 0
    described: list[str] = []
    error: str | None = None
    base_seed = params.get("seed")
    for i in range(job.count):
        if not await _wait_for_cooldown(provider, scope):
            error = "Provider limit reached (estimated); try again later"
            break
        seed = (base_seed + i) if isinstance(base_seed, int) else secrets.randbelow(2**31)
        req = GenerationRequest(
            prompt=params.get("final_prompt", job.prompt),
            model=job.model,
            aspect_ratio=params["aspect_ratio"],
            width=params["width"],
            height=params["height"],
            seed=seed,
            kind="video" if job.kind == "video" else "image",
            size=params.get("size", "large"),
            duration_s=params.get("duration"),
            image=start_frame,
            upscale=params.get("upscale") if job.kind == "video" else None,
            workdir=tmp_dir(),
        )
        try:
            try:
                media = await _generate_with_retry(provider, req, creds)
            except ProviderError:
                fallback = await _server_fallback(provider, job, creds, job.count - produced)
                if fallback is None:
                    raise
                # The user's own key failed: finish on the owner's key within their free share.
                log.info("job=%s user key failed, using server key", job.id)
                creds, scope = fallback, quota.scope_for("server", job.user_id)
                media = await _generate_with_retry(provider, req, creds)
            stored = await _store_output(media, req, params.get("upscale"))
        except ProviderError as exc:
            if exc.quota:
                await _quota_event(provider, scope, hit=True)
            error = exc.public
            break
        except InvalidImageError:
            error = "Provider returned an invalid file"
            break
        except MemoryError:
            error = "Not enough memory to finish this resolution"
            break
        except TimeoutError:  # includes upscaler.UpscaleTimeout
            error = "Generation timed out"
            break
        except Exception:  # noqa: BLE001 - never leak internals to the user
            log.exception("unexpected provider failure job=%s", job.id)
            error = "Unexpected error"
            break
        await _quota_event(provider, scope, hit=False)
        async with db.session_factory()() as session:
            if await session.get(Job, job.id) is None:  # user deleted account meanwhile
                delete_stored(stored.storage_key, stored.preview_key)
                return
            asset = Asset(
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
            session.add(asset)
            await session.commit()
            if stored.mime.startswith("image/"):
                described.append(asset.id)
        produced += 1
    await finish_job(job.id, produced, error)
    for asset_id in described:  # after the job is done, so alt text never delays results
        await describe.describe_asset(asset_id)
    log.info("job=%s produced=%d status=%s", job.id, produced, "ok" if produced else "failed")


async def recover_stale() -> None:
    """Fail + refund jobs left 'running' by a crashed worker."""
    s = get_settings()
    stale_after = max(s.job_timeout_seconds * 5, s.video_timeout_seconds * 2)
    cutoff = datetime.now(UTC) - timedelta(seconds=stale_after)
    async with db.session_factory()() as session:
        stale = (
            (
                await session.execute(
                    select(Job.id).where(
                        Job.status == JobStatus.running,
                        Job.started_at < cutoff,
                        Job.provider.not_in(queue.REMOTE_PROVIDERS),  # these have leases
                    )
                )
            )
            .scalars()
            .all()
        )
    for job_id in stale:
        await finish_job(job_id, 0, "Interrupted, credits refunded")


async def requeue_expired_leases() -> int:
    """Remote (GPU worker) jobs whose lease ran out go back to the queue; after too many claims
    they fail instead (credits refunded), so a job that crashes every worker cannot loop."""
    s = get_settings()
    cutoff = datetime.now(UTC) - timedelta(seconds=s.gpu_worker_lease_seconds)
    async with db.session_factory()() as session:
        expired = (
            await session.execute(
                select(Job.id, Job.attempts).where(
                    Job.status == JobStatus.running,
                    Job.provider.in_(queue.REMOTE_PROVIDERS),
                    Job.started_at < cutoff,
                )
            )
        ).all()
        requeued = 0
        for job_id, attempts in expired:
            if attempts >= s.gpu_worker_max_attempts:
                continue
            result = await session.execute(
                update(Job)
                .where(Job.id == job_id, Job.status == JobStatus.running, Job.started_at < cutoff)
                .values(status=JobStatus.queued, started_at=None)
            )
            requeued += result.rowcount
        await session.commit()
    for job_id, attempts in expired:
        if attempts >= s.gpu_worker_max_attempts:
            await finish_job(job_id, 0, "The GPU worker did not finish, credits refunded")
    return requeued


async def run_once() -> bool:
    global _busy
    job = await claim_next()
    if job is None:
        return False
    _busy += 1
    try:
        await process(job)
    finally:
        _busy -= 1
    return True


async def _slot(stop: asyncio.Event | None, poll: float) -> None:
    while not (stop and stop.is_set()):
        try:
            worked = await run_once()
        except Exception:  # noqa: BLE001 - keep the slot alive
            log.exception("worker slot error")
            worked = False
        if not worked:
            await asyncio.sleep(poll)


async def _janitor(stop: asyncio.Event | None) -> None:
    """Every minute: reconcile payment orders, requeue expired GPU leases, settle multi-scene
    videos; every 5 minutes: recover stale jobs."""
    tick = 0
    while not (stop and stop.is_set()):
        await asyncio.sleep(60)
        tick += 1
        try:
            await payment_orders.reconcile()
        except Exception:  # noqa: BLE001
            log.exception("payment reconciliation failed")
        try:
            await requeue_expired_leases()
        except Exception:  # noqa: BLE001
            log.exception("GPU lease requeue failed")
        try:
            await stories.recover()
        except Exception:  # noqa: BLE001
            log.exception("story recovery failed")
        if tick % 5:
            continue
        try:
            await recover_stale()
        except Exception:  # noqa: BLE001
            log.exception("stale job recovery failed")


_busy = 0


async def _heartbeat(stop: asyncio.Event | None, slots: int) -> None:
    """Lets the admin panel see live workers and how busy they are."""
    worker_id = f"{socket.gethostname()}:{os.getpid()}"[:64]
    while not (stop and stop.is_set()):
        try:
            async with db.session_factory()() as session:
                row = await session.get(WorkerHeartbeat, worker_id)
                if row is None:
                    row = WorkerHeartbeat(id=worker_id, slots=slots)
                    session.add(row)
                row.busy, row.seen_at = _busy, datetime.now(UTC)
                await session.commit()
        except Exception:  # noqa: BLE001
            log.exception("heartbeat failed")
        await asyncio.sleep(15)


async def run_forever(stop: asyncio.Event | None = None) -> None:
    """Run `worker_slots` jobs concurrently; caps in services/queue.py keep heavy work in check."""
    await recover_stale()
    s = get_settings()
    tasks = [asyncio.create_task(_slot(stop, s.worker_poll_seconds)) for _ in range(s.worker_slots)]
    tasks.append(asyncio.create_task(_janitor(stop)))
    tasks.append(asyncio.create_task(_heartbeat(stop, s.worker_slots)))
    try:
        await asyncio.gather(*tasks)
    finally:
        for t in tasks:
            t.cancel()


if __name__ == "__main__":  # pragma: no cover
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_forever())
