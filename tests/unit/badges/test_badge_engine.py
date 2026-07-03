"""Tests for badge assignment engine."""

from datetime import date

import pytest

from gamification_engine.badges.badge_engine import (
    assign_badges,
    get_earned_badge_types,
)
from gamification_engine.config.badge_config import BadgeThreshold
from gamification_engine.domain.enums import BadgeType
from gamification_engine.domain.errors import ConfigurationError
from gamification_engine.domain.models import BadgeAssignment


def test_get_earned_badge_types_returns_all_crossed_thresholds() -> None:
    """A user earns every badge tier whose threshold is reached."""

    assert get_earned_badge_types(499) == ()
    assert get_earned_badge_types(500) == (BadgeType.BRONZE,)
    assert get_earned_badge_types(3000) == (
        BadgeType.BRONZE,
        BadgeType.SILVER,
        BadgeType.GOLD,
    )


def test_assign_badges_awards_missing_badges_in_tier_order() -> None:
    """Crossing multiple thresholds should award all missing tiers."""

    new_badges, all_badges = assign_badges(
        {"U1": 3200},
        existing_badges=[],
        run_date=date(2026, 3, 14),
    )

    assert [badge.badge_type for badge in new_badges] == [
        BadgeType.BRONZE,
        BadgeType.SILVER,
        BadgeType.GOLD,
    ]
    assert new_badges == all_badges
    assert all(
        badge.badge_id and badge.badge_id.startswith("badge-") for badge in new_badges
    )


def test_assign_badges_does_not_duplicate_existing_badge() -> None:
    """An already awarded badge should not be emitted again."""

    existing = [
        BadgeAssignment(
            user_id="U1",
            badge_type=BadgeType.BRONZE,
            awarded_at=date(2026, 3, 1),
            badge_id="badge-existing",
        )
    ]

    new_badges, all_badges = assign_badges(
        {"U1": 1600},
        existing_badges=existing,
        run_date=date(2026, 3, 14),
    )

    assert [badge.badge_type for badge in new_badges] == [BadgeType.SILVER]
    assert all_badges[0] == existing[0]
    assert all_badges[1].badge_type is BadgeType.SILVER


def test_assign_badges_is_deterministic() -> None:
    """Same inputs should produce the same badge IDs and ordering."""

    first_new, first_all = assign_badges(
        {"U2": 500, "U1": 1500},
        existing_badges=[],
        run_date=date(2026, 3, 14),
    )
    second_new, second_all = assign_badges(
        {"U1": 1500, "U2": 500},
        existing_badges=[],
        run_date=date(2026, 3, 14),
    )

    assert first_new == second_new
    assert first_all == second_all


def test_assign_badges_returns_no_new_badges_below_threshold() -> None:
    """Users below Bronze should not receive a badge."""

    new_badges, all_badges = assign_badges(
        {"U1": 499},
        existing_badges=[],
        run_date=date(2026, 3, 14),
    )

    assert new_badges == []
    assert all_badges == []


def test_get_earned_badge_types_rejects_invalid_threshold_config() -> None:
    """Threshold configuration should be validated."""

    with pytest.raises(ConfigurationError, match="ordered"):
        get_earned_badge_types(
            1000,
            thresholds=(
                BadgeThreshold(BadgeType.SILVER, 1500),
                BadgeThreshold(BadgeType.BRONZE, 500),
            ),
        )
