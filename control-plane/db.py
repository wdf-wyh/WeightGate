"""SQLAlchemy engine + session (Postgres in compose; SQLite for local/tests)."""

from __future__ import annotations

import os
from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

_ENGINE = None
_SessionLocal: sessionmaker[Session] | None = None


class Base(DeclarativeBase):
    pass


def database_url() -> str:
    url = os.environ.get("DATABASE_URL", "").strip()
    if url:
        # SQLAlchemy 2 prefers postgresql+psycopg://
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+psycopg://", 1)
        return url
    # In-memory SQLite when unset (unit tests / offline smoke)
    return "sqlite+pysqlite:///:memory:"


def get_engine():
    global _ENGINE, _SessionLocal
    if _ENGINE is None:
        url = database_url()
        kwargs: dict = {"future": True}
        if url.startswith("sqlite"):
            kwargs["connect_args"] = {"check_same_thread": False}
            # Keep a single connection so :memory: schema persists across sessions
            if ":memory:" in url:
                from sqlalchemy.pool import StaticPool

                kwargs["poolclass"] = StaticPool
        _ENGINE = create_engine(url, **kwargs)
        if url.startswith("sqlite"):

            @event.listens_for(_ENGINE, "connect")
            def _fk_on(dbapi_conn, _):  # type: ignore[no-untyped-def]
                cursor = dbapi_conn.cursor()
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.close()

        _SessionLocal = sessionmaker(bind=_ENGINE, autoflush=False, autocommit=False, future=True)
    return _ENGINE


def get_session_factory() -> sessionmaker[Session]:
    get_engine()
    assert _SessionLocal is not None
    return _SessionLocal


def init_db() -> None:
    # Import models so metadata is populated
    from models import (  # noqa: F401
        AlertRow,
        ApiKeyRow,
        HostRow,
        InstanceRow,
        LicenseRow,
        RoutePolicyRow,
        TenantRow,
        UsageEventRow,
    )

    Base.metadata.create_all(bind=get_engine())


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    factory = get_session_factory()
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def reset_engine_for_tests() -> None:
    """Drop cached engine (tests that change DATABASE_URL)."""
    global _ENGINE, _SessionLocal
    if _ENGINE is not None:
        _ENGINE.dispose()
    _ENGINE = None
    _SessionLocal = None
