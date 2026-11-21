# SPDX-License-Identifier: AGPL-3.0-or-later
"""After a restart the first request of the day for an already-seen user must not 500."""

from sqlalchemy import select

from app import db, deps
from app.models import User
from tests.conftest import make_user


async def test_user_stays_usable_after_duplicate_activity_row():
    _, body = await make_user("restart@example.com")
    async with db.SessionLocal() as session:
        user = (
            await session.execute(select(User).where(User.email == "restart@example.com"))
        ).scalar_one()
        deps._seen_today.clear()  # a fresh process has not seen this user yet
        await deps._record_activity(session, user)  # row may already exist -> IntegrityError path
        deps._seen_today.clear()
        await deps._record_activity(session, user)  # definitely a duplicate now
        # handlers read user.id synchronously; an expired instance would raise MissingGreenlet
        assert user.id and user.email == "restart@example.com"
        assert body
