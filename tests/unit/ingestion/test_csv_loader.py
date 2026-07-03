"""Tests for CSV loader functions."""

from pathlib import Path

import pytest

from gamification_engine.domain.errors import IngestionError
from gamification_engine.ingestion.csv_loader import (
    load_challenge_definitions_csv,
    load_user_activities_csv,
)

FIXTURES_DIR = Path(__file__).resolve().parents[2] / "fixtures"


def test_load_user_activities_csv_returns_deterministic_order() -> None:
    """Activities should be normalized into stable order after loading."""

    activities = load_user_activities_csv(FIXTURES_DIR / "valid_user_activities.csv")

    assert [activity.event_id for activity in activities] == ["AE-1", "AE-3", "AE-2"]
    assert activities[0].activity_date.isoformat() == "2026-03-08"


def test_load_challenge_definitions_csv_returns_deterministic_order() -> None:
    """Challenges should be sorted by challenge ID after loading."""

    challenges = load_challenge_definitions_csv(FIXTURES_DIR / "valid_challenges.csv")

    assert [challenge.challenge_id for challenge in challenges] == [
        "C-01",
        "C-02",
        "C-03",
    ]


def test_load_user_activities_csv_rejects_invalid_rows() -> None:
    """Invalid activity values should fail ingestion."""

    with pytest.raises(IngestionError, match="watch_minutes"):
        load_user_activities_csv(FIXTURES_DIR / "invalid_user_activities.csv")


def test_load_challenge_definitions_csv_rejects_duplicate_ids() -> None:
    """Challenge IDs must be unique."""

    with pytest.raises(IngestionError, match="Duplicate challenge_id"):
        load_challenge_definitions_csv(FIXTURES_DIR / "invalid_challenges.csv")


def test_load_csv_rejects_missing_file() -> None:
    """Missing input files should produce an ingestion error."""

    with pytest.raises(IngestionError, match="does not exist"):
        load_user_activities_csv(FIXTURES_DIR / "missing.csv")
