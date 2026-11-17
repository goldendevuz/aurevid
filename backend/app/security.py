# SPDX-License-Identifier: AGPL-3.0-or-later
"""Password hashing (argon2id), access JWTs, refresh tokens, CSRF tokens, cookie helpers."""

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from fastapi import Response

from app.config import get_settings

ACCESS_COOKIE = "av_access"
REFRESH_COOKIE = "av_refresh"
CSRF_COOKIE = "av_csrf"
CSRF_HEADER = "x-csrf-token"
REFRESH_PATH = "/api/auth"

# argon2id with library defaults (RFC 9106 "second recommended" profile)
_hasher = PasswordHasher()
_DUMMY_HASH = _hasher.hash("timing-equaliser-not-a-real-password")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str | None, password: str) -> bool:
    """Constant-ish time: verifies against a dummy hash when the user does not exist."""
    try:
        return _hasher.verify(password_hash or _DUMMY_HASH, password) and password_hash is not None
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def as_utc(dt: datetime) -> datetime:
    """SQLite returns naive datetimes; treat them as UTC."""
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def create_access_token(user_id: str) -> str:
    s = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": user_id,
        "typ": "access",
        "iat": now,
        "exp": now + timedelta(minutes=s.access_token_minutes),
        "jti": secrets.token_hex(8),
    }
    return jwt.encode(payload, s.jwt_secret, algorithm="HS256")


def decode_access_token(token: str) -> str | None:
    try:
        payload = jwt.decode(
            token,
            get_settings().jwt_secret,
            algorithms=["HS256"],
            options={"require": ["exp", "sub", "typ"]},
        )
    except jwt.PyJWTError:
        return None
    if payload.get("typ") != "access":
        return None
    return str(payload["sub"])


def new_refresh_token() -> tuple[str, str]:
    """Returns (raw token for the cookie, sha256 hash for the DB)."""
    raw = secrets.token_urlsafe(48)
    return raw, hash_refresh_token(raw)


def hash_refresh_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def new_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def csrf_matches(cookie_value: str | None, header_value: str | None) -> bool:
    if not cookie_value or not header_value:
        return False
    return hmac.compare_digest(cookie_value, header_value)


def _cookie_kwargs() -> dict:
    s = get_settings()
    return {"secure": s.cookie_secure, "samesite": "lax", "domain": s.cookie_domain}


def set_auth_cookies(response: Response, access: str, refresh: str) -> None:
    s = get_settings()
    kw = _cookie_kwargs()
    response.set_cookie(
        ACCESS_COOKIE, access, httponly=True, max_age=s.access_token_minutes * 60, path="/", **kw
    )
    response.set_cookie(
        REFRESH_COOKIE,
        refresh,
        httponly=True,
        max_age=s.refresh_token_days * 86400,
        path=REFRESH_PATH,
        **kw,
    )


def clear_auth_cookies(response: Response) -> None:
    kw = _cookie_kwargs()
    response.delete_cookie(ACCESS_COOKIE, path="/", httponly=True, **kw)
    response.delete_cookie(REFRESH_COOKIE, path=REFRESH_PATH, httponly=True, **kw)


def set_csrf_cookie(response: Response, token: str) -> None:
    # Readable by JS on purpose (double-submit pattern); not a secret on its own.
    response.set_cookie(CSRF_COOKIE, token, httponly=False, path="/", **_cookie_kwargs())
