"""Tests for CSV ingestion validators."""

import pytest

from gamification_engine.domain.enums import ChallengeType
from gamification_engine.domain.errors import IngestionError
from gamification_engine.ingestion.schemas import USER_ACTIVITY_SCHEMA
from gamification_engine.ingestion.validators import (
    parse_challenge_definition_row,
    parse_user_activity_row,
    validate_headers,
)


def test_validate_headers_accepts_required_columns_with_extra_columns() -> None:
    """Extra CSV columns should not break ingestion."""

    headers = [*USER_ACTIVITY_SCHEMA.required_headers, "extra_column"]

    validate_headers(headers, USER_ACTIVITY_SCHEMA)


def test_validate_headers_rejects_missing_required_column() -> None:
    """Required CSV columns must be present."""

    headers = sorted(USER_ACTIVITY_SCHEMA.required_headers - {"watch_minutes"})

    with pytest.raises(IngestionError, match="watch_minutes"):
        validate_headers(headers, USER_ACTIVITY_SCHEMA)


def test_parse_user_activity_row_maps_csv_fields_to_domain_model() -> None:
    """Activity CSV rows should parse into UserActivity models."""

    activity = parse_user_activity_row(
        {
            "event_id": "AE-1",
            "user_id": "U1",
            "date": "2026-03-08",
            "shows_watched": "S2|S3",
            "unique_genres": "2",
            "watch_minutes": "142",
            "episodes_completed": "2",
            "watch_party_minutes": "60",
            "ratings": "2",
        },
        row_number=2,
    )

    assert activity.user_id == "U1"
    assert activity.shows_watched == ("S2", "S3")
    assert activity.ratings_given == 2


def test_parse_user_activity_row_rejects_bad_date() -> None:
    """Dates must use ISO calendar format."""

    with pytest.raises(IngestionError, match="YYYY-MM-DD"):
        parse_user_activity_row(
            {
                "event_id": "AE-1",
                "user_id": "U1",
                "date": "08/03/2026",
                "shows_watched": "S2",
                "unique_genres": "1",
                "watch_minutes": "142",
                "episodes_completed": "2",
                "watch_party_minutes": "60",
                "ratings": "2",
            },
            row_number=2,
        )


def test_parse_challenge_definition_row_maps_csv_fields() -> None:
    """Challenge rows should parse into typed challenge definitions."""

    challenge = parse_challenge_definition_row(
        {
            "challenge_id": "C-01",
            "challenge_name": "Daily Watcher",
            "challenge_type": "daily",
            "condition": "watch_minutes_today >= 60",
            "reward_points": "80",
            "priority": "5",
            "is_active": "yes",
        },
        row_number=2,
    )

    assert challenge.challenge_type is ChallengeType.DAILY
    assert challenge.is_active is True


def test_parse_challenge_definition_row_rejects_unknown_type() -> None:
    """Only supported challenge types should be accepted."""

    with pytest.raises(IngestionError, match="challenge_type"):
        parse_challenge_definition_row(
            {
                "challenge_id": "C-01",
                "challenge_name": "Daily Watcher",
                "challenge_type": "MONTHLY",
                "condition": "watch_minutes_today >= 60",
                "reward_points": "80",
                "priority": "5",
                "is_active": "true",
            },
            row_number=2,
        )

