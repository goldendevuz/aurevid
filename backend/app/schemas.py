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
    upscale: UpscaleTarget | None = None  # final resolution: 4K or 8K

    @field_validator("prompt")
    @classmethod
    def _prompt_len(cls, v: str) -> str:
        if len(v) > get_settings().max_prompt_chars:
            raise ValueError("prompt too long")
        if any(ord(c) < 32 and c not in "\n\t" for c in v):
            raise ValueError("prompt contains control characters")
        return v


class AssetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    job_id: str | None
    source: str
    mime: str
    width: int
    height: int
    is_favorite: bool
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
    model_label: str | None = None  # human-readable model name (None for unknown/disabled ones)
    provider_name: str | None = None
    has_audio: bool = False


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
