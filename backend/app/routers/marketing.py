# SPDX-License-Identifier: AGPL-3.0-or-later
"""Marketing helper API: ad prompt sets for 9:16 and 1:1 from product text and/or photo."""

import secrets
from typing import Literal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from app.deps import CurrentUser, Session, not_found
from app.images import InvalidImageError, load_stored_image
from app.models import Asset, ModerationEvent
from app.moderation import moderator
from app.providers.registry import get_provider, resolve_credentials
from app.ratelimit import hit
from app.services import marketing

router = APIRouter(prefix="/api/marketing", tags=["marketing"])


class IdeasIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    product: str = Field(min_length=2, max_length=80)
    description: str = Field(default="", max_length=400)
    audience: str = Field(default="", max_length=80)
    tone: Literal["friendly", "premium", "playful", "bold"] = "friendly"
    language: Literal["en", "uz", "ru"] = "en"
    per_format: int = Field(default=3, ge=1, le=4)
    image_asset_id: str | None = Field(default=None, max_length=32)
    use_ai: bool = False
    seed: int | None = Field(default=None, ge=0, le=2**31 - 1)


@router.post("/ideas")
async def ideas(body: IdeasIn, user: CurrentUser, session: Session):
    hit("marketing-user", user.id, "10/hour" if body.use_ai else "40/hour")
    verdict = moderator.check_prompt(f"{body.product} {body.description} {body.audience}")
    if not verdict.allowed:
        session.add(ModerationEvent(user_id=user.id, category=verdict.category or "other"))
        await session.commit()
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail={"code": "prompt_rejected"})

    colors: list[dict] = []
    if body.image_asset_id:
        asset = await session.get(Asset, body.image_asset_id)
        if asset is None or asset.user_id != user.id or not asset.mime.startswith("image/"):
            raise not_found()  # only your own images (IDOR)
        try:
            colors = marketing.palette(load_stored_image(asset.preview_key or asset.storage_key))
        except (OSError, InvalidImageError):
            colors = []

    source, note = "templates", None
    result: list[marketing.Idea] | None = None
    provider = get_provider("cloudflare")
    ai_available = False
    if provider is not None:
        creds = await resolve_credentials(session, provider, user.id)
        ai_available = creds.source != "none"
        if body.use_ai and ai_available:
            try:
                result = await marketing.ai_ideas(
                    creds, body.product, body.description, body.audience, body.tone,
                    body.language, body.per_format, colors,
                )  # fmt: skip
                source = "ai"
            except marketing.LLMUnavailable:
                note = "ai_failed"
    if body.use_ai and not ai_available:
        note = "ai_needs_key"
    if result is None:
        seed = body.seed if body.seed is not None else secrets.randbelow(2**31)
        result = marketing.template_ideas(
            body.product, body.description, body.audience, body.tone, body.language,
            body.per_format, colors, seed,
        )  # fmt: skip
    return {
        "source": source,
        "note": note,
        "ai_available": ai_available,
        "palette": colors,
        "ideas": [i.__dict__ for i in result],
    }
