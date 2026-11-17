# SPDX-License-Identifier: AGPL-3.0-or-later
"""Async database engine and session helpers (SQLite by default, PostgreSQL via config)."""

from collections.abc import AsyncIterator

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings


class Base(DeclarativeBase):
    pass


def _make_engine(url: str):
    kwargs: dict = {"pool_pre_ping": True}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"timeout": 30}
    engine = create_async_engine(url, **kwargs)
    if url.startswith("sqlite"):

        @event.listens_for(engine.sync_engine, "connect")
        def _sqlite_pragmas(dbapi_conn, _record):  # pragma: no cover - trivial
            # Let SQLAlchemy control BEGIN so we can use BEGIN IMMEDIATE (see below).
            dbapi_conn.isolation_level = None
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            cur.execute("PRAGMA journal_mode=WAL")
            cur.execute("PRAGMA busy_timeout=30000")
            cur.close()

        @event.listens_for(engine.sync_engine, "begin")
        def _sqlite_begin(conn):  # pragma: no cover - trivial
            # Take the write lock up front: concurrent writers wait (busy_timeout) instead of
            # failing with "database is locked" when a read transaction upgrades to a write.
            conn.exec_driver_sql("BEGIN IMMEDIATE")

    return engine


engine = _make_engine(get_settings().database_url)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


def configure_engine(url: str) -> None:
    """Re-point the global engine (used by tests)."""
    global engine, SessionLocal
    engine = _make_engine(url)
    SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


def session_factory() -> async_sessionmaker[AsyncSession]:
    return SessionLocal


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session
