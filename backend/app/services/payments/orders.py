# SPDX-License-Identifier: AGPL-3.0-or-later
"""Payment orders: create, verify with the gateway, credit exactly once, reconcile.

Rules:
* Credits are granted only after our own server-to-server check says "success" AND the amount
  equals the amount we stored. Webhooks, return URLs and query parameters are never trusted.
* Crediting is one transaction: a conditional UPDATE (status != 'paid' -> 'paid') plus
  `credits.apply` with key `purchase:<order_id>`. Replays, concurrent polls, webhooks and the
  reconciler can all race; only one of them flips the row, and the ledger key backs it up.
* No DB transaction is held open while calling the gateway (SQLite takes the write lock at BEGIN).
"""

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app import db
from app.config import CreditPack
from app.models import PaymentOrder, PaymentStatus, User
from app.security import as_utc
from app.services import credits
from app.services.payments import get_gateway
from app.services.payments.base import CheckResult, GatewayError, PaymentGateway
from app.webhooks import claim_event

log = logging.getLogger("aurevid.payments")

RECHECK_MIN_AGE = timedelta(minutes=2)
EXPIRE_AFTER = timedelta(hours=24)


async def create(session: AsyncSession, user: User, pack: CreditPack, gw: PaymentGateway):
    order = PaymentOrder(
        user_id=user.id,
        pack_id=pack.id,
        credits=pack.credits,
        amount_uzs=pack.amount_uzs,
        provider=gw.name,
        status=PaymentStatus.created,
    )
    session.add(order)
    await session.commit()
    try:
        pid, pay_url = await gw.create_order(
            pack.amount_uzs, f"Aurevid: {pack.credits} credits", order.id
        )
    except GatewayError as exc:
        log.warning("payment order=%s create failed: %s", order.id, exc)
        order.status = PaymentStatus.failed
        await session.commit()
        raise
    order.provider_order_id, order.pay_url = pid, pay_url
    order.status = PaymentStatus.pending
    await session.commit()
    log.info("payment order=%s created provider=%s", order.id, gw.name)
    return order


async def apply_result(session: AsyncSession, order_id: str, result: CheckResult) -> str:
    """Apply a verified gateway answer in one transaction. Returns the resulting status."""
    now = datetime.now(UTC)
    order = await session.get(PaymentOrder, order_id, populate_existing=True)
    if order is None:
        return "missing"
    if order.status == PaymentStatus.paid:
        await session.commit()
        return order.status
    new_status: str | None = None
    if result.status == "success":
        if result.amount_uzs != order.amount_uzs:
            # Paid a different amount than we asked: never credit, leave it for the admin.
            log.warning("payment order=%s amount mismatch, not credited", order.id)
            new_status = PaymentStatus.failed
        else:
            flipped = (
                await session.execute(
                    update(PaymentOrder)
                    .where(PaymentOrder.id == order.id, PaymentOrder.status != PaymentStatus.paid)
                    .values(
                        status=PaymentStatus.paid,
                        paid_at=now,
                        last_checked_at=now,
                        provider_txn_id=result.txn_id,
                    )
                    .returning(PaymentOrder.id)
                )
            ).scalar_one_or_none()
            if flipped is None:  # someone else got there first
                await session.rollback()
                return PaymentStatus.paid
            await claim_event(session, order.provider, f"paid:{order.provider_order_id}")
            if order.user_id is not None:
                await credits.apply(
                    session, order.user_id, order.credits, "purchase", f"purchase:{order.id}"
                )
            else:
                log.warning("payment order=%s paid after account deletion", order.id)
            await session.commit()
            log.info("payment order=%s paid credits=%d", order.id, order.credits)
            return PaymentStatus.paid
    elif result.status in ("failed", "canceled"):
        new_status = PaymentStatus.failed
    values: dict = {"last_checked_at": now}
    if new_status is not None:
        values["status"] = new_status
    await session.execute(
        update(PaymentOrder)
        .where(PaymentOrder.id == order.id, PaymentOrder.status != PaymentStatus.paid)
        .values(**values)
    )
    await session.commit()
    return new_status or order.status


async def verify(session: AsyncSession, order: PaymentOrder) -> str:
    """Ask the gateway about one order and apply the answer. Gateway errors leave it as is."""
    gw = get_gateway()
    if gw is None or gw.name != order.provider or not order.provider_order_id:
        return order.status
    order_id, pid = order.id, order.provider_order_id
    await session.commit()  # end any open transaction before the network call
    try:
        result = await gw.check(pid)
    except GatewayError as exc:
        log.warning("payment order=%s check failed: %s", order_id, exc)
        await session.execute(
            update(PaymentOrder)
            .where(PaymentOrder.id == order_id)
            .values(last_checked_at=datetime.now(UTC))
        )
        await session.commit()
        return order.status
    return await apply_result(session, order_id, result)


def _due(order: PaymentOrder, now: datetime) -> bool:
    """Back off for abandoned checkouts: every minute, then every 10 min, then hourly."""
    age = now - as_utc(order.created_at)
    gap = timedelta(minutes=1) if age < timedelta(minutes=15) else timedelta(minutes=10)
    if age >= timedelta(hours=2):
        gap = timedelta(hours=1)
    last = order.last_checked_at
    return last is None or now - as_utc(last) >= gap - timedelta(seconds=5)


async def reconcile(now: datetime | None = None) -> None:
    """Worker janitor: catch payments whose webhook never arrived; expire stale orders."""
    now = now or datetime.now(UTC)
    async with db.session_factory()() as session:
        pending = (
            (
                await session.execute(
                    select(PaymentOrder)
                    .where(
                        PaymentOrder.status == PaymentStatus.pending,
                        PaymentOrder.created_at <= now - RECHECK_MIN_AGE,
                        PaymentOrder.created_at > now - EXPIRE_AFTER,
                    )
                    .order_by(PaymentOrder.created_at)
                    .limit(200)
                )
            )
            .scalars()
            .all()
        )
        for order in pending:
            if _due(order, now):
                await verify(session, order)
        await session.execute(
            update(PaymentOrder)
            .where(
                or_(
                    PaymentOrder.status == PaymentStatus.pending,
                    PaymentOrder.status == PaymentStatus.created,
                ),
                PaymentOrder.created_at <= now - EXPIRE_AFTER,
            )
            .values(status=PaymentStatus.expired)
        )
        await session.commit()
