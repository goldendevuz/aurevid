# SPDX-License-Identifier: AGPL-3.0-or-later
"""Webhook verification helpers (signature, timestamp window, idempotency).

No webhook endpoint is wired yet (payments come later); these helpers are tested so the
first real webhook (Payme/Click/provider callbacks) reuses one audited path.
"""

import hashlib
import hmac
import time

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import WebhookEvent


class WebhookRejected(ValueError):
    pass


def verify_signature(
    secret: str,
    body: bytes,
    signature_hex: str,
    timestamp: str,
    tolerance_seconds: int = 300,
    now: float | None = None,
) -> None:
    """HMAC-SHA256 over f"{timestamp}.{body}". Rejects stale or future timestamps (replay)."""
    if not secret:
        raise WebhookRejected("webhook secret not configured")
    try:
        ts = int(timestamp)
    except ValueError as exc:
        raise WebhookRejected("bad timestamp") from exc
    current = time.time() if now is None else now
    if abs(current - ts) > tolerance_seconds:
        raise WebhookRejected("timestamp outside tolerance")
    expected = hmac.new(secret.encode(), f"{ts}.".encode() + body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature_hex.lower()):
        raise WebhookRejected("bad signature")


async def claim_event(session: AsyncSession, source: str, event_id: str) -> bool:
    """Returns True the first time an event id is seen, False for duplicates."""
    try:
        async with session.begin_nested():
            session.add(WebhookEvent(id=f"{source}:{event_id}", source=source))
    except IntegrityError:
        return False
    return True
