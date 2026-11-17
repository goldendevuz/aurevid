# SPDX-License-Identifier: AGPL-3.0-or-later
"""Ledger integrity: atomic debits, no negative balance, idempotency, under concurrency."""

import asyncio

import pytest
from sqlalchemy import func, select

from app import db
from app.models import CreditLedger, User
from app.services import credits


async def _user(balance: int) -> str:
    async with db.session_factory()() as s:
        u = User(email="race@example.com", password_hash="x")
        s.add(u)
        await s.flush()
        await credits.apply(s, u.id, balance, "seed", f"seed:{u.id}")
        await s.commit()
        return u.id


async def _debit(user_id: str, n: int) -> bool:
    async with db.session_factory()() as s:
        try:
            await credits.apply(s, user_id, -1, "generation", f"race:{n}")
            await s.commit()
            return True
        except credits.InsufficientCredits:
            await s.rollback()
            return False


async def test_concurrent_debits_never_overdraw():
    user_id = await _user(5)
    results = await asyncio.gather(*[_debit(user_id, n) for n in range(25)])
    assert sum(results) == 5
    async with db.session_factory()() as s:
        bal = await credits.balance(s, user_id)
        total = (
            await s.execute(
                select(func.sum(CreditLedger.delta)).where(CreditLedger.user_id == user_id)
            )
        ).scalar_one()
    assert bal == 0 and total == 0  # cached balance == ledger sum


async def test_same_idempotency_key_applies_once_concurrently():
    user_id = await _user(10)

    async def refund():
        async with db.session_factory()() as s:
            try:
                await credits.apply(s, user_id, 3, "refund", "refund:job-1")
                await s.commit()
            except Exception:  # noqa: BLE001 - unique violation for the loser
                await s.rollback()

    await asyncio.gather(*[refund() for _ in range(10)])
    async with db.session_factory()() as s:
        assert await credits.balance(s, user_id) == 13
        rows = (
            await s.execute(
                select(func.count()).where(CreditLedger.idempotency_key == "refund:job-1")
            )
        ).scalar_one()
    assert rows == 1


async def test_balance_check_constraint_backs_up_the_code():
    from sqlalchemy import update
    from sqlalchemy.exc import IntegrityError

    user_id = await _user(1)
    async with db.session_factory()() as s:
        with pytest.raises(IntegrityError):
            await s.execute(update(User).where(User.id == user_id).values(credit_balance=-1))
            await s.commit()


async def test_zero_delta_rejected():
    user_id = await _user(1)
    async with db.session_factory()() as s:
        with pytest.raises(ValueError):
            await credits.apply(s, user_id, 0, "noop", "noop:1")
