# SPDX-License-Identifier: AGPL-3.0-or-later
"""Credits: append-only ledger + cached balance, changed atomically in one transaction.

The debit is a single conditional UPDATE (`balance >= amount`), so concurrent requests can
never drive the balance negative, on SQLite or PostgreSQL. A CHECK constraint backs it up.
Each ledger row has a unique idempotency key, so retries never double-charge or double-refund.
"""

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CreditLedger, User


class InsufficientCredits(Exception):
    pass


async def _existing(session: AsyncSession, key: str) -> CreditLedger | None:
    return (
        await session.execute(select(CreditLedger).where(CreditLedger.idempotency_key == key))
    ).scalar_one_or_none()


async def apply(
    session: AsyncSession,
    user_id: str,
    delta: int,
    reason: str,
    idempotency_key: str,
    job_id: str | None = None,
) -> CreditLedger:
    """Apply a credit change inside the caller's transaction (caller commits)."""
    if delta == 0:
        raise ValueError("delta must be non-zero")
    prior = await _existing(session, idempotency_key)
    if prior is not None:
        return prior
    stmt = update(User).where(User.id == user_id)
    if delta < 0:
        stmt = stmt.where(User.credit_balance >= -delta)
    stmt = stmt.values(credit_balance=User.credit_balance + delta).returning(User.credit_balance)
    new_balance = (await session.execute(stmt)).scalar_one_or_none()
    if new_balance is None:
        raise InsufficientCredits()
    entry = CreditLedger(
        user_id=user_id,
        delta=delta,
        reason=reason,
        job_id=job_id,
        idempotency_key=idempotency_key,
        balance_after=new_balance,
    )
    session.add(entry)
    await session.flush()
    return entry


async def balance(session: AsyncSession, user_id: str) -> int:
    return (
        await session.execute(select(User.credit_balance).where(User.id == user_id))
    ).scalar_one()
