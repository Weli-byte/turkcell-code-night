"""Domain models, errors, and core business types."""

from gamification_engine.domain.enums import (
    BadgeType,
    ChallengeStatus,
    ChallengeType,
    NotificationChannel,
    NotificationType,
    RewardReason,
)
from gamification_engine.domain.errors import (
    ConfigurationError,
    DomainError,
    GamificationEngineError,
    IngestionError,
    IntegrityValidationError,
    RuleEvaluationError,
)
from gamification_engine.domain.models import (
    BadgeAssignment,
    ChallengeDecision,
    ChallengeDefinition,
    DailyUserState,
    ExplanationResponse,
    LeaderboardEntry,
    Notification,
    PointsLedgerEntry,
    RewardEvent,
    UserActivity,
)

__all__ = [
    "BadgeAssignment",
    "BadgeType",
    "ChallengeDecision",
    "ChallengeDefinition",
    "ChallengeStatus",
    "ChallengeType",
    "ConfigurationError",
    "DailyUserState",
    "DomainError",
    "ExplanationResponse",
    "GamificationEngineError",
    "IngestionError",
    "IntegrityValidationError",
    "LeaderboardEntry",
    "Notification",
    "NotificationChannel",
    "NotificationType",
    "PointsLedgerEntry",
    "RewardEvent",
    "RewardReason",
    "RuleEvaluationError",
    "UserActivity",
]
