# SPDX-License-Identifier: AGPL-3.0-or-later
"""Multi-scene video: 2-4 prompts become that many ordinary 5 s video jobs, joined into one clip.

Every scene goes through the same checks and charges as POST /api/jobs (``prepare_job``), inside
one transaction: if any scene would be refused (credits, daily limit, free share, keys, moderation,
queue admission) nothing is created and nothing is charged.
"""

from datetime import UTC, datetime

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Path, Query, status
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError

from app.deps import CurrentUser, Session, not_found
from app.images import delete_stored
from app.models import Asset, Job, JobStatus, Story, StoryStatus
from app.moderation import moderator
from app.ratelimit import hit
from app.routers.jobs import _bad, _log_rejection, asset_out, enqueue, job_out, prepare_job
from app.schemas import JobCreateIn, SceneOut, StoryCreateIn, StoryOut
from app.services import credits, stories

router = APIRouter(prefix="/api/stories", tags=["stories"])

SceneIndex = Path(ge=0, le=3)


async def story_out(session, story: Story) -> StoryOut:
    scenes = await stories.current_scenes(session, story.id)
    final = None
    if story.final_asset_id:
        asset = await session.get(Asset, story.final_asset_id)
        if asset is not None and asset.user_id == story.user_id:
            final = asset_out(asset)
    return StoryOut(
        id=story.id,
        title=story.title,
        status=story.status,
        error=story.error,
        created_at=story.created_at,
        finished_at=story.finished_at,
        cost=sum(j.cost for j in scenes),
        scenes=[
            SceneOut(index=j.scene_index, prompt=j.prompt, job=await job_out(session, j))
            for j in scenes
        ],
        final=final,
    )


async def _owned_story(session, user_id: str, story_id: str) -> Story:
    story = await session.get(Story, story_id)
    if story is None or story.user_id != user_id:
        raise not_found()
    return story


@router.post("", response_model=StoryOut, status_code=201)
async def create_story(
    body: StoryCreateIn,
    user: CurrentUser,
    session: Session,
    idempotency_key: str | None = Header(default=None, max_length=60),
):
    hit("jobs-user", user.id, "10/minute")

    if idempotency_key:  # a repeated request returns the story it already made
        prior = (
            await session.execute(
                select(Job.story_id).where(
                    Job.user_id == user.id, Job.client_request_id == f"{idempotency_key}:0"
                )
            )
        ).scalar_one_or_none()
        existing = await session.get(Story, prior) if prior else None
        if existing is not None:
            return await story_out(session, existing)

    # Moderation first: a refusal is logged (category only) and nothing has been written yet.
    for text in (*body.scenes, *([body.title] if body.title else [])):
        verdict = moderator.check_prompt(text)
        if not verdict.allowed:
            await _log_rejection(session, user.id, verdict.category)
            raise _bad("prompt_rejected")

    story = Story(user_id=user.id, title=body.title)
    session.add(story)
    try:
        await session.flush()
        for index, prompt in enumerate(body.scenes):
            scene = JobCreateIn(
                prompt=prompt,
                provider=body.provider,
                model=body.model,
                aspect_ratio=body.aspect_ratio,
                size=body.size,
                count=1,
                duration=stories.SCENE_SECONDS,
            )
            # Same validation and limits as POST /api/jobs. Scenes already flushed in this
            # transaction count towards the daily limit, queue admission and free share.
            job = await prepare_job(
                session, user.id, scene, f"{idempotency_key}:{index}" if idempotency_key else None
            )
            job.story_id, job.scene_index = story.id, index
            session.add(job)
            await session.flush()
            if job.cost > 0:
                await credits.apply(
                    session, user.id, -job.cost, "generation", f"job:{job.id}", job.id
                )
        await session.commit()
    except HTTPException:
        await session.rollback()
        raise
    except credits.InsufficientCredits:
        await session.rollback()
        raise _bad("insufficient_credits", status.HTTP_402_PAYMENT_REQUIRED) from None
    except IntegrityError:
        await session.rollback()
        raise _bad("duplicate_request", status.HTTP_409_CONFLICT) from None
    return await story_out(session, story)


@router.get("", response_model=list[StoryOut])
async def list_stories(
    user: CurrentUser,
    session: Session,
    limit: int = Query(default=12, ge=1, le=50),
    before: datetime | None = None,
):
    stmt = select(Story).where(Story.user_id == user.id)
    if before is not None:
        stmt = stmt.where(Story.created_at < before)
    rows = (await session.execute(stmt.order_by(Story.created_at.desc()).limit(limit))).scalars()
    return [await story_out(session, s) for s in rows]


@router.get("/{story_id}", response_model=StoryOut)
async def get_story(story_id: str, user: CurrentUser, session: Session):
    return await story_out(session, await _owned_story(session, user.id, story_id))


@router.post("/{story_id}/scenes/{index}/retry", response_model=StoryOut, status_code=201)
async def retry_scene(story_id: str, user: CurrentUser, session: Session, index: int = SceneIndex):
    """Run a failed scene again as a new job, charged like any new job."""
    hit("jobs-user", user.id, "10/minute")
    story = await _owned_story(session, user.id, story_id)
    scene = next(
        (j for j in await stories.current_scenes(session, story.id) if j.scene_index == index),
        None,
    )
    if scene is None:
        raise not_found()
    if scene.status != JobStatus.failed:
        raise _bad("scene_not_failed", status.HTTP_409_CONFLICT)
    params = scene.params or {}
    job = await prepare_job(
        session,
        user.id,
        JobCreateIn(
            prompt=scene.prompt,
            provider=scene.provider,
            model=scene.model,
            aspect_ratio=params["aspect_ratio"],
            size=params.get("size", "large"),
            count=1,
            duration=stories.SCENE_SECONDS,
        ),
    )
    job.story_id, job.scene_index = story.id, index
    story.status, story.error, story.finished_at = StoryStatus.pending, None, None
    story.updated_at = datetime.now(UTC)
    await enqueue(session, job)  # inserts the job and debits in one transaction, or neither
    return await story_out(session, story)


@router.post("/{story_id}/stitch", response_model=StoryOut)
async def restitch(story_id: str, user: CurrentUser, session: Session, background: BackgroundTasks):
    """Join the clips again after a failed join (every scene succeeded, so this is free)."""
    story = await _owned_story(session, user.id, story_id)
    if story.status != StoryStatus.failed or story.error != "stitch_failed":
        raise _bad("story_not_stitchable", status.HTTP_409_CONFLICT)
    story.status, story.error, story.finished_at = StoryStatus.pending, None, None
    story.updated_at = datetime.now(UTC)
    await session.commit()
    out = await story_out(session, story)
    # The background join writes in its own session: release this request's SQLite write lock
    # first (background tasks start before the dependency's session is closed).
    await session.close()
    background.add_task(stories.settle, story.id)
    return out


@router.delete("/{story_id}", status_code=204)
async def delete_story(story_id: str, user: CurrentUser, session: Session) -> None:
    """Remove a finished story with its scene clips and the joined video."""
    story = await _owned_story(session, user.id, story_id)
    jobs = (
        (await session.execute(select(Job).where(Job.story_id == story.id, Job.user_id == user.id)))
        .scalars()
        .all()
    )
    if story.status == StoryStatus.stitching or any(
        j.status in (JobStatus.queued, JobStatus.running) for j in jobs
    ):
        raise _bad("job_not_finished", status.HTTP_409_CONFLICT)
    job_ids = [j.id for j in jobs]
    asset_filter = Asset.job_id.in_(job_ids) if job_ids else Asset.id == story.final_asset_id
    if job_ids and story.final_asset_id:
        asset_filter = asset_filter | (Asset.id == story.final_asset_id)
    assets = (
        (await session.execute(select(Asset).where(Asset.user_id == user.id, asset_filter)))
        .scalars()
        .all()
    )
    keys = [(a.storage_key, a.preview_key) for a in assets]
    for a in assets:
        await session.delete(a)
    if job_ids:
        await session.execute(delete(Job).where(Job.id.in_(job_ids)))
    await session.delete(story)
    await session.commit()
    for storage_key, preview_key in keys:
        delete_stored(storage_key, preview_key)
