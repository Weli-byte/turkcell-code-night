"""Shared fixtures for backend service tests (in-memory SQLite)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Protocol

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from gamification_backend.config import BackendSettings
from gamification_backend.db.base import (
    create_db_engine,
    create_session_factory,
    init_database,
)
from gamification_backend.db.models import UserRecord

_REPO_ROOT = Path(__file__).resolve().parents[2]


class UserFactory(Protocol):
    """Callable fixture type: creates a committed user row."""

    def __call__(self, user_id: str = "u001") -> UserRecord:
        """Insert and return a user with the given id/username."""
        ...


@pytest.fixture()
def engine() -> Iterator[Engine]:
    """Initialized in-memory SQLite engine (schema + append-only guards)."""

    engine = create_db_engine("sqlite://")
    init_database(engine)
    yield engine
    engine.dispose()


@pytest.fixture()
def session(engine: Engine) -> Iterator[Session]:
    """Database session bound to the in-memory engine."""

    factory = create_session_factory(engine)
    with factory() as session:
        yield session


@pytest.fixture()
def challenges_csv() -> Path:
    """Path to the committed sample challenge definitions."""

    return _REPO_ROOT / "data" / "input" / "challenges.csv"


@pytest.fixture()
def test_settings(challenges_csv: Path) -> BackendSettings:
    """Settings pointing at an in-memory database and the sample CSV."""

    return BackendSettings(
        database_url="sqlite://",
        challenges_csv=challenges_csv,
        seed_on_startup=True,
    )


@pytest.fixture()
def make_user(session: Session) -> UserFactory:
    """Factory inserting a minimal user row (FK target for other tables)."""

    def _make(user_id: str = "u001") -> UserRecord:
        user = UserRecord(id=user_id, username=user_id)
        session.add(user)
        session.commit()
        return user

    return _make
