# SPDX-License-Identifier: AGPL-3.0-or-later
"""Shared FastAPI dependencies: DB session, current user, admin guard."""

from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import User, UserActivity
from app.security import ACCESS_COOKIE, decode_access_token
from app.timeutil import today_local

# (user_id, day) pairs already recorded by this process: at most one DB write per user per day.
_seen_today: set[tuple[str, str]] = set()


async def _record_activity(session: AsyncSession, user: User) -> None:
    user_id = user.id
    day = today_local().isoformat()
    if (user_id, day) in _seen_today:
        return
    if len(_seen_today) > 200_000:
        _seen_today.clear()
    try:
        async with session.begin_nested():
            session.add(UserActivity(user_id=user_id, day=day))
        await session.commit()
    except IntegrityError:
        await session.rollback()  # already recorded (another process or a restart)
        await session.refresh(user)  # rollback expires it; handlers read user.id synchronously
    _seen_today.add((user_id, day))


Session = Annotated[AsyncSession, Depends(get_session)]


async def current_user(request: Request, session: Session) -> User:
    token = request.cookies.get(ACCESS_COOKIE)
    user_id = decode_access_token(token) if token else None
    if not user_id:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail={"code": "not_authenticated"})
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail={"code": "not_authenticated"})
    if user.is_blocked:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail={"code": "account_blocked"})
    await _record_activity(session, user)
    return user


CurrentUser = Annotated[User, Depends(current_user)]


async def admin_user(user: CurrentUser) -> User:
    if not user.is_admin:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    return user


AdminUser = Annotated[User, Depends(admin_user)]


def not_found() -> HTTPException:
    # Same response for "missing" and "not yours" so ids cannot be probed (IDOR).
    return HTTPException(status.HTTP_404_NOT_FOUND, detail={"code": "not_found"})
