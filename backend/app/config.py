# SPDX-License-Identifier: AGPL-3.0-or-later
"""Application settings. Secrets come only from environment variables."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: Literal["dev", "test", "prod"] = "dev"
    database_url: str = "sqlite+aiosqlite:///./data/aurevid.db"
    asset_dir: str = "./data/assets"

    # --- secrets (never commit real values) ---
    jwt_secret: str = Field(default="", repr=False)
    byok_encryption_key: str = Field(default="", repr=False)  # Fernet key, base64
    turnstile_secret: str = Field(default="", repr=False)
    cf_account_id: str = Field(default="", repr=False)
    cf_api_token: str = Field(default="", repr=False)

    # --- cookies / auth ---
    cookie_secure: bool = True
    cookie_domain: str | None = None
    access_token_minutes: int = 15
    refresh_token_days: int = 30

    # --- http ---
    cors_origins: list[str] = ["http://localhost:5173"]
    rate_limit_storage: str = "memory://"

    # --- product limits ---
    max_prompt_chars: int = 1000
    max_upload_bytes: int = 8 * 1024 * 1024
    max_image_pixels: int = 4096 * 4096
    daily_job_limit: int = 30
    signup_credits: int = 50

    # --- providers ---
    pollinations_enabled: bool = False  # terms unverified (MODEL_LICENSES.md); opt-in only
    pollinations_base_url: str = "https://image.pollinations.ai"
    cloudflare_enabled: bool = True
    fal_enabled: bool = False
    mock_provider_enabled: bool = False

    # --- worker ---
    run_worker_in_api: bool = True
    worker_poll_seconds: float = 1.0
    job_timeout_seconds: int = 180

    @field_validator("cors_origins")
    @classmethod
    def _no_wildcard(cls, v: list[str]) -> list[str]:
        if any(o.strip() == "*" for o in v):
            raise ValueError("CORS wildcard '*' is not allowed; list explicit origins")
        return v

    @model_validator(mode="after")
    def _prod_requirements(self) -> "Settings":
        if self.app_env == "prod":
            if len(self.jwt_secret) < 32:
                raise ValueError("JWT_SECRET must be set (>= 32 chars) in prod")
            if not self.byok_encryption_key:
                raise ValueError("BYOK_ENCRYPTION_KEY must be set in prod")
            if not self.cookie_secure:
                raise ValueError("COOKIE_SECURE must be true in prod")
            if self.mock_provider_enabled:
                raise ValueError("MOCK_PROVIDER_ENABLED must be false in prod")
        elif not self.jwt_secret:
            # Dev/test convenience only: an ephemeral secret, sessions reset on restart.
            import secrets

            self.jwt_secret = secrets.token_urlsafe(48)
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
