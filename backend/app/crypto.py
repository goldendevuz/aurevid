# SPDX-License-Identifier: AGPL-3.0-or-later
"""Encryption at rest for BYOK provider keys (Fernet = AES-128-CBC + HMAC-SHA256)."""

import json
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

from app.config import get_settings


class CryptoUnavailable(RuntimeError):
    pass


@lru_cache
def _fernet() -> Fernet:
    key = get_settings().byok_encryption_key
    if not key:
        raise CryptoUnavailable("BYOK_ENCRYPTION_KEY is not configured")
    return Fernet(key.encode())


def byok_available() -> bool:
    try:
        _fernet()
    except (CryptoUnavailable, ValueError):
        return False
    return True


def encrypt_secret(data: dict[str, str]) -> str:
    return _fernet().encrypt(json.dumps(data).encode()).decode()


def decrypt_secret(token: str) -> dict[str, str]:
    try:
        return json.loads(_fernet().decrypt(token.encode()))
    except InvalidToken as exc:  # key rotated or data tampered
        raise CryptoUnavailable("cannot decrypt stored key") from exc
