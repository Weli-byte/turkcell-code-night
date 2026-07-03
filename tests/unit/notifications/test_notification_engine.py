"""Tests for deterministic notification generation."""

from datetime import UTC, date, datetime

from gamification_engine.domain.enums import (
    BadgeType,
    NotificationChannel,
    NotificationType,
    RewardReason,
)
from gamification_engine.domain.models import (
    BadgeAssignment,
    Notification,
    RewardEvent,
)
from gamification_engine.notifications.notification_engine import create_notifications


def _reward(reward_id: str, user_id: str = "U1") -> RewardEvent:
    return RewardEvent(
        reward_id=reward_id,
        user_id=user_id,
        challenge_id="C-01",
        reward_points=80,
        reward_date=date(2026, 3, 14),
        reason=RewardReason.CHALLENGE_COMPLETED,
    )


def _badge(badge_id: str, user_id: str = "U1") -> BadgeAssignment:
    return BadgeAssignment(
        user_id=user_id,
        badge_type=BadgeType.BRONZE,
        awarded_at=date(2026, 3, 14),
        badge_id=badge_id,
    )


def test_create_notifications_creates_reward_and_badge_notifications() -> None:
    """Reward and badge events should both produce notification records."""

    notifications = create_notifications(
        [_reward("reward-1")],
        [_badge("badge-1")],
    )

    assert [item.notification_type for item in notifications] == [
        NotificationType.BADGE_EARNED,
        NotificationType.CHALLENGE_REWARD,
    ]
    assert {item.source_ref for item in notifications} == {"reward-1", "badge-1"}
    assert all(item.channel is NotificationChannel.IN_APP for item in notifications)
    assert all(
        item.created_at.isoformat() == "2026-03-14T00:00:00+00:00"
        for item in notifications
    )


def test_create_notifications_preserves_existing_and_skips_duplicates() -> None:
    """Existing notifications should prevent duplicate event notifications."""

    existing = Notification(
        notification_id="notification-existing",
        user_id="U1",
        notification_type=NotificationType.CHALLENGE_REWARD,
        channel=NotificationChannel.IN_APP,
        message="Already sent.",
        created_at=datetime(2026, 3, 14, tzinfo=UTC),
        source_ref="reward-1",
    )

    notifications = create_notifications(
        [_reward("reward-1"), _reward("reward-2")],
        [],
        existing_notifications=[existing],
    )

    assert [item.source_ref for item in notifications] == ["reward-1", "reward-2"]
    assert notifications[0] == existing


def test_create_notifications_deduplicates_same_batch_events() -> None:
    """Duplicate source events in one batch should create one notification."""

    notifications = create_notifications(
        [_reward("reward-1"), _reward("reward-1")],
        [_badge("badge-1"), _badge("badge-1")],
    )

    assert [item.source_ref for item in notifications] == ["badge-1", "reward-1"]


def test_create_notifications_has_deterministic_ids() -> None:
    """Same event should produce the same notification ID across runs."""

    first = create_notifications([_reward("reward-1")], [_badge("badge-1")])
    second = create_notifications([_reward("reward-1")], [_badge("badge-1")])

    assert [item.notification_id for item in first] == [
        item.notification_id for item in second
    ]
    assert all(item.notification_id.startswith("notification-") for item in first)


def test_create_notifications_supports_channel_override() -> None:
    """Callers can choose an output channel."""

    [notification] = create_notifications(
        [_reward("reward-1")],
        [],
        channel=NotificationChannel.BIP,
    )

    assert notification.channel is NotificationChannel.BIP
