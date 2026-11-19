# SPDX-License-Identifier: AGPL-3.0-or-later
"""Optional credit packs (UZS). Off unless PAYMENTS_PROVIDER is set; signup credits stay.

The gateway callback is unauthenticated and unsigned: it is only a hint to re-check the order
with the gateway ourselves. It is CSRF-exempt by exact path (main.py) and always answers 200.
"""

import json
import logging
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from app.config import get_settings
from app.deps import CurrentUser, Session, not_found
from app.models import PaymentOrder, PaymentStatus
from app.ratelimit import client_ip, hit
from app.schemas import UTCDateTime
from app.security import as_utc
from app.services.payments import get_gateway, orders
from app.services.payments.base import GatewayError

router = APIRouter(prefix="/api/payments", tags=["payments"])
log = logging.getLogger("aurevid.payments")

CALLBACK_PATH = "/api/payments/inpay/callback"
POLL_RECHECK = timedelta(seconds=10)
CALLBACK_RECHECK = timedelta(seconds=2)
MAX_CALLBACK_BYTES = 8 * 1024


class OrderIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pack_id: str = Field(min_length=1, max_length=32)


class PackOut(BaseModel):
    id: str
    credits: int
    amount_uzs: int


class PacksOut(BaseModel):
    enabled: bool
    packs: list[PackOut]


class OrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    pack_id: str
    credits: int
    amount_uzs: int
    status: str
    created_at: UTCDateTime
    paid_at: UTCDateTime | None


class OrderCreated(BaseModel):
    order_id: str
    pay_url: str


@router.get("/packs", response_model=PacksOut)
async def packs():
    s = get_settings()
    return PacksOut(
        enabled=s.payments_provider != "none",
        packs=[PackOut(**p.model_dump()) for p in s.credit_packs],
    )


@router.post("/orders", response_model=OrderCreated, status_code=201)
async def create_order(body: OrderIn, user: CurrentUser, session: Session):
    gw = get_gateway()
    if gw is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, {"code": "payments_disabled"})
    pack = next((p for p in get_settings().credit_packs if p.id == body.pack_id), None)
    if pack is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, {"code": "unknown_pack"})
    hit("payorder-user", user.id, "5/minute")
    hit("payorder-user-day", user.id, "30/day")
    try:
        order = await orders.create(session, user, pack, gw)
    except GatewayError:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, {"code": "payment_gateway_error"}
        ) from None
    return OrderCreated(order_id=order.id, pay_url=order.pay_url or "")


@router.get("/orders", response_model=list[OrderOut])
async def list_orders(user: CurrentUser, session: Session):
    rows = await session.execute(
        select(PaymentOrder)
        .where(PaymentOrder.user_id == user.id)
        .order_by(PaymentOrder.created_at.desc())
        .limit(20)
    )
    return [OrderOut.model_validate(o) for o in rows.scalars().all()]


@router.get("/orders/{order_id}", response_model=OrderOut)
async def get_order(order_id: str, user: CurrentUser, session: Session):
    hit("payorder-poll", user.id, "120/minute")
    order = await session.get(PaymentOrder, order_id[:32])
    if order is None or order.user_id != user.id:
        raise not_found()
    now = datetime.now(UTC)
    if order.status == PaymentStatus.pending and (
        order.last_checked_at is None or now - as_utc(order.last_checked_at) >= POLL_RECHECK
    ):
        await orders.verify(session, order)
        order = await session.get(PaymentOrder, order.id, populate_existing=True)
    return OrderOut.model_validate(order)


async def _callback_order_id(request: Request) -> str | None:
    body = await request.body()
    if len(body) > MAX_CALLBACK_BYTES:
        return None
    data: object = None
    try:
        data = json.loads(body)
    except ValueError:
        try:
            data = dict((await request.form()).items())
        except Exception:  # noqa: BLE001 - malformed body: ignore
            return None
    if isinstance(data, dict) and isinstance(data.get("data"), dict):
        data = data["data"]
    if not isinstance(data, dict):
        return None
    value = data.get("order_id")
    if isinstance(value, int | str) and not isinstance(value, bool):
        text = str(value).strip()
        return text if 0 < len(text) <= 64 else None
    return None


@router.post(CALLBACK_PATH.removeprefix("/api/payments"))
async def inpay_callback(request: Request, session: Session):
    """Unsigned trigger: look up our order and verify it with inPAY. Always 200."""
    ok = {"status": "ok"}
    try:
        hit("payments-callback", f"ip:{client_ip(request)}", "120/minute")
        provider_order_id = await _callback_order_id(request)
        if provider_order_id is None:
            return ok
        order = (
            await session.execute(
                select(PaymentOrder).where(
                    PaymentOrder.provider == "inpay",
                    PaymentOrder.provider_order_id == provider_order_id,
                )
            )
        ).scalar_one_or_none()
        if order is None or order.status == PaymentStatus.paid:
            return ok
        last = order.last_checked_at
        if last is not None and datetime.now(UTC) - as_utc(last) < CALLBACK_RECHECK:
            return ok
        await orders.verify(session, order)
    except Exception:  # noqa: BLE001 - never make the gateway retry on our errors
        log.warning("payments callback ignored after an error", exc_info=False)
    return ok
