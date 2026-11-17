# SPDX-License-Identifier: AGPL-3.0-or-later
"""Job scheduling: admission control, fair ordering and resource caps.

Goals: the server never takes on more than it can finish, one user cannot starve the others, and
heavy CPU work (local AI upscaling) never runs more than ``cpu_job_concurrency`` at a time.

* Admission (at job creation): at most ``max_active_jobs_per_user`` queued+running jobs per user
  and ``max_queue_length`` queued jobs overall. Beyond that the API answers 429/503 with
  Retry-After instead of letting the backlog grow without bound.
* Fair order: round-robin across users. Each user's queued jobs get a rank (1st, 2nd, ...) and
  running jobs count against it, so the next job always comes from the user who has the least
  work in flight. Ties go to the oldest job.
* Resource caps (checked from the DB, so they hold across several worker processes):
  ``cpu_job_concurrency`` for CPU-class jobs and ``provider_concurrency`` per remote provider.
"""

from collections import Counter
from collections.abc import Iterable, Sequence
from statistics import median

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import Job, JobStatus
from app.security import as_utc

CPU, NET = "cpu", "net"
LOCAL_PROVIDER = "local"
# Fallback durations (seconds) until we have history for a provider.
DEFAULT_SECONDS = {"image": 20, "video": 150, "upscale": 45}


def resource_class(job: Job) -> str:
    params = job.params or {}
    if job.provider == LOCAL_PROVIDER or (job.kind == "image" and params.get("upscale")):
        return CPU
    return NET


def fair_order(queued: Sequence[Job], running: Iterable[Job]) -> list[Job]:
    """Round-robin by user: (jobs this user already has ahead/in flight, created_at)."""
    in_flight = Counter(j.user_id for j in running)
    rank: dict[str, int] = {}
    seen: Counter[str] = Counter()
    for job in sorted(queued, key=lambda j: as_utc(j.created_at)):
        rank[job.id] = seen[job.user_id] + in_flight[job.user_id]
        seen[job.user_id] += 1
    return sorted(queued, key=lambda j: (rank[j.id], as_utc(j.created_at)))


def pick(queued: Sequence[Job], running: Sequence[Job]) -> Job | None:
    s = get_settings()
    by_class = Counter(resource_class(j) for j in running)
    by_provider = Counter(j.provider for j in running if j.provider != LOCAL_PROVIDER)
    for job in fair_order(queued, running):
        if resource_class(job) == CPU and by_class[CPU] >= s.cpu_job_concurrency:
            continue
        if job.provider != LOCAL_PROVIDER and by_provider[job.provider] >= s.provider_concurrency:
            continue
        return job
    return None


def over_capacity(job: Job, running: Sequence[Job]) -> bool:
    """After claiming: did a concurrent worker push us past a cap? (`running` includes `job`)."""
    s = get_settings()
    if resource_class(job) == CPU:
        return sum(resource_class(j) == CPU for j in running) > s.cpu_job_concurrency
    if job.provider != LOCAL_PROVIDER:
        return sum(j.provider == job.provider for j in running) > s.provider_concurrency
    return False


async def load(session: AsyncSession, state: JobStatus, limit: int = 500) -> list[Job]:
    rows = await session.execute(
        select(Job).where(Job.status == state).order_by(Job.created_at).limit(limit)
    )
    return list(rows.scalars().all())


async def admit(session: AsyncSession, user_id: str) -> None:
    """Refuse new work early instead of letting the backlog grow without bound."""
    s = get_settings()
    active = (
        await session.execute(
            select(func.count(Job.id)).where(
                Job.user_id == user_id, Job.status.in_([JobStatus.queued, JobStatus.running])
            )
        )
    ).scalar_one()
    if active >= s.max_active_jobs_per_user:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"code": "too_many_active_jobs", "limit": s.max_active_jobs_per_user},
            headers={"Retry-After": "30"},
        )
    queued = (
        await session.execute(select(func.count(Job.id)).where(Job.status == JobStatus.queued))
    ).scalar_one()
    if queued >= s.max_queue_length:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "queue_full", "retry_after": 120},
            headers={"Retry-After": "120"},
        )


def _kind_key(job: Job) -> str:
    return "upscale" if job.provider == LOCAL_PROVIDER else job.kind


async def average_seconds(session: AsyncSession, job: Job) -> float:
    """Mean wall time of the last 20 finished jobs of the same provider + kind."""
    rows = await session.execute(
        select(Job.started_at, Job.finished_at)
        .where(
            Job.provider == job.provider,
            Job.kind == job.kind,
            Job.status == JobStatus.done,
            Job.started_at.is_not(None),
            Job.finished_at.is_not(None),
        )
        .order_by(Job.finished_at.desc())
        .limit(20)
    )
    spans = [
        (as_utc(f) - as_utc(s)).total_seconds()
        for s, f in rows.all()
        if s and f and as_utc(f) >= as_utc(s)
    ]
    if not spans:
        return float(DEFAULT_SECONDS[_kind_key(job)])
    return sum(spans) / len(spans)


# Fallback for video that is also upscaled (several extra Topaz passes on fal).
DEFAULT_UPSCALED_VIDEO_SECONDS = 420


async def typical_run_seconds(session: AsyncSession, job: Job) -> int:
    """Median run time of recent finished jobs like this one (same provider, model, kind and
    whether it is upscaled): what the UI shows as "usually about ...". Median, not mean, so one
    stuck job does not skew it."""
    upscaled = bool((job.params or {}).get("upscale"))
    rows = await session.execute(
        select(Job.started_at, Job.finished_at, Job.params)
        .where(
            Job.provider == job.provider,
            Job.model == job.model,
            Job.kind == job.kind,
            Job.status == JobStatus.done,
            Job.started_at.is_not(None),
            Job.finished_at.is_not(None),
        )
        .order_by(Job.finished_at.desc())
        .limit(40)
    )
    spans = [
        (as_utc(f) - as_utc(st)).total_seconds()
        for st, f, params in rows.all()
        if bool((params or {}).get("upscale")) == upscaled and as_utc(f) >= as_utc(st)
    ]
    if spans:
        return max(1, int(median(spans[:20])))
    if upscaled and job.kind == "video":
        return DEFAULT_UPSCALED_VIDEO_SECONDS
    return DEFAULT_SECONDS[_kind_key(job)]


async def position_and_eta(session: AsyncSession, job: Job) -> tuple[int, int]:
    """1-based place among queued jobs in fair order, and a rough wait in seconds."""
    queued = await load(session, JobStatus.queued)
    running = await load(session, JobStatus.running)
    order = fair_order(queued, running)
    try:
        position = next(i for i, j in enumerate(order) if j.id == job.id) + 1
    except StopIteration:
        return 0, 0
    s = get_settings()
    lanes = s.cpu_job_concurrency if resource_class(job) == CPU else s.provider_concurrency
    ahead = sum(1 for j in order[: position - 1] if resource_class(j) == resource_class(job))
    per_job = await average_seconds(session, job)
    eta = per_job * (ahead // max(1, lanes) + 1) * max(1, job.count)
    return position, int(eta)
