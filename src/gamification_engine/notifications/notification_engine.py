"""Create deterministic notification records from gamification events."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from datetime import UTC, date, datetime, time

from gamification_engine.domain.enums import (
    BadgeType,
    NotificationChannel,
    NotificationType,
)
from gamification_engine.domain.models import (
    BadgeAssignment,
    Notification,
    RewardEvent,
)


def create_notifications(
    reward_events: Iterable[RewardEvent],
    new_badges: Iterable[BadgeAssignment],
    existing_notifications: Iterable[Notification] = (),
    channel: NotificationChannel = NotificationChannel.IN_APP,
) -> list[Notification]:
    """Create missing notification records for rewards and badge awards.

    Existing notification records are preserved. Duplicate prevention uses the
    pair ``(notification_type, source_ref)`` so the same event is not announced
    twice across repeated runs.
    """

    existing = sort_notifications(existing_notifications)
    existing_keys = {
        (notification.notification_type, notification.source_ref)
        for notification in existing
    }
    batch_keys: set[tuple[NotificationType, str]] = set()

    new_notifications: list[Notification] = []

    for reward_event in sorted(
        reward_events,
        key=lambda reward: (
            reward.reward_date,
            reward.user_id,
            reward.challenge_id,
            reward.reward_id,
        ),
    ):
        key = (NotificationType.CHALLENGE_REWARD, reward_event.reward_id)
        if key in existing_keys or key in batch_keys:
            continue
        batch_keys.add(key)
        new_notifications.append(_create_reward_notification(reward_event, channel))

    for badge in sorted(
        new_badges,
        key=lambda item: (
            item.awarded_at,
            item.user_id,
            _badge_order(item.badge_type),
            item.badge_id or "",
        ),
    ):
        source_ref = _badge_source_ref(badge)
        key = (NotificationType.BADGE_EARNED, source_ref)
        if key in existing_keys or key in batch_keys:
            continue
        batch_keys.add(key)
        new_notifications.append(_create_badge_notification(badge, channel))

    return sort_notifications([*existing, *new_notifications])


def sort_notifications(
    notifications: Iterable[Notification],
) -> list[Notification]:
    """Return notifications in deterministic output order."""

    return sorted(
        notifications,
        key=lambda notification: (
            notification.created_at,
            notification.user_id,
            notification.notification_type.value,
            notification.source_ref,
            notification.notification_id,
        ),
    )


def _create_reward_notification(
    reward_event: RewardEvent,
    channel: NotificationChannel,
) -> Notification:
    source_ref = reward_event.reward_id
    return Notification(
        notification_id=_build_notification_id(
            reward_event.user_id,
            NotificationType.CHALLENGE_REWARD,
            source_ref,
        ),
        user_id=reward_event.user_id,
        notification_type=NotificationType.CHALLENGE_REWARD,
        channel=channel,
        message=(
            f"Challenge {reward_event.challenge_id} completed. "
            f"You earned {reward_event.reward_points} points."
        ),
        created_at=_start_of_day_utc(reward_event.reward_date),
        source_ref=source_ref,
    )


def _create_badge_notification(
    badge: BadgeAssignment,
    channel: NotificationChannel,
) -> Notification:
    source_ref = _badge_source_ref(badge)
    return Notification(
        notification_id=_build_notification_id(
            badge.user_id,
            NotificationType.BADGE_EARNED,
            source_ref,
        ),
        user_id=badge.user_id,
        notification_type=NotificationType.BADGE_EARNED,
        channel=channel,
        message=f"{badge.badge_type.value.title()} badge earned.",
        created_at=_start_of_day_utc(badge.awarded_at),
        source_ref=source_ref,
    )


def _build_notification_id(
    user_id: str,
    notification_type: NotificationType,
    source_ref: str,
) -> str:
    raw_key = f"{user_id}|{notification_type.value}|{source_ref}"
    digest = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()[:16]
    return f"notification-{digest}"


def _start_of_day_utc(value: date) -> datetime:
    return datetime.combine(value, time.min, tzinfo=UTC)


def _badge_source_ref(badge: BadgeAssignment) -> str:
    if badge.badge_id is not None:
        return badge.badge_id
    return f"{badge.user_id}|{badge.badge_type.value}"


def _badge_order(badge_type: BadgeType) -> int:
    return [BadgeType.BRONZE, BadgeType.SILVER, BadgeType.GOLD].index(badge_type)
