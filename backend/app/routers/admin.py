# SPDX-License-Identifier: AGPL-3.0-or-later
"""Minimal moderation tools for admins: review reports, block users, remove assets."""

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, update

from app.deps import AdminUser, Session, not_found
from app.images import delete_stored
from app.models import Asset, RefreshToken, Report, User, utcnow
from app.services import credits

router = APIRouter(prefix="/api/admin", tags=["admin"])


class BlockIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    blocked: bool


class GrantIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    amount: int = Field(ge=1, le=10_000)
    note_id: str = Field(min_length=4, max_length=40)  # makes the grant idempotent


@router.get("/reports")
async def list_reports(_: AdminUser, session: Session):
    rows = (
        (
            await session.execute(
                select(Report).where(Report.status == "open").order_by(Report.created_at).limit(100)
            )
        )
        .scalars()
        .all()
    )
    return [
        {
            "id": r.id,
            "asset_id": r.asset_id,
            "reason": r.reason,
            "details": r.details,
            "created_at": r.created_at,
        }
        for r in rows
    ]


@router.post("/users/{user_id}/block")
async def block_user(user_id: str, body: BlockIn, admin: AdminUser, session: Session):
    target = await session.get(User, user_id)
    if target is None or target.id == admin.id:
        raise not_found()
    target.is_blocked = body.blocked
    if body.blocked:
        await session.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=utcnow())
        )
    await session.commit()
    return {"id": target.id, "blocked": target.is_blocked}


@router.delete("/assets/{asset_id}", status_code=204)
async def remove_asset(asset_id: str, _: AdminUser, session: Session) -> None:
    asset = await session.get(Asset, asset_id)
    if asset is None:
        raise not_found()
    keys = (asset.storage_key, asset.preview_key)
    await session.execute(
        update(Report).where(Report.asset_id == asset_id).values(status="actioned")
    )
    await session.delete(asset)
    await session.commit()
    delete_stored(*keys)


@router.post("/users/{user_id}/credits")
async def grant_credits(user_id: str, body: GrantIn, _: AdminUser, session: Session):
    if await session.get(User, user_id) is None:
        raise not_found()
    entry = await credits.apply(
        session, user_id, body.amount, "admin_grant", f"grant:{user_id}:{body.note_id}"
    )
    await session.commit()
    return {"balance": entry.balance_after}
