# SPDX-License-Identifier: AGPL-3.0-or-later
"""Credits & usage (read-only for users; no payments in the MVP)."""

from datetime import UTC, datetime

from fastapi import APIRouter
from sqlalchemy import func, select

from app.config import get_settings
from app.deps import CurrentUser, Session
from app.models import CreditLedger, Job
from app.schemas import LedgerOut, UsageOut

router = APIRouter(prefix="/api/credits", tags=["credits"])


@router.get("", response_model=UsageOut)
async def usage(user: CurrentUser, session: Session):
    start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    jobs_today = (
        await session.execute(
            select(func.count(Job.id)).where(Job.user_id == user.id, Job.created_at >= start)
        )
    ).scalar_one()
    ledger = (
        (
            await session.execute(
                select(CreditLedger)
                .where(CreditLedger.user_id == user.id)
                .order_by(CreditLedger.created_at.desc())
                .limit(50)
            )
        )
        .scalars()
        .all()
    )
    return UsageOut(
        balance=user.credit_balance,
        jobs_today=jobs_today,
        daily_job_limit=get_settings().daily_job_limit,
        ledger=[LedgerOut.model_validate(e) for e in ledger],
    )
