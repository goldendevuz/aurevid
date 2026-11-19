# SPDX-License-Identifier: AGPL-3.0-or-later
"""Voice prompts: a short recording from the browser -> Whisper on Cloudflare -> prompt text.

The audio is never stored. Size is capped (the browser also stops recording at
``voice_max_seconds``) and the format is checked by its magic bytes, not by the declared type.
"""

from typing import Literal

from fastapi import APIRouter, Form, HTTPException, UploadFile, status

from app.config import get_settings
from app.deps import CurrentUser, Session
from app.providers import cloudflare
from app.providers.base import ProviderError
from app.providers.registry import get_provider, resolve_credentials
from app.ratelimit import hit
from app.schemas import TranscriptOut
from app.services import quota

router = APIRouter(prefix="/api/voice", tags=["voice"])


def audio_kind(data: bytes) -> str | None:
    """Container sniffed from content: what MediaRecorder produces in current browsers."""
    if data[:4] == b"\x1a\x45\xdf\xa3":
        return "webm"
    if data[:4] == b"OggS":
        return "ogg"
    if data[4:8] == b"ftyp":
        return "mp4"
    if data[:4] == b"RIFF" and data[8:12] == b"WAVE":
        return "wav"
    if data[:3] == b"ID3" or (len(data) > 1 and data[0] == 0xFF and data[1] & 0xE0 == 0xE0):
        return "mp3"
    return None


def _bad(code: str, http: int = status.HTTP_400_BAD_REQUEST) -> HTTPException:
    return HTTPException(http, detail={"code": code})


@router.post("/transcribe", response_model=TranscriptOut)
async def transcribe(
    file: UploadFile,
    user: CurrentUser,
    session: Session,
    language: Literal["uz", "ru", "en"] | None = Form(default=None),
):
    s = get_settings()
    provider = get_provider("cloudflare")
    if not s.voice_enabled or provider is None:
        raise _bad("voice_unavailable", status.HTTP_503_SERVICE_UNAVAILABLE)
    hit("voice-user", user.id, "6/minute")
    hit("voice-user-day", user.id, "40/day")  # bounds Neurons spent on the shared server key
    data = await file.read(s.voice_max_bytes + 1)
    if len(data) > s.voice_max_bytes:
        raise _bad("audio_too_large", status.HTTP_413_CONTENT_TOO_LARGE)
    if len(data) < 64 or audio_kind(data) is None:
        raise _bad("invalid_audio", status.HTTP_415_UNSUPPORTED_MEDIA_TYPE)

    creds = await resolve_credentials(session, provider, user.id)
    if not provider.has_usable_credentials(creds):
        raise _bad("provider_key_required")
    scope = quota.scope_for(creds.source, user.id)
    q = await quota.view(session, provider.info.id, scope, provider.info.daily_quota_prior)
    if q.blocked_seconds > 0:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"code": "provider_cooldown", "retry_after": q.blocked_seconds},
            headers={"Retry-After": str(q.blocked_seconds)},
        )
    try:
        text = await cloudflare.transcribe(data, creds, language)
    except ProviderError as exc:
        if exc.quota:
            await quota.record_quota_hit(
                session, provider.info.id, scope, provider.info.daily_quota_prior
            )
            await session.commit()
        raise _bad("transcription_failed", status.HTTP_502_BAD_GATEWAY) from None
    return TranscriptOut(text=text[: s.max_prompt_chars])
