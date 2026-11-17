# SPDX-License-Identifier: AGPL-3.0-or-later
"""Email + password auth with httpOnly cookies and rotating refresh tokens."""

from datetime import UTC, datetime, timedelta

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from app.config import get_settings
from app.deps import CurrentUser, Session
from app.models import RefreshToken, User, new_id
from app.ratelimit import client_ip, hit, limit_ip
from app.schemas import LoginIn, RegisterIn, UserOut
from app.security import (
    REFRESH_COOKIE,
    as_utc,
    clear_auth_cookies,
    create_access_token,
    hash_password,
    hash_refresh_token,
    new_csrf_token,
    new_refresh_token,
    set_auth_cookies,
    set_csrf_cookie,
    verify_password,
)
from app.services import credits

router = APIRouter(prefix="/api/auth", tags=["auth"])


async def verify_turnstile(token: str | None, ip: str) -> None:
    secret = get_settings().turnstile_secret
    if not secret:
        return  # captcha disabled (dev / not configured)
    if not token:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail={"code": "captcha_required"})
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                "https://challenges.cloudflare.com/turnstile/v0/siteverify",
                data={"secret": secret, "response": token, "remoteip": ip},
            )
        ok = resp.json().get("success") is True
    except (httpx.HTTPError, ValueError):
        ok = False
    if not ok:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail={"code": "captcha_failed"})


async def _issue_session(session: Session, response: Response, user: User, family: str | None):
    raw, digest = new_refresh_token()
    session.add(
        RefreshToken(
            user_id=user.id,
            family_id=family or new_id(),
            token_hash=digest,
            expires_at=datetime.now(UTC) + timedelta(days=get_settings().refresh_token_days),
        )
    )
    await session.commit()
    set_auth_cookies(response, create_access_token(user.id), raw)
    set_csrf_cookie(response, new_csrf_token())


@router.get("/csrf", status_code=204)
async def csrf(response: Response) -> None:
    set_csrf_cookie(response, new_csrf_token())


@router.post(
    "/register",
    response_model=UserOut,
    status_code=201,
    dependencies=[Depends(limit_ip("register", "5/hour"))],
)
async def register(body: RegisterIn, request: Request, response: Response, session: Session):
    await verify_turnstile(body.turnstile_token, client_ip(request))
    user = User(email=body.email.lower(), password_hash=hash_password(body.password))
    user.locale = body.locale
    session.add(user)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        # Generic message: do not confirm which emails exist.
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail={"code": "registration_failed"}
        ) from None
    signup = get_settings().signup_credits
    if signup > 0:
        await credits.apply(session, user.id, signup, "signup_bonus", f"signup:{user.id}")
    await _issue_session(session, response, user, None)
    await session.refresh(user)
    return user


@router.post(
    "/login", response_model=UserOut, dependencies=[Depends(limit_ip("login", "10/minute"))]
)
async def login(body: LoginIn, request: Request, response: Response, session: Session):
    email = body.email.lower()
    hit("login-email", email, "20/hour")
    await verify_turnstile(body.turnstile_token, client_ip(request))
    user = (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if not verify_password(user.password_hash if user else None, body.password) or user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail={"code": "invalid_credentials"})
    if user.is_blocked:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail={"code": "account_blocked"})
    await _issue_session(session, response, user, None)
    return user


@router.post("/refresh", status_code=204, dependencies=[Depends(limit_ip("refresh", "30/minute"))])
async def refresh(request: Request, response: Response, session: Session) -> None:
    raw = request.cookies.get(REFRESH_COOKIE)
    unauthorized = HTTPException(status.HTTP_401_UNAUTHORIZED, detail={"code": "invalid_session"})
    if not raw:
        raise unauthorized
    token = (
        await session.execute(
            select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(raw))
        )
    ).scalar_one_or_none()
    if token is None:
        raise unauthorized
    now = datetime.now(UTC)
    if token.revoked_at is not None:
        # Reuse of a rotated token => likely theft. Kill the whole family.
        await session.execute(
            update(RefreshToken)
            .where(RefreshToken.family_id == token.family_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=now)
        )
        await session.commit()
        clear_auth_cookies(response)
        raise unauthorized
    if as_utc(token.expires_at) < now:
        raise unauthorized
    user = await session.get(User, token.user_id)
    if user is None or user.is_blocked:
        raise unauthorized
    # Atomic rotation: only one concurrent refresh can revoke this token.
    rotated = await session.execute(
        update(RefreshToken)
        .where(RefreshToken.id == token.id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=now)
    )
    if rotated.rowcount != 1:
        await session.rollback()
        raise unauthorized
    await _issue_session(session, response, user, token.family_id)


@router.post("/logout", status_code=204)
async def logout(request: Request, response: Response, session: Session) -> None:
    raw = request.cookies.get(REFRESH_COOKIE)
    if raw:
        await session.execute(
            update(RefreshToken)
            .where(
                RefreshToken.token_hash == hash_refresh_token(raw),
                RefreshToken.revoked_at.is_(None),
            )
            .values(revoked_at=datetime.now(UTC))
        )
        await session.commit()
    clear_auth_cookies(response)


@router.get("/me", response_model=UserOut)
async def whoami(user: CurrentUser):
    return user
