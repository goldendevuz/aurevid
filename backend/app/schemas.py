# SPDX-License-Identifier: AGPL-3.0-or-later
"""Request/response schemas (Pydantic v2). All input is validated here."""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.config import get_settings
from app.providers.base import AspectRatio, SizeName, UpscaleTarget
from app.security import as_utc

# SQLite returns naive datetimes; always emit explicit UTC so clients never guess the zone.
UTCDateTime = Annotated[datetime, AfterValidator(as_utc)]

Locale = Literal["en", "uz", "ru"]


class _In(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class RegisterIn(_In):
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)
    locale: Locale = "en"
    accept_terms: bool
    turnstile_token: str | None = Field(default=None, max_length=2048)

    @field_validator("accept_terms")
    @classmethod
    def _must_accept(cls, v: bool) -> bool:
        if not v:
            raise ValueError("terms must be accepted")
        return v


class LoginIn(_In):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)
    turnstile_token: str | None = Field(default=None, max_length=2048)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    email: str
    locale: str
    is_admin: bool
    credit_balance: int
    created_at: UTCDateTime
    expand_available: bool = False


class UpdateMeIn(_In):
    locale: Locale


class DeleteMeIn(_In):
    password: str = Field(min_length=1, max_length=128)


class ProviderKeyIn(_In):
    values: dict[str, str] = Field(min_length=1, max_length=4)

    @field_validator("values")
    @classmethod
    def _sizes(cls, v: dict[str, str]) -> dict[str, str]:
        for k, val in v.items():
            if not (1 <= len(k) <= 32) or not (1 <= len(val) <= 512):
                raise ValueError("invalid key field")
        return v


class ProviderKeyOut(BaseModel):
    provider: str
    configured: bool
    updated_at: UTCDateTime | None = None


def check_prompt(v: str) -> str:
    if len(v) > get_settings().max_prompt_chars:
        raise ValueError("prompt too long")
    if any(ord(c) < 32 and c not in "\n\t" for c in v):
        raise ValueError("prompt contains control characters")
    return v


check_prompt_text = check_prompt  # name used by the edit/voice schemas


Resolution = Literal["480p", "720p", "1080p"]


class JobCreateIn(_In):
    prompt: str = Field(min_length=3)
    provider: str = Field(max_length=32)
    model: str = Field(max_length=64)
    aspect_ratio: AspectRatio = "1:1"
    size: SizeName = "large"
    count: int = Field(default=1, ge=1, le=4)
    preset_id: str | None = Field(default=None, max_length=64)
    seed: int | None = Field(default=None, ge=0, le=2**31 - 1)
    duration: int | None = Field(default=None, ge=1, le=20)  # video seconds
    image_asset_id: str | None = Field(default=None, max_length=32)  # image-to-video start frame
    upscale: UpscaleTarget | None = None  # final resolution: 2K, 4K or 8K (images; video 4K/8K)
    resolution: Resolution | None = None  # video models with a resolution parameter
    quality: Literal["standard", "publish"] = "standard"  # "publish": best free model + upscale

    @field_validator("prompt")
    @classmethod
    def _prompt_len(cls, v: str) -> str:
        return check_prompt(v)


class StoryCreateIn(_In):
    """2-4 scene prompts, each becoming a 5 s video job with the same model and format."""

    provider: str = Field(max_length=32)
    model: str = Field(max_length=64)
    aspect_ratio: AspectRatio = "16:9"
    size: SizeName = "large"
    resolution: Resolution | None = None
    scenes: list[str] = Field(min_length=2, max_length=4)
    title: str | None = Field(default=None, max_length=80)

    @field_validator("scenes")
    @classmethod
    def _scene_prompts(cls, v: list[str]) -> list[str]:
        out = []
        for prompt in v:
            prompt = prompt.strip()
            if len(prompt) < 3:
                raise ValueError("scene prompt too short")
            out.append(check_prompt(prompt))
        return out


class RecipeRunIn(_In):
    """First step (an image job) plus the settings of the follow-up video step."""

    prompt: str = Field(min_length=3)
    provider: str = Field(max_length=32)
    model: str = Field(max_length=64)
    aspect_ratio: AspectRatio = "1:1"
    size: SizeName = "large"
    preset_id: str | None = Field(default=None, max_length=64)
    seed: int | None = Field(default=None, ge=0, le=2**31 - 1)
    video_provider: str = Field(max_length=32)
    video_model: str = Field(max_length=64)
    duration: int | None = Field(default=None, ge=1, le=20)
    upscale: UpscaleTarget | None = None  # final video resolution (optional)

    @field_validator("prompt")
    @classmethod
    def _prompt_len(cls, v: str) -> str:
        return check_prompt(v)
        return check_prompt_text(v)


class AssetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    job_id: str | None
    source: str
    mime: str
    width: int
    height: int
    is_favorite: bool
    alt_text: str | None = None
    created_at: UTCDateTime
    url: str = ""
    preview_url: str = ""


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    kind: str
    status: str
    provider: str
    model: str
    prompt: str
    preset_id: str | None
    params: dict
    count: int
    cost: int
    error: str | None
    created_at: UTCDateTime
    started_at: UTCDateTime | None = None
    finished_at: UTCDateTime | None
    assets: list[AssetOut] = []
    queue_position: int | None = None  # 1-based, queued jobs only
    eta_seconds: int | None = None  # rough estimate from recent job durations
    typical_seconds: int | None = None  # running jobs: median run time of similar finished jobs
    story_id: str | None = None  # set when the job is one scene of a multi-scene video
    scene_index: int | None = None
    model_label: str | None = None  # human-readable model name (None for unknown/disabled ones)
    provider_name: str | None = None
    has_audio: bool = False


class SceneOut(BaseModel):
    index: int
    prompt: str
    job: JobOut


class StoryOut(BaseModel):
    id: str
    title: str | None
    status: str
    error: str | None
    created_at: UTCDateTime
    finished_at: UTCDateTime | None
    cost: int  # credits charged for the scenes currently in the story
    scenes: list[SceneOut]
    final: AssetOut | None = None


class FacetOut(BaseModel):
    value: str
    count: int
    label: str | None = None
    provider: str | None = None  # models only: which provider the model belongs to


class JobFacetsOut(BaseModel):
    total: int
    kinds: list[FacetOut]
    statuses: list[FacetOut]
    providers: list[FacetOut]
    models: list[FacetOut]


class EditIn(_In):
    """'Edit with text': an instruction applied to one of the caller's own images."""

    instruction: str = Field(min_length=3)

    @field_validator("instruction")
    @classmethod
    def _instruction(cls, v: str) -> str:
        return check_prompt_text(v)


class TranscriptOut(BaseModel):
    text: str


class FavoriteIn(_In):
    favorite: bool


class UpscaleIn(_In):
    target: UpscaleTarget


class ReportIn(_In):
    asset_id: str = Field(max_length=32)
    reason: Literal["illegal", "sexual", "minor_safety", "violence", "copyright", "other"]
    details: str | None = Field(default=None, max_length=500)


class LedgerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    delta: int
    reason: str
    job_id: str | None
    balance_after: int
    created_at: UTCDateTime


class UsageOut(BaseModel):
    balance: int
    jobs_today: int
    daily_job_limit: int
    ledger: list[LedgerOut]
