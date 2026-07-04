"""Tests for the append-only ledger repository and its database guards."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.exc import DatabaseError
from sqlalchemy.orm import Session

from gamification_backend.repositories.ledger import AppendOnlyLedgerRepository

from .conftest import UserFactory

CREATED_AT = datetime(2026, 7, 4, 12, 0, 0, tzinfo=UTC)


def _append(
    repo: AppendOnlyLedgerRepository,
    *,
    ledger_id: str = "L-001",
    user_id: str = "u001",
    points_delta: int = 80,
    source_ref: str = "RW-001",
) -> bool:
    return repo.append(
        ledger_id=ledger_id,
        user_id=user_id,
        points_delta=points_delta,
        source="CHALLENGE_COMPLETED",
        source_ref=source_ref,
        created_at=CREATED_AT,
    )


def test_append_writes_entry(session: Session, make_user: UserFactory) -> None:
    make_user()
    repo = AppendOnlyLedgerRepository(session)

    assert _append(repo) is True

    entries = repo.entries_for_user("u001")
    assert len(entries) == 1
    assert entries[0].ledger_id == "L-001"
    assert entries[0].points_delta == 80


def test_duplicate_source_ref_is_idempotent(
    session: Session, make_user: UserFactory
) -> None:
    make_user()
    repo = AppendOnlyLedgerRepository(session)

    assert _append(repo) is True
    assert _append(repo, ledger_id="L-002") is False

    assert len(repo.entries_for_user("u001")) == 1
    assert repo.total_points("u001") == 80


def test_same_source_ref_for_different_users_is_allowed(
    session: Session, make_user: UserFactory
) -> None:
    make_user("u001")
    make_user("u002")
    repo = AppendOnlyLedgerRepository(session)

    assert _append(repo) is True
    assert _append(repo, ledger_id="L-002", user_id="u002") is True


def test_non_positive_delta_is_rejected(
    session: Session, make_user: UserFactory
) -> None:
    make_user()
    repo = AppendOnlyLedgerRepository(session)

    with pytest.raises(ValueError, match="positive"):
        _append(repo, points_delta=0)
    with pytest.raises(ValueError, match="positive"):
        _append(repo, points_delta=-50)
    assert repo.entries_for_user("u001") == []


def test_total_points_sums_all_entries(
    session: Session, make_user: UserFactory
) -> None:
    make_user()
    repo = AppendOnlyLedgerRepository(session)

    assert repo.total_points("u001") == 0
    _append(repo)
    _append(repo, ledger_id="L-002", source_ref="RW-002", points_delta=150)

    assert repo.total_points("u001") == 230


def test_repository_exposes_no_update_or_delete(session: Session) -> None:
    repo = AppendOnlyLedgerRepository(session)

    mutating = [
        name
        for name in dir(repo)
        if not name.startswith("_")
        and any(verb in name.lower() for verb in ("update", "delete", "remove"))
    ]
    assert mutating == []


def test_raw_update_is_blocked_by_trigger(
    engine: Engine, session: Session, make_user: UserFactory
) -> None:
    make_user()
    _append(AppendOnlyLedgerRepository(session))

    with engine.connect() as connection:
        with pytest.raises(DatabaseError, match="append-only"):
            connection.execute(text("UPDATE points_ledger SET points_delta = 9999"))


def test_raw_delete_is_blocked_by_trigger(
    engine: Engine, session: Session, make_user: UserFactory
) -> None:
    make_user()
    _append(AppendOnlyLedgerRepository(session))

    with engine.connect() as connection:
        with pytest.raises(DatabaseError, match="append-only"):
            connection.execute(text("DELETE FROM points_ledger"))
