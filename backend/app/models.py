# SPDX-License-Identifier: AGPL-3.0-or-later
"""ORM models: users, refresh_tokens, jobs, assets, credits_ledger, provider_keys, reports."""

import enum
import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


def new_id() -> str:
    return uuid.uuid4().hex


class JobStatus(enum.StrEnum):
    queued = "queued"
    running = "running"
    done = "done"
    failed = "failed"


class User(Base):
    __tablename__ = "users"
    __table_args__ = (CheckConstraint("credit_balance >= 0", name="ck_users_balance_nonneg"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    locale: Mapped[str] = mapped_column(String(8), default="en")
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False)
    # Team/test accounts: excluded from admin analytics by default.
    is_internal: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    # Cached balance; the ledger is the source of truth and both change in one transaction.
    credit_balance: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    family_id: Mapped[str] = mapped_column(String(32), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        UniqueConstraint("user_id", "client_request_id", name="uq_jobs_user_request"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    client_request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    kind: Mapped[str] = mapped_column(String(16), default="image")
    provider: Mapped[str] = mapped_column(String(32))
    model: Mapped[str] = mapped_column(String(64))
    prompt: Mapped[str] = mapped_column(Text)
    preset_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    params: Mapped[dict] = mapped_column(JSON, default=dict)
    # Whose key ran it: "user" (BYOK), "server" (owner's key, counts against the free share),
    # "none" (keyless/local). Set at creation; the worker switches it on a server fallback.
    key_source: Mapped[str | None] = mapped_column(String(8), nullable=True, index=True)
    count: Mapped[int] = mapped_column(Integer, default=1)
    cost: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus, native_enum=False, length=16), default=JobStatus.queued, index=True
    )
    error: Mapped[str | None] = mapped_column(String(255), nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Asset(Base):
    __tablename__ = "assets"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    job_id: Mapped[str | None] = mapped_column(
        ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    source: Mapped[str] = mapped_column(String(16))  # generated | upload
    storage_key: Mapped[str] = mapped_column(String(80), unique=True)  # random, server-chosen
    preview_key: Mapped[str | None] = mapped_column(String(80), nullable=True)  # small WebP
    mime: Mapped[str] = mapped_column(String(32))
    width: Mapped[int] = mapped_column(Integer)
    height: Mapped[int] = mapped_column(Integer)
    size_bytes: Mapped[int] = mapped_column(Integer)
    is_favorite: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class CreditLedger(Base):
    """Append-only. Application code never UPDATEs or DELETEs rows (except account erasure)."""

    __tablename__ = "credits_ledger"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    delta: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(String(32))
    job_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(96), unique=True)
    balance_after: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ProviderKey(Base):
    """BYOK secrets, encrypted at rest. Never returned to clients."""

    __tablename__ = "provider_keys"
    __table_args__ = (UniqueConstraint("user_id", "provider", name="uq_provider_keys_user"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    provider: Mapped[str] = mapped_column(String(32))
    ciphertext: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    reporter_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    asset_id: Mapped[str | None] = mapped_column(
        ForeignKey("assets.id", ondelete="SET NULL"), nullable=True
    )
    reason: Mapped[str] = mapped_column(String(32))
    details: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="open")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class WebhookEvent(Base):
    """Processed webhook ids, for idempotency / replay protection (payments come later)."""

    __tablename__ = "webhook_events"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    source: Mapped[str] = mapped_column(String(32))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ProviderQuota(Base):
    """Learned usage limits per provider + credential scope (see services/quota.py)."""

    __tablename__ = "provider_quotas"
    __table_args__ = (UniqueConstraint("provider", "scope", name="uq_provider_quota"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    provider: Mapped[str] = mapped_column(String(32))
    scope: Mapped[str] = mapped_column(String(48), index=True)  # server | anon | user:<id>
    day: Mapped[str] = mapped_column(String(10))  # UTC date the counters belong to
    used_today: Mapped[int] = mapped_column(Integer, default=0)
    hits_today: Mapped[int] = mapped_column(Integer, default=0)
    est_daily_limit: Mapped[float | None] = mapped_column(Float, nullable=True)
    est_source: Mapped[str] = mapped_column(String(16), default="unknown")
    observations: Mapped[int] = mapped_column(Integer, default=0)
    consecutive_hits: Mapped[int] = mapped_column(Integer, default=0)
    cooldown_s: Mapped[float] = mapped_column(Float, default=15.0)
    blocked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class UserActivity(Base):
    """One row per user per active day (UTC+5 calendar day). Feeds retention and cohorts."""

    __tablename__ = "user_activity"
    __table_args__ = (UniqueConstraint("user_id", "day", name="uq_user_activity_day"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    day: Mapped[str] = mapped_column(String(10), index=True)  # YYYY-MM-DD, Asia/Tashkent


class ModerationEvent(Base):
    """A prompt refused by moderation. Category only: the prompt text is not stored."""

    __tablename__ = "moderation_events"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    category: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )


class WorkerHeartbeat(Base):
    __tablename__ = "worker_heartbeats"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # host:pid
    slots: Mapped[int] = mapped_column(Integer)
    busy: Mapped[int] = mapped_column(Integer, default=0)
    seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Announcement(Base):
    """In-app banner shown to every signed-in user (admin "broadcast")."""

    __tablename__ = "announcements"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    level: Mapped[str] = mapped_column(String(16), default="info")  # info | warning | success
    text_en: Mapped[str] = mapped_column(String(500))
    text_uz: Mapped[str | None] = mapped_column(String(500), nullable=True)
    text_ru: Mapped[str | None] = mapped_column(String(500), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AdminAudit(Base):
    """Append-only record of admin actions (ids and small details only, no secrets)."""

    __tablename__ = "admin_audit"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    admin_id: Mapped[str | None] = mapped_column(String(32), index=True)
    action: Mapped[str] = mapped_column(String(48))
    target: Mapped[str | None] = mapped_column(String(64), nullable=True)
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )
