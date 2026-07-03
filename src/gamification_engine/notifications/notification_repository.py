"""JSON persistence helpers for notification records."""

from __future__ import annotations

import json
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from typing import Any

from gamification_engine.domain.enums import NotificationChannel, NotificationType
from gamification_engine.domain.errors import IngestionError
from gamification_engine.domain.models import Notification
from gamification_engine.notifications.notification_engine import sort_notifications


def load_notifications_json(path: str | Path) -> list[Notification]:
    """Load notifications from JSON.

    Missing files are treated as empty notification history.
    """

    notification_path = Path(path)
    if not notification_path.exists():
        return []
    if not notification_path.is_file():
        raise IngestionError(f"Notification path is not a file: {notification_path}.")

    try:
        raw_data = json.loads(notification_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise IngestionError(
            f"Could not read notification JSON: {notification_path}."
        ) from exc

    if not isinstance(raw_data, list):
        raise IngestionError("Notification JSON must contain a list of records.")

    notifications = [
        _parse_notification(item, index + 1) for index, item in enumerate(raw_data)
    ]
    return sort_notifications(notifications)


def write_notifications_json(
    path: str | Path,
    notifications: Iterable[Notification],
) -> None:
    """Write notifications as deterministic JSON."""

    notification_path = Path(path)
    notification_path.parent.mkdir(parents=True, exist_ok=True)
    payload = [
        notification.to_dict() for notification in sort_notifications(notifications)
    ]
    notification_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _parse_notification(raw_entry: Any, row_number: int) -> Notification:
    if not isinstance(raw_entry, dict):
        raise IngestionError(f"Notification {row_number} must be an object.")

    try:
        return Notification(
            notification_id=_required_text(raw_entry, "notification_id"),
            user_id=_required_text(raw_entry, "user_id"),
            notification_type=NotificationType(
                _required_text(raw_entry, "notification_type")
            ),
            channel=NotificationChannel(_required_text(raw_entry, "channel")),
            message=_required_text(raw_entry, "message"),
            created_at=datetime.fromisoformat(_required_text(raw_entry, "created_at")),
            source_ref=_required_text(raw_entry, "source_ref"),
        )
    except (ValueError, TypeError) as exc:
        raise IngestionError(f"Invalid notification {row_number}: {exc}") from exc


def _required_text(raw_entry: dict[str, Any], field_name: str) -> str:
    value = raw_entry.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string.")
    return value.strip()
