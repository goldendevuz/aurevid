# SPDX-License-Identifier: AGPL-3.0-or-later
"""Business-day helpers. Uzbekistan is UTC+5 all year (no DST), configurable for other markets."""

from datetime import UTC, date, datetime, timedelta

from app.config import get_settings
from app.security import as_utc


def offset() -> timedelta:
    return timedelta(hours=get_settings().analytics_utc_offset_hours)


def local_day(dt: datetime) -> date:
    return (as_utc(dt) + offset()).date()


def today_local() -> date:
    return local_day(datetime.now(UTC))


def local_midnight_utc(day: date) -> datetime:
    """UTC instant at which a local calendar day starts."""
    return datetime(day.year, day.month, day.day, tzinfo=UTC) - offset()
