"""Tests for Sprint 2 domain models."""

from datetime import UTC, date, datetime

import pytest

from gamification_engine.domain.enums import (
    BadgeType,
    ChallengeStatus,
    ChallengeType,
    NotificationChannel,
    NotificationType,
    RewardReason,
)
from gamification_engine.domain.errors import DomainError
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


def test_user_activity_serializes_to_json_compatible_dict() -> None:
    """Raw activity should preserve current CSV semantics in typed form."""

    activity = UserActivity(
        event_id="AE-1",
        user_id="U1",
        activity_date=date(2026, 3, 8),
        shows_watched=("S2", "S3"),
        unique_genres=2,
        watch_minutes=142,
        episodes_completed=2,
        watch_party_minutes=60,
        ratings_given=2,
    )

    assert activity.to_dict() == {
        "event_id": "AE-1",
        "user_id": "U1",
        "activity_date": "2026-03-08",
        "watch_minutes": 142,
        "episodes_completed": 2,
        "unique_genres": 2,
        "watch_party_minutes": 60,
        "ratings_given": 2,
        "shows_watched": ["S2", "S3"],
    }


def test_user_activity_rejects_negative_metrics() -> None:
    """Activity metrics cannot be negative."""

    with pytest.raises(DomainError, match="watch_minutes"):
        UserActivity(
            user_id="U1",
            activity_date=date(2026, 3, 8),
            watch_minutes=-1,
            episodes_completed=0,
            unique_genres=0,
            watch_party_minutes=0,
            ratings_given=0,
        )


def test_challenge_definition_validates_reward_and_priority() -> None:
    """Challenges require positive reward points and priority."""

    challenge = ChallengeDefinition(
        challenge_id="C-01",
        name="Daily Watcher",
        challenge_type=ChallengeType.DAILY,
        condition="watch_minutes_today >= 60",
        reward_points=80,
        priority=5,
        is_active=True,
    )

    assert challenge.to_dict()["challenge_type"] == "DAILY"

    with pytest.raises(DomainError, match="reward_points"):
        ChallengeDefinition(
            challenge_id="C-02",
            name="Invalid",
            challenge_type=ChallengeType.DAILY,
            condition="watch_minutes_today >= 60",
            reward_points=0,
            priority=1,
            is_active=True,
        )


def test_daily_user_state_exposes_rule_context() -> None:
    """Rule context should contain only state metrics available to rules."""

    state = DailyUserState(
        user_id="U1",
        state_date=date(2026, 3, 14),
        watch_minutes_today=70,
        watch_minutes_7d=450,
        episodes_completed_today=2,
        episodes_completed_7d=9,
        unique_genres_today=3,
        watch_party_minutes_today=45,
        ratings_today=1,
        ratings_7d=4,
        watch_streak_days=3,
    )

    assert state.to_rule_context() == {
        "watch_minutes_today": 70,
        "watch_minutes_7d": 450,
        "episodes_completed_today": 2,
        "episodes_completed_7d": 9,
        "unique_genres_today": 3,
        "watch_party_minutes_today": 45,
        "ratings_today": 1,
        "ratings_7d": 4,
        "watch_streak_days": 3,
    }


def test_reward_and_ledger_models_serialize_enums_and_dates() -> None:
    """Reward and ledger outputs should be JSON-compatible."""

    reward = RewardEvent(
        reward_id="R-U1-20260314-C01",
        user_id="U1",
        challenge_id="C-01",
        reward_points=80,
        reward_date=date(2026, 3, 14),
        reason=RewardReason.CHALLENGE_COMPLETED,
        suppressed_challenge_ids=("C-02",),
    )
    ledger = PointsLedgerEntry(
        ledger_id="L-U1-20260314-C01",
        user_id="U1",
        points_delta=80,
        source=RewardReason.CHALLENGE_COMPLETED,
        source_ref=reward.reward_id,
        created_at=datetime(2026, 3, 14, tzinfo=UTC),
    )

    assert reward.to_dict()["reason"] == "CHALLENGE_COMPLETED"
    assert reward.to_dict()["suppressed_challenge_ids"] == ["C-02"]
    assert ledger.to_dict()["created_at"] == "2026-03-14T00:00:00+00:00"


def test_output_models_serialize_consistently() -> None:
    """Badge, leaderboard, notification, decision, and explanation contracts."""

    badge = BadgeAssignment(
        user_id="U1",
        badge_type=BadgeType.BRONZE,
        awarded_at=date(2026, 3, 14),
        badge_id="B-U1-BRONZE",
    )
    leaderboard_entry = LeaderboardEntry(
        rank=1,
        user_id="U1",
        total_points=500,
        badges=(BadgeType.BRONZE,),
    )
    notification = Notification(
        notification_id="N-U1-1",
        user_id="U1",
        notification_type=NotificationType.BADGE_EARNED,
        channel=NotificationChannel.IN_APP,
        message="Bronze badge earned.",
        created_at=datetime(2026, 3, 14, tzinfo=UTC),
        source_ref="B-U1-BRONZE",
    )
    decision = ChallengeDecision(
        user_id="U1",
        challenge_id="C-01",
        status=ChallengeStatus.SELECTED,
        evaluated_at=date(2026, 3, 14),
        reason="Highest priority triggered challenge.",
    )
    explanation = ExplanationResponse(
        user_id="U1",
        question="Why am I first?",
        answer="You have the highest point total.",
        evidence={"state_date": date(2026, 3, 14), "badges": [BadgeType.BRONZE]},
    )

    assert badge.to_dict()["badge_type"] == "BRONZE"
    assert leaderboard_entry.to_dict()["badges"] == ["BRONZE"]
    assert notification.to_dict()["notification_type"] == "BADGE_EARNED"
    assert decision.to_dict()["status"] == "SELECTED"
    assert explanation.to_dict()["evidence"] == {
        "state_date": "2026-03-14",
        "badges": ["BRONZE"],
    }


def test_empty_identifiers_are_rejected() -> None:
    """Identifiers are required for deterministic references."""

    with pytest.raises(DomainError, match="user_id"):
        LeaderboardEntry(rank=1, user_id=" ", total_points=0)
