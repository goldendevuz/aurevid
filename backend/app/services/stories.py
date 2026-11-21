# SPDX-License-Identifier: AGPL-3.0-or-later
"""Multi-scene video: scene bookkeeping and the join step.

A story is N ordinary video jobs (``Job.story_id`` + ``Job.scene_index``). Whenever one of them
finishes the worker calls ``settle``; when every scene (the newest job of each index) succeeded,
the clips are joined with ffmpeg (services/stitch.py) into one video asset.

``settle`` is idempotent and safe to call from several workers: joining is claimed with a
conditional UPDATE (pending/partial/failed -> stitching), and the final asset is attached only if
the story has none yet. A story stuck in "stitching" (crashed worker) is reset by ``recover``.
"""

import asyncio
import logging
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app import db
from app.images import InvalidImageError, asset_path, delete_stored, store_video_file, tmp_dir
from app.models import Asset, Job, JobStatus, Story, StoryStatus
from app.services import stitch

log = logging.getLogger("aurevid.stories")

SCENE_SECONDS = 5
STALE_STITCH_SECONDS = 600
ACTIVE = (JobStatus.queued, JobStatus.running)


async def current_scenes(session: AsyncSession, story_id: str) -> list[Job]:
    """The newest job of every scene index, in scene order (older failed tries are history)."""
    jobs = (
        (
            await session.execute(
                select(Job)
                .where(Job.story_id == story_id, Job.scene_index.is_not(None))
                .order_by(Job.scene_index, Job.created_at)
            )
        )
        .scalars()
        .all()
    )
    latest: dict[int, Job] = {}
    for job in jobs:
        latest[job.scene_index] = job  # ascending created_at: the last one wins
    return [latest[i] for i in sorted(latest)]


async def _set(story_id: str, **values) -> None:
    async with db.session_factory()() as session:
        await session.execute(
            update(Story).where(Story.id == story_id).values(updated_at=datetime.now(UTC), **values)
        )
        await session.commit()


async def _fail(story_id: str, code: str) -> None:
    await _set(story_id, status=StoryStatus.failed, error=code, finished_at=datetime.now(UTC))


async def settle_for_job(job_id: str) -> None:
    async with db.session_factory()() as session:
        story_id = (
            await session.execute(select(Job.story_id).where(Job.id == job_id))
        ).scalar_one_or_none()
    if story_id:
        await settle(story_id)


async def settle(story_id: str) -> None:
    """Move a story along: wait, mark partial/failed, or join the clips."""
    async with db.session_factory()() as session:
        story = await session.get(Story, story_id)
        if story is None or story.status in (StoryStatus.ready, StoryStatus.stitching):
            return
        scenes = await current_scenes(session, story_id)
        if not scenes or any(j.status in ACTIVE for j in scenes):
            return
        done = [j for j in scenes if j.status == JobStatus.done]
        if len(done) < len(scenes):
            story.status = StoryStatus.partial if done else StoryStatus.failed
            story.error = None
            story.finished_at = datetime.now(UTC)
            story.updated_at = datetime.now(UTC)
            await session.commit()
            return
        claimed = await session.execute(
            update(Story)
            .where(
                Story.id == story_id,
                Story.status.in_((StoryStatus.pending, StoryStatus.partial, StoryStatus.failed)),
            )
            .values(
                status=StoryStatus.stitching,
                error=None,
                finished_at=None,
                updated_at=datetime.now(UTC),
            )
        )
        await session.commit()
        if claimed.rowcount != 1:
            return  # another worker is joining it
    await _stitch(story_id)


async def _clip_paths(session: AsyncSession, story: Story, scenes: list[Job]):
    paths = []
    for job in scenes:
        asset = (
            await session.execute(
                select(Asset)
                .where(Asset.job_id == job.id, Asset.mime == "video/mp4")
                .order_by(Asset.created_at)
                .limit(1)
            )
        ).scalar_one_or_none()
        if asset is None or asset.user_id != story.user_id:
            raise stitch.StitchError()
        path = asset_path(asset.storage_key)
        if not path.exists():
            raise stitch.StitchError()
        paths.append(path)
    return paths


async def _stitch(story_id: str) -> None:
    out = tmp_dir() / f"story-{secrets.token_hex(8)}.mp4"
    stored = None
    try:
        async with db.session_factory()() as session:
            story = await session.get(Story, story_id)
            if story is None:
                return
            paths = await _clip_paths(session, story, await current_scenes(session, story_id))
        info = await stitch.concat_clips(paths, out)
        stored = await asyncio.to_thread(store_video_file, out, info.width, info.height)
    except (stitch.StitchError, InvalidImageError, OSError):
        log.exception("stitching failed story=%s", story_id)
        await _fail(story_id, "stitch_failed")
        return
    except Exception:  # noqa: BLE001 - never leave a story stuck in "stitching"
        log.exception("unexpected stitching failure story=%s", story_id)
        await _fail(story_id, "stitch_failed")
        return
    finally:
        out.unlink(missing_ok=True)  # store_video_file already moved it on success

    async with db.session_factory()() as session:
        story = await session.get(Story, story_id)
        if story is None or story.final_asset_id:
            # Deleted meanwhile, or another worker attached a video first: no duplicate asset.
            delete_stored(stored.storage_key, stored.preview_key)
            return
        asset = Asset(
            user_id=story.user_id,
            job_id=None,
            source="generated",
            storage_key=stored.storage_key,
            mime=stored.mime,
            width=stored.width,
            height=stored.height,
            size_bytes=stored.size_bytes,
            preview_key=stored.preview_key,
        )
        session.add(asset)
        await session.flush()
        story.final_asset_id = asset.id
        story.status = StoryStatus.ready
        story.error = None
        story.finished_at = datetime.now(UTC)
        story.updated_at = datetime.now(UTC)
        await session.commit()
    log.info("story=%s stitched", story_id)


async def recover() -> None:
    """Janitor: reset joins that were interrupted, and settle stories whose last scene finished
    while no worker was looking."""
    cutoff = datetime.now(UTC) - timedelta(seconds=STALE_STITCH_SECONDS)
    async with db.session_factory()() as session:
        await session.execute(
            update(Story)
            .where(Story.status == StoryStatus.stitching, Story.updated_at < cutoff)
            .values(status=StoryStatus.pending, updated_at=datetime.now(UTC))
        )
        await session.commit()
        ids = (
            (await session.execute(select(Story.id).where(Story.status == StoryStatus.pending)))
            .scalars()
            .all()
        )
    for story_id in ids:
        try:
            await settle(story_id)
        except Exception:  # noqa: BLE001 - one broken story must not block the others
            log.exception("story settle failed story=%s", story_id)
