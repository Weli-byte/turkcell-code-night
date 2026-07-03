"""Tests for notification JSON repository."""

import json
from datetime import UTC, datetime

import pytest

from gamification_engine.domain.enums import NotificationChannel, NotificationType
from gamification_engine.domain.errors import IngestionError
from gamification_engine.domain.models import Notification
from gamification_engine.notifications.notification_repository import (
    load_notifications_json,
    write_notifications_json,
)


def _notification() -> Notification:
    return Notification(
        notification_id="notification-1",
        user_id="U1",
        notification_type=NotificationType.CHALLENGE_REWARD,
        channel=NotificationChannel.IN_APP,
        message="Challenge C-01 completed. You earned 80 points.",
        created_at=datetime(2026, 3, 14, tzinfo=UTC),
        source_ref="reward-1",
    )


def test_load_notifications_json_returns_empty_for_missing_file(tmp_path) -> None:
    """A missing notification file represents empty history."""

    assert load_notifications_json(tmp_path / "missing.json") == []


def test_write_and_load_notifications_json_round_trips(tmp_path) -> None:
    """Repository should persist and restore notifications."""

    path = tmp_path / "notifications.json"
    notifications = [_notification()]

    write_notifications_json(path, notifications)
    loaded = load_notifications_json(path)

    assert loaded == notifications
    raw_payload = json.loads(path.read_text(encoding="utf-8"))
    assert raw_payload[0]["notification_type"] == "CHALLENGE_REWARD"


def test_load_notifications_json_rejects_non_list_payload(tmp_path) -> None:
    """Notification JSON top-level payload must be a list."""

    path = tmp_path / "notifications.json"
    path.write_text("{}", encoding="utf-8")

    with pytest.raises(IngestionError, match="must contain a list"):
        load_notifications_json(path)


def test_load_notifications_json_rejects_invalid_record(tmp_path) -> None:
    """Invalid notification records should fail ingestion."""

    path = tmp_path / "notifications.json"
    path.write_text(
        '[{"notification_id": "N1", "notification_type": "UNKNOWN"}]',
        encoding="utf-8",
    )

    with pytest.raises(IngestionError, match="Invalid notification"):
        load_notifications_json(path)
