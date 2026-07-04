"""Tests for challenge CSV seeding and listing."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session

from gamification_backend.db.models import ChallengeRecord
from gamification_backend.repositories.challenges import (
    list_active_challenges,
    seed_challenges_from_csv,
)


def test_seed_inserts_all_challenges(session: Session, challenges_csv: Path) -> None:
    inserted = seed_challenges_from_csv(session, challenges_csv)

    assert inserted == 6


def test_seed_is_idempotent(session: Session, challenges_csv: Path) -> None:
    seed_challenges_from_csv(session, challenges_csv)

    assert seed_challenges_from_csv(session, challenges_csv) == 0


def test_seed_preserves_existing_rows(session: Session, challenges_csv: Path) -> None:
    seed_challenges_from_csv(session, challenges_csv)

    record = session.get(ChallengeRecord, "CH-001")
    assert record is not None
    record.reward_points = 999
    session.commit()

    seed_challenges_from_csv(session, challenges_csv)

    refreshed = session.get(ChallengeRecord, "CH-001")
    assert refreshed is not None
    assert refreshed.reward_points == 999


def test_active_challenges_ordered_by_priority_then_id(
    session: Session, challenges_csv: Path
) -> None:
    seed_challenges_from_csv(session, challenges_csv)

    active = list_active_challenges(session)

    assert [c.challenge_id for c in active] == [
        "CH-004",
        "CH-003",
        "CH-005",
        "CH-002",
        "CH-001",
    ]
    # CH-006 is inactive in the sample data and must be excluded.
    assert all(c.is_active for c in active)
