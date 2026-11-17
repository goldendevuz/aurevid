# SPDX-License-Identifier: AGPL-3.0-or-later
"""Assets: owner-only file download, favourites, deletion, validated uploads, reports."""

from fastapi import APIRouter, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select

from app.config import get_settings
from app.deps import CurrentUser, Session, not_found
from app.images import InvalidImageError, asset_path, delete_stored, store_image
from app.models import Asset, Report
from app.ratelimit import hit
from app.routers.jobs import asset_out
from app.schemas import AssetOut, FavoriteIn, ReportIn

router = APIRouter(prefix="/api", tags=["assets"])


async def _owned(session, user_id: str, asset_id: str) -> Asset:
    asset = await session.get(Asset, asset_id)
    if asset is None or asset.user_id != user_id:
        raise not_found()
    return asset


@router.get("/assets/{asset_id}/file")
async def asset_file(asset_id: str, user: CurrentUser, session: Session):
    asset = await _owned(session, user.id, asset_id)
    path = asset_path(asset.storage_key)
    if not path.exists():
        raise not_found()
    return FileResponse(
        path,
        media_type=asset.mime,
        filename=f"aurevid-{asset.id}.webp",
        content_disposition_type="inline",
        headers={"Cache-Control": "private, max-age=3600"},
    )


@router.post("/assets/{asset_id}/favorite", response_model=AssetOut)
async def set_favorite(asset_id: str, body: FavoriteIn, user: CurrentUser, session: Session):
    asset = await _owned(session, user.id, asset_id)
    asset.is_favorite = body.favorite
    await session.commit()
    return asset_out(asset)


@router.delete("/assets/{asset_id}", status_code=204)
async def delete_asset(asset_id: str, user: CurrentUser, session: Session) -> None:
    asset = await _owned(session, user.id, asset_id)
    key = asset.storage_key
    await session.delete(asset)
    await session.commit()
    delete_stored(key)


@router.post("/assets/upload", response_model=AssetOut, status_code=201)
async def upload(file: UploadFile, user: CurrentUser, session: Session):
    """Reference image upload (for marketing helper / image-to-video, later)."""
    hit("upload-user", user.id, "20/hour")
    limit = get_settings().max_upload_bytes
    data = await file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, detail={"code": "file_too_large"})
    try:
        stored = store_image(data)  # MIME decided by content, never by name or header
    except InvalidImageError:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail={"code": "invalid_image"}
        ) from None
    asset = Asset(
        user_id=user.id,
        source="upload",
        storage_key=stored.storage_key,
        mime=stored.mime,
        width=stored.width,
        height=stored.height,
        size_bytes=stored.size_bytes,
    )
    session.add(asset)
    await session.commit()
    return asset_out(asset)


@router.post("/reports", status_code=201)
async def report(body: ReportIn, user: CurrentUser, session: Session):
    hit("report-user", user.id, "20/hour")
    # A user can report only assets they can see, which in the MVP means their own.
    asset = await _owned(session, user.id, body.asset_id)
    exists = (
        await session.execute(
            select(Report).where(Report.reporter_id == user.id, Report.asset_id == asset.id)
        )
    ).scalar_one_or_none()
    if exists is None:
        session.add(
            Report(reporter_id=user.id, asset_id=asset.id, reason=body.reason, details=body.details)
        )
        await session.commit()
    return {"status": "received"}
