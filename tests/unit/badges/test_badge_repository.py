"""Tests for badge assignment JSON repository."""

import json
from datetime import date

import pytest

from gamification_engine.badges.badge_repository import (
    load_badge_assignments_json,
    write_badge_assignments_json,
)
from gamification_engine.domain.enums import BadgeType
from gamification_engine.domain.errors import IngestionError
from gamification_engine.domain.models import BadgeAssignment


def test_load_badge_assignments_json_returns_empty_for_missing_file(tmp_path) -> None:
    """A missing badge file represents empty history."""

    assert load_badge_assignments_json(tmp_path / "missing.json") == []


def test_write_and_load_badge_assignments_json_round_trips(tmp_path) -> None:
    """Repository should persist and restore badge assignments."""

    badges = [
        BadgeAssignment(
            user_id="U1",
            badge_type=BadgeType.BRONZE,
            awarded_at=date(2026, 3, 14),
            badge_id="badge-u1-bronze",
        )
    ]
    path = tmp_path / "badges.json"

    write_badge_assignments_json(path, badges)
    loaded_badges = load_badge_assignments_json(path)

    assert loaded_badges == badges
    raw_payload = json.loads(path.read_text(encoding="utf-8"))
    assert raw_payload[0]["badge_type"] == "BRONZE"


def test_load_badge_assignments_json_rejects_non_list_payload(tmp_path) -> None:
    """Badge JSON top-level payload must be a list."""

    path = tmp_path / "badges.json"
    path.write_text("{}", encoding="utf-8")

    with pytest.raises(IngestionError, match="must contain a list"):
        load_badge_assignments_json(path)


def test_load_badge_assignments_json_rejects_invalid_assignment(tmp_path) -> None:
    """Invalid badge assignments should fail ingestion."""

    path = tmp_path / "badges.json"
    path.write_text('[{"user_id": "U1", "badge_type": "PLATINUM"}]', encoding="utf-8")

    with pytest.raises(IngestionError, match="Invalid badge assignment"):
        load_badge_assignments_json(path)
