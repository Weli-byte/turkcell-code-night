"""Enumerations used by the gamification domain models."""

from enum import StrEnum


class ChallengeType(StrEnum):
    """Supported challenge categories."""

    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    STREAK = "STREAK"


class BadgeType(StrEnum):
    """Supported badge tiers."""

    BRONZE = "BRONZE"
    SILVER = "SILVER"
    GOLD = "GOLD"


class RewardReason(StrEnum):
    """Reasons that can produce point ledger entries."""

    CHALLENGE_COMPLETED = "CHALLENGE_COMPLETED"
    MANUAL_ADJUSTMENT = "MANUAL_ADJUSTMENT"


class NotificationType(StrEnum):
    """Types of user-facing notification records."""

    CHALLENGE_REWARD = "CHALLENGE_REWARD"
    BADGE_EARNED = "BADGE_EARNED"


class NotificationChannel(StrEnum):
    """Supported notification channels for exported notification records."""

    IN_APP = "IN_APP"
    BIP = "BIP"
    EMAIL = "EMAIL"


class ChallengeStatus(StrEnum):
    """Evaluation status for a challenge decision."""

    TRIGGERED = "TRIGGERED"
    SELECTED = "SELECTED"
    SUPPRESSED = "SUPPRESSED"
    NOT_TRIGGERED = "NOT_TRIGGERED"
