# SPDX-License-Identifier: AGPL-3.0-or-later
"""DB-backed job queue worker. Works on SQLite and PostgreSQL without Redis.

Claiming is a conditional UPDATE (status='queued' -> 'running'), so two workers can never
process the same job. Run standalone with `python -m app.worker`, or inside the API process
(RUN_WORKER_IN_API=true) for single-container free hosting.
"""

import asyncio
import logging
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update

from app import db
from app.config import get_settings
from app.images import InvalidImageError, delete_stored, store_image
from app.models import Asset, Job, JobStatus
from app.providers.base import GenerationRequest, ProviderError
from app.providers.registry import get_provider, resolve_credentials
from app.services import credits

log = logging.getLogger("aurevid.worker")


async def claim_next() -> Job | None:
    async with db.session_factory()() as session:
        candidate = (
            await session.execute(
                select(Job.id)
                .where(Job.status == JobStatus.queued)
                .order_by(Job.created_at)
                .limit(1)
            )
        ).scalar_one_or_none()
        if candidate is None:
            return None
        result = await session.execute(
            update(Job)
            .where(Job.id == candidate, Job.status == JobStatus.queued)
            .values(
                status=JobStatus.running,
                started_at=datetime.now(UTC),
                attempts=Job.attempts + 1,
            )
        )
        await session.commit()
        if result.rowcount != 1:
            return None  # another worker won the race
        return await session.get(Job, candidate)


async def _finish(job_id: str, produced: int, error: str | None) -> None:
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


RETRY_DELAY_SECONDS = 6.0  # free tiers (e.g. Pollinations) throttle back-to-back requests


async def _generate_with_retry(provider, req: GenerationRequest, creds):
    timeout = get_settings().job_timeout_seconds
    try:
        return await asyncio.wait_for(provider.generate(req, creds), timeout=timeout)
    except ProviderError as exc:
        if not exc.retryable:
            raise
        await asyncio.sleep(RETRY_DELAY_SECONDS)
        return await asyncio.wait_for(provider.generate(req, creds), timeout=timeout)


async def process(job: Job) -> None:
    provider = get_provider(job.provider)
    if provider is None:
        await _finish(job.id, 0, "Provider is not available")
        return
    params = job.params or {}
    async with db.session_factory()() as session:
        creds = await resolve_credentials(session, provider, job.user_id)
    produced = 0
    error: str | None = None
    base_seed = params.get("seed")
    for i in range(job.count):
        seed = (base_seed + i) if isinstance(base_seed, int) else secrets.randbelow(2**31)
        req = GenerationRequest(
            prompt=params.get("final_prompt", job.prompt),
            model=job.model,
            aspect_ratio=params["aspect_ratio"],
            width=params["width"],
            height=params["height"],
            seed=seed,
        )
        try:
            image = await _generate_with_retry(provider, req, creds)
            stored = store_image(image.data)  # validates by content + re-encodes
        except ProviderError as exc:
            error = exc.public
            break
        except InvalidImageError:
            error = "Provider returned an invalid image"
            break
        except TimeoutError:
            error = "Generation timed out"
            break
        except Exception:  # noqa: BLE001 - never leak internals to the user
            log.exception("unexpected provider failure job=%s", job.id)
            error = "Unexpected error"
            break
        async with db.session_factory()() as session:
            if await session.get(Job, job.id) is None:  # user deleted account meanwhile
                delete_stored(stored.storage_key)
                return
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
                )
            )
            await session.commit()
        produced += 1
    await _finish(job.id, produced, error)
    log.info("job=%s produced=%d status=%s", job.id, produced, "ok" if produced else "failed")


async def recover_stale() -> None:
    """Fail + refund jobs left 'running' by a crashed worker."""
    cutoff = datetime.now(UTC) - timedelta(seconds=get_settings().job_timeout_seconds * 5)
    async with db.session_factory()() as session:
        stale = (
            (
                await session.execute(
                    select(Job.id).where(Job.status == JobStatus.running, Job.started_at < cutoff)
                )
            )
            .scalars()
            .all()
        )
    for job_id in stale:
        await _finish(job_id, 0, "Interrupted, credits refunded")


async def run_once() -> bool:
    job = await claim_next()
    if job is None:
        return False
    await process(job)
    return True


async def run_forever(stop: asyncio.Event | None = None) -> None:
    await recover_stale()
    poll = get_settings().worker_poll_seconds
    while not (stop and stop.is_set()):
        try:
            worked = await run_once()
        except Exception:  # noqa: BLE001 - keep the loop alive
            log.exception("worker loop error")
            worked = False
        if not worked:
            await asyncio.sleep(poll)


if __name__ == "__main__":  # pragma: no cover
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_forever())
