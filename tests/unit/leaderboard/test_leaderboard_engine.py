"""Tests for deterministic leaderboard generation."""

from datetime import date

import pytest

from gamification_engine.domain.enums import BadgeType
from gamification_engine.domain.models import BadgeAssignment
from gamification_engine.leaderboard.leaderboard_engine import build_leaderboard


def test_build_leaderboard_sorts_by_points_descending_then_user_id() -> None:
    """Leaderboard order should be deterministic for equal scores."""

    leaderboard = build_leaderboard(
        {
            "U3": 300,
            "U2": 500,
            "U1": 500,
        }
    )

    assert [entry.to_dict() for entry in leaderboard] == [
        {"rank": 1, "user_id": "U1", "total_points": 500, "badges": []},
        {"rank": 2, "user_id": "U2", "total_points": 500, "badges": []},
        {"rank": 3, "user_id": "U3", "total_points": 300, "badges": []},
    ]


def test_build_leaderboard_assigns_consecutive_ranks() -> None:
    """Equal scores should not share rank in the MVP policy."""

    leaderboard = build_leaderboard({"U1": 100, "U2": 100, "U3": 100})

    assert [entry.rank for entry in leaderboard] == [1, 2, 3]


def test_build_leaderboard_includes_badges_in_tier_order() -> None:
    """Leaderboard entries should include earned badges in configured order."""

    leaderboard = build_leaderboard(
        {"U1": 3200},
        [
            BadgeAssignment(
                user_id="U1",
                badge_type=BadgeType.GOLD,
                awarded_at=date(2026, 3, 14),
            ),
            BadgeAssignment(
                user_id="U1",
                badge_type=BadgeType.BRONZE,
                awarded_at=date(2026, 3, 14),
            ),
            BadgeAssignment(
                user_id="U1",
                badge_type=BadgeType.SILVER,
                awarded_at=date(2026, 3, 14),
            ),
        ],
    )

    assert leaderboard[0].badges == (
        BadgeType.BRONZE,
        BadgeType.SILVER,
        BadgeType.GOLD,
    )


def test_build_leaderboard_ignores_badges_for_users_without_points() -> None:
    """A badge-only user should not appear without a point total."""

    leaderboard = build_leaderboard(
        {"U1": 500},
        [
            BadgeAssignment(
                user_id="U2",
                badge_type=BadgeType.BRONZE,
                awarded_at=date(2026, 3, 14),
            )
        ],
    )

    assert [entry.user_id for entry in leaderboard] == ["U1"]


def test_build_leaderboard_supports_optional_limit() -> None:
    """A non-negative limit should return only the first N users."""

    leaderboard = build_leaderboard({"U1": 300, "U2": 200, "U3": 100}, limit=2)

    assert [entry.user_id for entry in leaderboard] == ["U1", "U2"]


def test_build_leaderboard_rejects_negative_limit() -> None:
    """Negative limit values are invalid."""

    with pytest.raises(ValueError, match="limit"):
        build_leaderboard({"U1": 100}, limit=-1)


def test_build_leaderboard_returns_empty_list_for_empty_totals() -> None:
    """No point totals means no leaderboard entries."""

    assert build_leaderboard({}) == []

