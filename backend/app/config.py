# SPDX-License-Identifier: AGPL-3.0-or-later
"""Application settings. Secrets come only from environment variables."""

from functools import lru_cache
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class CreditPack(BaseModel):
    """An optional credit top-up sold in UZS (see services/payments)."""

    id: str = Field(pattern=r"^[a-z0-9_-]{1,32}$")
    credits: int = Field(gt=0, le=1_000_000)
    amount_uzs: int = Field(ge=1000, le=100_000_000)  # inPAY minimum is 1 000 so'm


# PLACEHOLDER prices: the owner must confirm them before payments are switched on.
DEFAULT_CREDIT_PACKS = [
    CreditPack(id="small", credits=100, amount_uzs=15_000),
    CreditPack(id="medium", credits=300, amount_uzs=39_000),
    CreditPack(id="large", credits=1000, amount_uzs=119_000),
]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        hide_input_in_errors=True,  # a config error must never print secrets from the env
    )

    app_env: Literal["dev", "test", "prod"] = "dev"
    database_url: str = "sqlite+aiosqlite:///./data/aurevid.db"
    asset_dir: str = "./data/assets"

    # --- secrets (never commit real values) ---
    jwt_secret: str = Field(default="", repr=False)
    byok_encryption_key: str = Field(default="", repr=False)  # Fernet key, base64
    turnstile_secret: str = Field(default="", repr=False)
    cf_account_id: str = Field(default="", repr=False)
    cf_api_token: str = Field(default="", repr=False)
    # Owner's own Modal endpoint (deploy/modal): a few free clips per user, see allowance.py.
    modal_submit_url: str = Field(default="", repr=False)
    modal_token_id: str = Field(default="", repr=False)
    modal_token_secret: str = Field(default="", repr=False)
    inpay_merchant_id: str = Field(default="", repr=False)
    inpay_merchant_token: str = Field(default="", repr=False)

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
    max_image_pixels: int = 8192 * 8192  # room for 8K outputs
    max_provider_image_bytes: int = (
        80 * 1024 * 1024
    )  # provider output (users stay at max_upload_bytes)
    max_video_bytes: int = 600 * 1024 * 1024  # 8K clips; streamed to disk, never held in memory
    daily_job_limit: int = 30
    signup_credits: int = 50
    server_free_videos_per_user: int = 2  # lifetime clips on the owner's Modal key
    # All users together, per UTC month: keeps the owner's Modal bill inside its free $30 credit
    # (~$0.18 per clip measured 2026-11-20, so 150 clips ~ $27).
    server_video_monthly_cap: int = 150
    analytics_utc_offset_hours: int = 5  # Asia/Tashkent; used for "today", daily charts, cohorts

    # --- providers ---
    pollinations_enabled: bool = False  # terms unverified (MODEL_LICENSES.md); opt-in only
    pollinations_base_url: str = "https://image.pollinations.ai"
    cloudflare_enabled: bool = True
    # Side tools on the Cloudflare account (user's key first, else the server key):
    alt_text_enabled: bool = True  # describe generated/uploaded images (Qwen 3.8 27B)
    voice_enabled: bool = True  # voice prompts (Whisper large-v3-turbo)
    voice_max_bytes: int = 1024 * 1024  # ~60 s of Opus; the browser stops at voice_max_seconds
    voice_max_seconds: int = 30
    # fal.ai (video, image-to-video, 4K/8K video). On by default (owner decision 2026-11-17);
    # it only runs with each user's own key, so the server never pays.
    # Owner rule (2026-11-20): only models whose licence AND service terms clearly allow commercial
    # use run. Models marked "unclear"/"no" (Kling, Seedance, Pollinations video, Topaz) are hidden
    # everywhere unless this is true, and it is refused in prod. See MODEL_LICENSES.md.
    allow_unclear_models: bool = False
    pollinations_video_enabled: bool = False  # all its models have unclear terms
    modal_video_enabled: bool = True  # BYOK only: runs in the user's own Modal workspace
    fal_enabled: bool = True
    fal_video_upscale_enabled: bool = False  # Topaz: output terms unclear
    mock_provider_enabled: bool = False
    upscaler_enabled: bool = True  # local Real-ESRGAN (CPU) for 4K/8K images
    upscaler_timeout_seconds: int = 300  # hard stop per image (checked between tiles)
    upscaler_threads: int = 0  # 0 = all cores but one (keeps the API responsive)

    # --- payments (optional credit packs; the product stays free to use) ---
    payments_provider: Literal["none", "fake", "inpay"] = "none"  # fake: dev/test only
    inpay_base_url: str = "https://inpay.uz/api/v1"
    public_base_url: str = ""  # e.g. https://aurevid.example; builds callback/return URLs
    credit_packs: list[CreditPack] = Field(default_factory=lambda: list(DEFAULT_CREDIT_PACKS))

    # --- worker ---
    run_worker_in_api: bool = True
    # --- queue / resource control ---
    worker_slots: int = 3  # jobs one worker process runs at the same time
    cpu_job_concurrency: int = 1  # heavy local CPU jobs (AI upscaling) at once, across workers
    provider_concurrency: int = 2  # in-flight jobs per provider, across workers
    max_active_jobs_per_user: int = 3  # queued + running
    max_queue_length: int = 200  # all users; beyond this new jobs are refused (back-pressure)
    worker_poll_seconds: float = 1.0
    job_timeout_seconds: int = 180
    video_timeout_seconds: int = 600

    @field_validator("cors_origins")
    @classmethod
    def _no_wildcard(cls, v: list[str]) -> list[str]:
        if any(o.strip() == "*" for o in v):
            raise ValueError("CORS wildcard '*' is not allowed; list explicit origins")
        return v

    @field_validator("credit_packs")
    @classmethod
    def _unique_packs(cls, v: list[CreditPack]) -> list[CreditPack]:
        if len({p.id for p in v}) != len(v):
            raise ValueError("CREDIT_PACKS ids must be unique")
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
            if self.allow_unclear_models:
                raise ValueError("ALLOW_UNCLEAR_MODELS must be false in prod (commercial-use rule)")
            if self.payments_provider == "fake":
                raise ValueError("PAYMENTS_PROVIDER=fake is not allowed in prod")
            if self.payments_provider != "none" and not self.public_base_url.startswith("https://"):
                raise ValueError("PUBLIC_BASE_URL must be an https:// URL in prod")
        if self.payments_provider == "inpay":
            if not (self.inpay_merchant_id and self.inpay_merchant_token and self.public_base_url):
                raise ValueError(
                    "PAYMENTS_PROVIDER=inpay needs INPAY_MERCHANT_ID, INPAY_MERCHANT_TOKEN "
                    "and PUBLIC_BASE_URL"
                )
            if not self.inpay_base_url.startswith("https://"):
                raise ValueError("INPAY_BASE_URL must be https")
        if self.app_env != "prod" and not self.jwt_secret:
            # Dev/test convenience only: an ephemeral secret, sessions reset on restart.
            import secrets

            self.jwt_secret = secrets.token_urlsafe(48)
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
