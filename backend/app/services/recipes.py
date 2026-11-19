# SPDX-License-Identifier: AGPL-3.0-or-later
"""Recipes: ready-made chains of jobs, e.g. image -> animate (-> 4K).

The chain lives in the first job's params ("recipe": {"id", "next": [steps]}). When a job of a
chain finishes, the worker calls `advance`: it creates the next step for the same user through
the normal job checks (credits, daily limit, free share, moderation), so every step is charged
on its own. Any failure stops the chain and records a readable error code on the job.
"""

import logging

from fastapi import HTTPException
from sqlalchemy import select

from app import db
from app.models import Asset, Job, JobStatus
from app.schemas import JobCreateIn

log = logging.getLogger("aurevid.recipes")

# Recipe id -> kinds of its steps, in order. The first step is always created by the API.
RECIPES: dict[str, tuple[str, ...]] = {
    "image-animate-4k": ("image", "video"),
}


def _code(exc: HTTPException) -> str:
    detail = exc.detail if isinstance(exc.detail, dict) else {}
    return str(detail.get("code") or "recipe_step_failed")


async def _set_recipe(session, job_id: str, **changes) -> None:
    job = await session.get(Job, job_id)
    if job is None:
        return
    params = dict(job.params or {})
    params["recipe"] = {**params.get("recipe", {}), **changes}
    job.params = params  # new dict, so the JSON column is marked dirty
    await session.commit()


async def advance(job_id: str) -> None:
    """Create the next step of a finished job's recipe, or stop the chain with an error."""
    from app.routers.jobs import enqueue, prepare_job  # the API's checks, shared on purpose

    async with db.session_factory()() as session:
        job = await session.get(Job, job_id)
        recipe = (job.params or {}).get("recipe") if job else None
        if not recipe or not recipe.get("next") or "next_job_id" in recipe or "error" in recipe:
            return
        if job.status != JobStatus.done:
            await _set_recipe(session, job_id, error="recipe_step_failed")
            return
        first = (
            await session.execute(
                select(Asset)
                .where(Asset.job_id == job.id, Asset.mime.like("image/%"))
                .order_by(Asset.created_at)
                .limit(1)
            )
        ).scalar_one_or_none()
        if first is None or first.user_id != job.user_id:
            await _set_recipe(session, job_id, error="recipe_step_failed")
            return
        step, rest = recipe["next"][0], recipe["next"][1:]
        body = JobCreateIn(
            prompt=job.prompt,
            provider=step["provider"],
            model=step["model"],
            aspect_ratio=job.params["aspect_ratio"],
            size=job.params.get("size", "large"),
            preset_id=job.preset_id,
            duration=step.get("duration"),
            image_asset_id=first.id,
            upscale=step.get("upscale"),
        )
        try:
            nxt = await prepare_job(session, job.user_id, body, f"recipe:{job.id}")
            nxt.params = {
                **nxt.params,
                "recipe": {"id": recipe["id"], "prev_job_id": job.id, "next": rest},
            }
            next_id = nxt.id
            await enqueue(session, nxt)
        except HTTPException as exc:
            await session.rollback()
            log.info("recipe stopped job=%s code=%s", job_id, _code(exc))
            await _set_recipe(session, job_id, error=_code(exc))
            return
        await _set_recipe(session, job_id, next_job_id=next_id)
