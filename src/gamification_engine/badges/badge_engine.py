"""Badge assignment engine."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from datetime import date

from gamification_engine.config.badge_config import (
    BADGE_THRESHOLDS,
    BadgeThreshold,
)
from gamification_engine.domain.enums import BadgeType
from gamification_engine.domain.errors import ConfigurationError
from gamification_engine.domain.models import BadgeAssignment


def get_earned_badge_types(
    total_points: int,
    thresholds: tuple[BadgeThreshold, ...] = BADGE_THRESHOLDS,
) -> tuple[BadgeType, ...]:
    """Return badge tiers earned for a total point value."""

    _validate_thresholds(thresholds)
    if total_points < 0:
        return ()

    return tuple(
        threshold.badge_type
        for threshold in thresholds
        if total_points >= threshold.required_points
    )


def assign_badges(
    user_total_points: dict[str, int],
    existing_badges: Iterable[BadgeAssignment],
    run_date: date,
    thresholds: tuple[BadgeThreshold, ...] = BADGE_THRESHOLDS,
) -> tuple[list[BadgeAssignment], list[BadgeAssignment]]:
    """Assign missing earned badges without duplicating existing awards.

    Args:
        user_total_points: Total points by user from the points ledger.
        existing_badges: Previously awarded badges.
        run_date: Business date used for newly awarded badges.
        thresholds: Ordered badge threshold configuration.

    Returns:
        A tuple of ``(new_badges, all_badges)``.
    """

    _validate_thresholds(thresholds)
    existing = sort_badge_assignments(existing_badges)
    awarded_keys = {(badge.user_id, badge.badge_type) for badge in existing}

    new_badges: list[BadgeAssignment] = []
    for user_id, total_points in sorted(user_total_points.items()):
        for badge_type in get_earned_badge_types(total_points, thresholds):
            key = (user_id, badge_type)
            if key in awarded_keys:
                continue

            awarded_keys.add(key)
            new_badges.append(
                BadgeAssignment(
                    user_id=user_id,
                    badge_type=badge_type,
                    awarded_at=run_date,
                    badge_id=_build_badge_id(user_id, badge_type),
                )
            )

    sorted_new = sort_badge_assignments(new_badges)
    return sorted_new, sort_badge_assignments([*existing, *sorted_new])


def sort_badge_assignments(
    badges: Iterable[BadgeAssignment],
) -> list[BadgeAssignment]:
    """Return badge assignments in deterministic output order."""

    return sorted(
        badges,
        key=lambda badge: (
            badge.awarded_at,
            badge.user_id,
            _badge_order(badge.badge_type),
            badge.badge_id or "",
        ),
    )


def _badge_order(badge_type: BadgeType) -> int:
    ordered_types = [threshold.badge_type for threshold in BADGE_THRESHOLDS]
    return ordered_types.index(badge_type)


def _build_badge_id(user_id: str, badge_type: BadgeType) -> str:
    raw_key = f"{user_id}|{badge_type.value}"
    digest = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()[:16]
    return f"badge-{digest}"


def _validate_thresholds(thresholds: tuple[BadgeThreshold, ...]) -> None:
    if not thresholds:
        raise ConfigurationError("At least one badge threshold is required.")

    seen_badges: set[BadgeType] = set()
    previous_points = -1
    for threshold in thresholds:
        if threshold.badge_type in seen_badges:
            raise ConfigurationError(
                f"Duplicate badge threshold: {threshold.badge_type.value}."
            )
        if threshold.required_points <= 0:
            raise ConfigurationError("Badge thresholds must be positive.")
        if threshold.required_points <= previous_points:
            raise ConfigurationError(
                "Badge thresholds must be ordered by increasing points."
            )

        seen_badges.add(threshold.badge_type)
        previous_points = threshold.required_points
