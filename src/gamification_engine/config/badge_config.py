"""Badge threshold configuration."""

from dataclasses import dataclass

from gamification_engine.domain.enums import BadgeType


@dataclass(frozen=True, slots=True)
class BadgeThreshold:
    """Point threshold required for a badge tier."""

    badge_type: BadgeType
    required_points: int


BADGE_THRESHOLDS: tuple[BadgeThreshold, ...] = (
    BadgeThreshold(BadgeType.BRONZE, 500),
    BadgeThreshold(BadgeType.SILVER, 1500),
    BadgeThreshold(BadgeType.GOLD, 3000),
)
