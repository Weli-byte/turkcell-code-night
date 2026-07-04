"""Engine/session construction and database initialization.

Responsibilities:

- Build a SQLAlchemy engine with SQLite pragmas suitable for a threaded
  web service (foreign keys ON, shared in-memory pool for tests).
- Create the schema and install the append-only triggers protecting the
  ``points_ledger`` table: any ``UPDATE`` or ``DELETE`` is aborted at the
  database level, so even raw SQL cannot rewrite point history.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from gamification_backend.db.models import Base

_APPEND_ONLY_TABLES = ("points_ledger",)


def create_db_engine(database_url: str) -> Engine:
    """Create a SQLAlchemy engine configured for the given URL.

    SQLite URLs get ``check_same_thread=False`` (FastAPI serves requests
    from a thread pool) and in-memory URLs additionally share a single
    connection via ``StaticPool`` so all sessions see the same database.
    """

    kwargs: dict[str, Any] = {}
    if database_url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
        if database_url in ("sqlite://", "sqlite:///:memory:"):
            kwargs["poolclass"] = StaticPool
    engine = create_engine(database_url, **kwargs)
    if database_url.startswith("sqlite"):
        _enable_sqlite_foreign_keys(engine)
    return engine


def _enable_sqlite_foreign_keys(engine: Engine) -> None:
    """Turn on foreign-key enforcement for every SQLite connection."""

    @event.listens_for(engine, "connect")
    def _set_pragma(dbapi_connection: Any, _record: Any) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def init_database(engine: Engine) -> None:
    """Create all tables and install append-only guard triggers."""

    Base.metadata.create_all(engine)
    if engine.dialect.name == "sqlite":
        _install_append_only_guards(engine)


def _install_append_only_guards(engine: Engine) -> None:
    """Abort UPDATE/DELETE on append-only tables via SQLite triggers."""

    with engine.begin() as connection:
        for table in _APPEND_ONLY_TABLES:
            for operation in ("UPDATE", "DELETE"):
                connection.execute(
                    text(
                        f"CREATE TRIGGER IF NOT EXISTS "
                        f"{table}_block_{operation.lower()} "
                        f"BEFORE {operation} ON {table} "
                        f"BEGIN "
                        f"SELECT RAISE(ABORT, '{table} is append-only'); "
                        f"END"
                    )
                )


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Build the session factory used by API dependencies and services."""

    return sessionmaker(bind=engine, expire_on_commit=False)
