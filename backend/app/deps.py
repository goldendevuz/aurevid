# SPDX-License-Identifier: AGPL-3.0-or-later
"""Shared FastAPI dependencies: DB session, current user, admin guard."""

from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import User
from app.security import ACCESS_COOKIE, decode_access_token

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
