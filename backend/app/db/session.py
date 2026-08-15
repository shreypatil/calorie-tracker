"""Database engine and session factory.

SQLite needs two pragmas set per connection to behave sanely: foreign keys are
off by default, and WAL journaling avoids reader/writer lock contention. Both
are no-ops on other backends, which is why the swap to PostgreSQL is only a URL
change.
"""

from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


def _sqlite_file_path(database_url: str) -> Path | None:
    prefix = "sqlite:///"
    if not database_url.startswith(prefix):
        return None
    path = database_url[len(prefix) :]
    return None if path == ":memory:" else Path(path)


def ensure_sqlite_directory(database_url: str) -> None:
    """Create the parent directory of a SQLite file if it is missing.

    Called by both the app engine factory and Alembic's env.py — Alembic builds
    its own engine, so it would otherwise fail on a fresh clone where `data/`
    does not exist yet.
    """
    if (file_path := _sqlite_file_path(database_url)) is not None:
        file_path.parent.mkdir(parents=True, exist_ok=True)


def create_db_engine(database_url: str | None = None) -> Engine:
    settings = get_settings()
    url = database_url or settings.database_url

    connect_args: dict = {}
    if url.startswith("sqlite"):
        # FastAPI runs sync endpoints across a threadpool, so connections are
        # legitimately used from more than one thread.
        connect_args["check_same_thread"] = False
        ensure_sqlite_directory(url)

    engine = create_engine(url, connect_args=connect_args, pool_pre_ping=True, future=True)

    if url.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def _set_sqlite_pragmas(dbapi_connection, _connection_record) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.close()

    return engine


engine = create_db_engine()
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, class_=Session)


def get_db() -> Iterator[Session]:
    """FastAPI dependency yielding a session that is always closed."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
