# SPDX-License-Identifier: AGPL-3.0-or-later
"""Expand prompt endpoint: turn a one-line idea into a detailed scene prompt."""

import logging
import re
from typing import Literal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.config import get_settings
from app.deps import CurrentUser, Session
from app.providers.registry import resolve_credentials
from app.ratelimit import hit
from app.services.expand import ExpandError, expand_prompt

log = logging.getLogger("aurevid.prompt")

router = APIRouter(prefix="/api/prompt", tags=["prompt"])


class ExpandIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    prompt: str = Field(min_length=3, max_length=500)
    kind: Literal["video", "image"]
    duration_sec: int | None = Field(default=None, ge=1, le=60)
    aspect_ratio: str | None = Field(default=None, max_length=11)
    has_audio: bool = True

    @field_validator("aspect_ratio")
    @classmethod
    def _valid_ar(cls, v: str | None) -> str | None:
        if v is not None and not re.match(r"^\d{1,2}:\d{1,2}$|^auto$", v):
            raise ValueError("invalid aspect ratio")
        return v


class ExpandOut(BaseModel):
    prompt: str
    cost_usd: float | None = None


@router.post("/expand", response_model=ExpandOut)
async def post_expand(body: ExpandIn, user: CurrentUser, session: Session):
    # Rate limit: 20/hour per user
    hit("expand-user", user.id, "20/hour")

    # Resolve API key: user's OpenRouter key -> server key -> 503
    api_key = await _resolve_expand_key(session, user.id)

    try:
        expanded, cost = await expand_prompt(
            prompt=body.prompt,
            kind=body.kind,
            duration_sec=body.duration_sec,
            aspect_ratio=body.aspect_ratio,
            has_audio=body.has_audio,
            api_key=api_key,
        )
    except ExpandError as e:
        raise HTTPException(e.status_code, detail={"code": e.code}) from None

    # Log without key or prompt text
    log.info("expand user=%s cost=%s", user.id, cost)

    return ExpandOut(prompt=expanded, cost_usd=cost)


async def _resolve_expand_key(session, user_id: str) -> str:
    """Resolve the API key for expand: user's OpenRouter key > server key > 503."""
    from app.providers.registry import enabled_providers

    # Try user's own key via BYOK
    providers = enabled_providers()
    or_provider = providers.get("openrouter_video")
    if or_provider is not None:
        creds = await resolve_credentials(session, or_provider, user_id)
        if creds.source == "user":
            key = creds.values.get("api_key", "")
            if key:
                return key

    # Try server key
    s = get_settings()
    if s.openrouter_api_key:
        return s.openrouter_api_key

    raise HTTPException(
        status.HTTP_503_SERVICE_UNAVAILABLE,
        detail={"code": "expand_unavailable"},
    )


async def has_expand_key(session, user_id: str) -> bool:
    """Check if expansion is available (user has key or server key set)."""
    from app.providers.registry import enabled_providers

    providers = enabled_providers()
    or_provider = providers.get("openrouter_video")
    if or_provider is not None:
        creds = await resolve_credentials(session, or_provider, user_id)
        if creds.source == "user" and creds.values.get("api_key"):
            return True

    s = get_settings()
    return bool(s.openrouter_api_key)
