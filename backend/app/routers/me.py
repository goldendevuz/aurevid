# SPDX-License-Identifier: AGPL-3.0-or-later
"""Account: profile, BYOK keys (write-only), data export, account deletion."""

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Response, status
from sqlalchemy import delete, select

from app.crypto import byok_available, encrypt_secret
from app.deps import CurrentUser, Session, not_found
from app.images import delete_stored
from app.models import (
    Asset,
    CreditLedger,
    Job,
    ModerationEvent,
    ProviderKey,
    RefreshToken,
    User,
    UserActivity,
)
from app.providers.registry import enabled_providers
from app.schemas import (
    DeleteMeIn,
    ProviderKeyIn,
    ProviderKeyOut,
    UpdateMeIn,
    UserOut,
)
from app.security import clear_auth_cookies, verify_password
from app.services import quota

router = APIRouter(prefix="/api/me", tags=["me"])


@router.get("", response_model=UserOut)
async def get_me(user: CurrentUser):
    return user


@router.patch("", response_model=UserOut)
async def update_me(body: UpdateMeIn, user: CurrentUser, session: Session):
    user.locale = body.locale
    await session.commit()
    return user


@router.get("/keys", response_model=list[ProviderKeyOut])
async def list_keys(user: CurrentUser, session: Session):
    rows = (
        (await session.execute(select(ProviderKey).where(ProviderKey.user_id == user.id)))
        .scalars()
        .all()
    )
    stored = {r.provider: r for r in rows}
    out = []
    for pid, provider in enabled_providers().items():
        if provider.info.byok:
            row = stored.get(pid)
            out.append(
                ProviderKeyOut(
                    provider=pid, configured=row is not None, updated_at=row and row.updated_at
                )
            )
    return out


@router.put("/keys/{provider_id}", response_model=ProviderKeyOut)
async def put_key(provider_id: str, body: ProviderKeyIn, user: CurrentUser, session: Session):
    provider = enabled_providers().get(provider_id)
    if provider is None or not provider.info.byok:
        raise not_found()
    if not byok_available():
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail={"code": "byok_disabled"})
    if set(body.values) != set(provider.info.byok_fields):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail={"code": "bad_fields"})
    row = (
        await session.execute(
            select(ProviderKey).where(
                ProviderKey.user_id == user.id, ProviderKey.provider == provider_id
            )
        )
    ).scalar_one_or_none()
    now = datetime.now(UTC)
    if row is None:
        row = ProviderKey(user_id=user.id, provider=provider_id, ciphertext="")
        session.add(row)
    row.ciphertext = encrypt_secret(body.values)
    row.updated_at = now
    await session.commit()
    # The secret itself is never echoed back.
    return ProviderKeyOut(provider=provider_id, configured=True, updated_at=now)


@router.delete("/keys/{provider_id}", status_code=204)
async def delete_key(provider_id: str, user: CurrentUser, session: Session) -> None:
    await session.execute(
        delete(ProviderKey).where(
            ProviderKey.user_id == user.id, ProviderKey.provider == provider_id
        )
    )
    await session.commit()


@router.get("/export")
async def export_data(user: CurrentUser, session: Session):
    jobs = (await session.execute(select(Job).where(Job.user_id == user.id))).scalars().all()
    assets = (await session.execute(select(Asset).where(Asset.user_id == user.id))).scalars().all()
    ledger = (
        (await session.execute(select(CreditLedger).where(CreditLedger.user_id == user.id)))
        .scalars()
        .all()
    )
    return {
        "user": UserOut.model_validate(user).model_dump(mode="json"),
        "jobs": [
            {
                "id": j.id,
                "prompt": j.prompt,
                "provider": j.provider,
                "model": j.model,
                "status": j.status,
                "created_at": j.created_at.isoformat(),
            }
            for j in jobs
        ],
        "assets": [
            {"id": a.id, "job_id": a.job_id, "mime": a.mime, "created_at": a.created_at.isoformat()}
            for a in assets
        ],
        "credits_ledger": [
            {"delta": e.delta, "reason": e.reason, "created_at": e.created_at.isoformat()}
            for e in ledger
        ],
    }


@router.delete("", status_code=204)
async def delete_me(body: DeleteMeIn, response: Response, user: CurrentUser, session: Session):
    if not verify_password(user.password_hash, body.password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail={"code": "invalid_credentials"})
    keys = (
        await session.execute(
            select(Asset.storage_key, Asset.preview_key).where(Asset.user_id == user.id)
        )
    ).all()
    # Explicit deletes (do not rely on FK cascade, which SQLite may not enforce everywhere).
    for model in (
        Asset, Job, ProviderKey, CreditLedger, RefreshToken, UserActivity, ModerationEvent,
    ):  # fmt: skip
        await session.execute(delete(model).where(model.user_id == user.id))
    await quota.delete_scope(session, f"user:{user.id}")
    await session.execute(delete(User).where(User.id == user.id))
    await session.commit()
    for key, preview in keys:
        delete_stored(key, preview)
    clear_auth_cookies(response)
