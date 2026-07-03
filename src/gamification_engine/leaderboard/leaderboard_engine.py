"""Build deterministic leaderboard entries from point totals."""

from __future__ import annotations

from collections.abc import Iterable

from gamification_engine.config.badge_config import BADGE_THRESHOLDS
from gamification_engine.domain.enums import BadgeType
from gamification_engine.domain.models import BadgeAssignment, LeaderboardEntry


def build_leaderboard(
    user_total_points: dict[str, int],
    badge_assignments: Iterable[BadgeAssignment] = (),
    limit: int | None = None,
) -> list[LeaderboardEntry]:
    """Build a deterministic leaderboard from user point totals.

    Users are sorted by total points descending and then by ``user_id``
    ascending. Ranks are assigned consecutively starting at 1.
    """

    if limit is not None and limit < 0:
        raise ValueError("limit must be non-negative when provided.")

    badge_map = _build_user_badge_map(badge_assignments)
    sorted_totals = sorted(
        user_total_points.items(),
        key=lambda item: (-item[1], item[0]),
    )

    if limit is not None:
        sorted_totals = sorted_totals[:limit]

    return [
        LeaderboardEntry(
            rank=index,
            user_id=user_id,
            total_points=total_points,
            badges=badge_map.get(user_id, ()),
        )
        for index, (user_id, total_points) in enumerate(sorted_totals, start=1)
    ]


def _build_user_badge_map(
    badge_assignments: Iterable[BadgeAssignment],
) -> dict[str, tuple[BadgeType, ...]]:
    badges_by_user: dict[str, set[BadgeType]] = {}
    for assignment in badge_assignments:
        badges_by_user.setdefault(assignment.user_id, set()).add(assignment.badge_type)

    return {
        user_id: tuple(
            badge_type for badge_type in _badge_order() if badge_type in badge_types
        )
        for user_id, badge_types in sorted(badges_by_user.items())
    }


def _badge_order() -> tuple[BadgeType, ...]:
    return tuple(threshold.badge_type for threshold in BADGE_THRESHOLDS)
