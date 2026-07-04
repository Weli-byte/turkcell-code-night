"""Notification persistence with deterministic ids for deduplication."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from gamification_backend.db.models import NotificationRecord


def add_notification(
    session: Session,
    *,
    notification_id: str,
    user_id: str,
    notification_type: str,
    message: str,
    source_ref: str,
    channel: str = "IN_APP",
) -> NotificationRecord | None:
    """Store a notification once; returns None when the id already exists."""

    exists_stmt = select(NotificationRecord.id).where(
        NotificationRecord.notification_id == notification_id
    )
    if session.execute(exists_stmt).first() is not None:
        return None
    record = NotificationRecord(
        notification_id=notification_id,
        user_id=user_id,
        notification_type=notification_type,
        channel=channel,
        message=message,
        source_ref=source_ref,
    )
    session.add(record)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        return None
    return record


def notifications_for_user(session: Session, user_id: str) -> list[NotificationRecord]:
    """The user's notifications, newest first."""

    stmt = (
        select(NotificationRecord)
        .where(NotificationRecord.user_id == user_id)
        .order_by(NotificationRecord.id.desc())
    )
    return list(session.execute(stmt).scalars())
