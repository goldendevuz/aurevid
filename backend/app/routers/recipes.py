# SPDX-License-Identifier: AGPL-3.0-or-later
"""Recipes: start a ready-made chain (see services/recipes.py)."""

from fastapi import APIRouter, HTTPException, status

from app.deps import CurrentUser, Session, not_found
from app.providers.registry import allowed_upscales, get_provider, resolve_credentials
from app.ratelimit import hit
from app.routers.jobs import enqueue, job_out, prepare_job
from app.schemas import JobCreateIn, JobOut, RecipeRunIn
from app.services.recipes import RECIPES

router = APIRouter(prefix="/api/recipes", tags=["recipes"])


def _bad(code: str) -> HTTPException:
    return HTTPException(status.HTTP_400_BAD_REQUEST, detail={"code": code})


@router.post("/{recipe_id}/run", response_model=JobOut, status_code=201)
async def run_recipe(recipe_id: str, body: RecipeRunIn, user: CurrentUser, session: Session):
    hit("jobs-user", user.id, "10/minute")
    if recipe_id not in RECIPES:
        raise not_found()

    # Check the follow-up step now, so the user is not charged for an image that cannot move on.
    vp = get_provider(body.video_provider)
    vm = vp.model(body.video_model) if vp else None
    if vp is None or vm is None or vm.kind != "video" or not vm.accepts_image:
        raise _bad("recipe_step_unavailable")
    if not vp.has_usable_credentials(await resolve_credentials(session, vp, user.id)):
        raise _bad("recipe_step_unavailable")
    if body.aspect_ratio not in vm.aspect_ratios:
        raise _bad("aspect_ratio_unsupported")
    duration = body.duration or vm.durations[0]
    if duration not in vm.durations:
        raise _bad("duration_unsupported")
    if body.upscale and body.upscale not in allowed_upscales(vm):
        raise _bad("upscale_unsupported")

    first = JobCreateIn(
        prompt=body.prompt,
        provider=body.provider,
        model=body.model,
        aspect_ratio=body.aspect_ratio,
        size=body.size,
        preset_id=body.preset_id,
        seed=body.seed,
    )
    job = await prepare_job(session, user.id, first)
    if job.kind != "image":
        raise _bad("unknown_model")
    step = {"provider": vp.info.id, "model": vm.id, "duration": duration, "upscale": body.upscale}
    job.params = {**job.params, "recipe": {"id": recipe_id, "next": [step]}}
    await enqueue(session, job)
    return await job_out(session, job)
