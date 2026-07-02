"""Typed domain models for the deterministic gamification engine.

The models in this module define data contracts and basic invariants only.
They do not evaluate rules, award points, assign badges, or build leaderboards.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from gamification_engine.domain.enums import (
    BadgeType,
    ChallengeStatus,
    ChallengeType,
    NotificationChannel,
    NotificationType,
    RewardReason,
)
from gamification_engine.domain.errors import DomainError


def _require_non_empty(value: str, field_name: str) -> str:
    """Validate that a string field is not empty."""

    normalized = value.strip()
    if not normalized:
        raise DomainError(f"{field_name} must not be empty.")
    return normalized


def _require_non_negative(value: int, field_name: str) -> int:
    """Validate that an integer field is zero or positive."""

    if value < 0:
        raise DomainError(f"{field_name} must be non-negative.")
    return value


def _require_positive(value: int, field_name: str) -> int:
    """Validate that an integer field is greater than zero."""

    if value <= 0:
        raise DomainError(f"{field_name} must be positive.")
    return value


def _serialize(value: Any) -> Any:
    """Convert domain values into JSON-compatible primitives."""

    if isinstance(value, date | datetime):
        return value.isoformat()
    if hasattr(value, "value"):
        return value.value
    if isinstance(value, list):
        return [_serialize(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _serialize(item) for key, item in value.items()}
    return value


@dataclass(frozen=True, slots=True)
class UserActivity:
    """Raw user engagement activity for a single user and date."""

    user_id: str
    activity_date: date
    watch_minutes: int
    episodes_completed: int
    unique_genres: int
    watch_party_minutes: int
    ratings_given: int
    event_id: str | None = None
    shows_watched: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        """Validate raw activity invariants."""

        object.__setattr__(self, "user_id", _require_non_empty(self.user_id, "user_id"))
        if self.event_id is not None:
            object.__setattr__(
                self,
                "event_id",
                _require_non_empty(self.event_id, "event_id"),
            )
        for field_name in (
            "watch_minutes",
            "episodes_completed",
            "unique_genres",
            "watch_party_minutes",
            "ratings_given",
        ):
            object.__setattr__(
                self,
                field_name,
                _require_non_negative(getattr(self, field_name), field_name),
            )
        object.__setattr__(
            self,
            "shows_watched",
            tuple(show.strip() for show in self.shows_watched if show.strip()),
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible representation."""

        return {
            "event_id": self.event_id,
            "user_id": self.user_id,
            "activity_date": self.activity_date.isoformat(),
            "watch_minutes": self.watch_minutes,
            "episodes_completed": self.episodes_completed,
            "unique_genres": self.unique_genres,
            "watch_party_minutes": self.watch_party_minutes,
            "ratings_given": self.ratings_given,
            "shows_watched": list(self.shows_watched),
        }


@dataclass(frozen=True, slots=True)
class ChallengeDefinition:
    """Configured challenge definition loaded from input data."""

    challenge_id: str
    name: str
    challenge_type: ChallengeType
    condition: str
    reward_points: int
    priority: int
    is_active: bool

    def __post_init__(self) -> None:
        """Validate challenge configuration invariants."""

        object.__setattr__(
            self,
            "challenge_id",
            _require_non_empty(self.challenge_id, "challenge_id"),
        )
        object.__setattr__(self, "name", _require_non_empty(self.name, "name"))
        object.__setattr__(
            self,
            "condition",
            _require_non_empty(self.condition, "condition"),
        )
        object.__setattr__(
            self,
            "reward_points",
            _require_positive(self.reward_points, "reward_points"),
        )
        object.__setattr__(
            self,
            "priority",
            _require_positive(self.priority, "priority"),
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible representation."""

        return {
            "challenge_id": self.challenge_id,
            "name": self.name,
            "challenge_type": self.challenge_type.value,
            "condition": self.condition,
            "reward_points": self.reward_points,
            "priority": self.priority,
            "is_active": self.is_active,
        }


@dataclass(frozen=True, slots=True)
class DailyUserState:
    """Derived engagement state for a user on a run date."""

    user_id: str
    state_date: date
    watch_minutes_today: int
    watch_minutes_7d: int
    episodes_completed_today: int
    episodes_completed_7d: int
    unique_genres_today: int
    watch_party_minutes_today: int
    ratings_today: int
    ratings_7d: int
    watch_streak_days: int

    def __post_init__(self) -> None:
        """Validate computed state metrics."""

        object.__setattr__(self, "user_id", _require_non_empty(self.user_id, "user_id"))
        for field_name in (
            "watch_minutes_today",
            "watch_minutes_7d",
            "episodes_completed_today",
            "episodes_completed_7d",
            "unique_genres_today",
            "watch_party_minutes_today",
            "ratings_today",
            "ratings_7d",
            "watch_streak_days",
        ):
            object.__setattr__(
                self,
                field_name,
                _require_non_negative(getattr(self, field_name), field_name),
            )

    def to_rule_context(self) -> dict[str, int]:
        """Return fields that are allowed to be referenced by challenge rules."""

        return {
            "watch_minutes_today": self.watch_minutes_today,
            "watch_minutes_7d": self.watch_minutes_7d,
            "episodes_completed_today": self.episodes_completed_today,
            "episodes_completed_7d": self.episodes_completed_7d,
            "unique_genres_today": self.unique_genres_today,
            "watch_party_minutes_today": self.watch_party_minutes_today,
            "ratings_today": self.ratings_today,
            "ratings_7d": self.ratings_7d,
            "watch_streak_days": self.watch_streak_days,
        }

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible representation."""

        return {
            "user_id": self.user_id,
            "state_date": self.state_date.isoformat(),
            **self.to_rule_context(),
        }


@dataclass(frozen=True, slots=True)
class ChallengeDecision:
    """Result of evaluating one challenge for one user."""

    user_id: str
    challenge_id: str
    status: ChallengeStatus
    evaluated_at: date
    reason: str

    def __post_init__(self) -> None:
        """Validate challenge decision fields."""

        object.__setattr__(self, "user_id", _require_non_empty(self.user_id, "user_id"))
        object.__setattr__(
            self,
            "challenge_id",
            _require_non_empty(self.challenge_id, "challenge_id"),
        )
        object.__setattr__(self, "reason", _require_non_empty(self.reason, "reason"))

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible representation."""

        return {
            "user_id": self.user_id,
            "challenge_id": self.challenge_id,
            "status": self.status.value,
            "evaluated_at": self.evaluated_at.isoformat(),
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class RewardEvent:
    """Selected reward candidate produced after challenge priority resolution."""

    reward_id: str
    user_id: str
    challenge_id: str
    reward_points: int
    reward_date: date
    reason: RewardReason
    suppressed_challenge_ids: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        """Validate reward event fields."""

        object.__setattr__(
            self,
            "reward_id",
            _require_non_empty(self.reward_id, "reward_id"),
        )
        object.__setattr__(self, "user_id", _require_non_empty(self.user_id, "user_id"))
        object.__setattr__(
            self,
            "challenge_id",
            _require_non_empty(self.challenge_id, "challenge_id"),
        )
        object.__setattr__(
            self,
            "reward_points",
            _require_positive(self.reward_points, "reward_points"),
        )
        object.__setattr__(
            self,
            "suppressed_challenge_ids",
            tuple(
                _require_non_empty(challenge_id, "suppressed_challenge_id")
                for challenge_id in self.suppressed_challenge_ids
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible representation."""

        return {
            "reward_id": self.reward_id,
            "user_id": self.user_id,
            "challenge_id": self.challenge_id,
            "reward_points": self.reward_points,
            "reward_date": self.reward_date.isoformat(),
            "reason": self.reason.value,
            "suppressed_challenge_ids": list(self.suppressed_challenge_ids),
        }


@dataclass(frozen=True, slots=True)
class PointsLedgerEntry:
    """Append-only point transaction."""

    ledger_id: str
    user_id: str
    points_delta: int
    source: RewardReason
    source_ref: str
    created_at: datetime

    def __post_init__(self) -> None:
        """Validate ledger entry fields."""

        object.__setattr__(
            self,
            "ledger_id",
            _require_non_empty(self.ledger_id, "ledger_id"),
        )
        object.__setattr__(self, "user_id", _require_non_empty(self.user_id, "user_id"))
        object.__setattr__(
            self,
            "points_delta",
            _require_positive(self.points_delta, "points_delta"),
        )
        object.__setattr__(
            self,
            "source_ref",
            _require_non_empty(self.source_ref, "source_ref"),
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible representation."""

        return {
            "ledger_id": self.ledger_id,
            "user_id": self.user_id,
            "points_delta": self.points_delta,
            "source": self.source.value,
            "source_ref": self.source_ref,
            "created_at": self.created_at.isoformat(),
        }


@dataclass(frozen=True, slots=True)
class BadgeAssignment:
    """Awarded badge record for a user."""

    user_id: str
    badge_type: BadgeType
    awarded_at: date
    badge_id: str | None = None

    def __post_init__(self) -> None:
        """Validate badge assignment fields."""

        object.__setattr__(self, "user_id", _require_non_empty(self.user_id, "user_id"))
        if self.badge_id is not None:
            object.__setattr__(
                self,
                "badge_id",
                _require_non_empty(self.badge_id, "badge_id"),
            )

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible representation."""

        return {
            "user_id": self.user_id,
            "badge_type": self.badge_type.value,
            "awarded_at": self.awarded_at.isoformat(),
            "badge_id": self.badge_id,
        }


@dataclass(frozen=True, slots=True)
class LeaderboardEntry:
    """Deterministic leaderboard row."""

    rank: int
    user_id: str
    total_points: int
    badges: tuple[BadgeType, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        """Validate leaderboard entry fields."""

        object.__setattr__(self, "rank", _require_positive(self.rank, "rank"))
        object.__setattr__(self, "user_id", _require_non_empty(self.user_id, "user_id"))
        object.__setattr__(
            self,
            "total_points",
            _require_non_negative(self.total_points, "total_points"),
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible representation."""

        return {
            "rank": self.rank,
            "user_id": self.user_id,
            "total_points": self.total_points,
            "badges": [badge.value for badge in self.badges],
        }


@dataclass(frozen=True, slots=True)
class Notification:
    """Notification record produced by the engine."""

    notification_id: str
    user_id: str
    notification_type: NotificationType
    channel: NotificationChannel
    message: str
    created_at: datetime
    source_ref: str

    def __post_init__(self) -> None:
        """Validate notification fields."""

        object.__setattr__(
            self,
            "notification_id",
            _require_non_empty(self.notification_id, "notification_id"),
        )
        object.__setattr__(self, "user_id", _require_non_empty(self.user_id, "user_id"))
        object.__setattr__(self, "message", _require_non_empty(self.message, "message"))
        object.__setattr__(
            self,
            "source_ref",
            _require_non_empty(self.source_ref, "source_ref"),
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible representation."""

        return {
            "notification_id": self.notification_id,
            "user_id": self.user_id,
            "notification_type": self.notification_type.value,
            "channel": self.channel.value,
            "message": self.message,
            "created_at": self.created_at.isoformat(),
            "source_ref": self.source_ref,
        }


@dataclass(frozen=True, slots=True)
class ExplanationResponse:
    """Deterministic answer returned by the explanation layer."""

    user_id: str
    question: str
    answer: str
    evidence: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate explanation response fields."""

        object.__setattr__(self, "user_id", _require_non_empty(self.user_id, "user_id"))
        object.__setattr__(
            self,
            "question",
            _require_non_empty(self.question, "question"),
        )
        object.__setattr__(self, "answer", _require_non_empty(self.answer, "answer"))

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible representation."""

        return {
            "user_id": self.user_id,
            "question": self.question,
            "answer": self.answer,
            "evidence": _serialize(self.evidence),
        }

