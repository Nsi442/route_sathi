"""SQLAlchemy engine/session management.

The engine is configured for serverless execution: no long-lived pool is kept
open, and Neon's pooled endpoint is expected in production.
"""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from backend.core.config import settings

_connect_args: dict = {}
_engine_kwargs: dict = {"pool_pre_ping": True, "future": True}

if settings.is_postgres:
    # NullPool-like behaviour: serverless functions are frozen between
    # invocations, so a small recycled pool avoids stale sockets on Neon.
    _engine_kwargs.update(pool_size=1, max_overflow=2, pool_recycle=280)
    _connect_args = {"connect_timeout": 10}
else:
    _connect_args = {"check_same_thread": False}

engine: Engine = create_engine(
    settings.database_url, connect_args=_connect_args, **_engine_kwargs
)

if not settings.is_postgres:

    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_connection, _record):  # pragma: no cover - trivial
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db() -> Iterator[Session]:
    """FastAPI dependency yielding a request-scoped session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
