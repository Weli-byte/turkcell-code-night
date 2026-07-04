"""Badge persistence with duplicate protection."""

from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from gamification_backend.db.models import BadgeRecord


def badges_for_user(session: Session, user_id: str) -> list[BadgeRecord]:
    """The user's badges in award order."""

    stmt = (
        select(BadgeRecord)
        .where(BadgeRecord.user_id == user_id)
        .order_by(BadgeRecord.id)
    )
    return list(session.execute(stmt).scalars())


def add_badge(
    session: Session, *, user_id: str, badge_type: str, awarded_at: date
) -> BadgeRecord | None:
    """Award a badge once; returns None when the tier is already owned."""

    exists_stmt = select(BadgeRecord.id).where(
        BadgeRecord.user_id == user_id, BadgeRecord.badge_type == badge_type
    )
    if session.execute(exists_stmt).first() is not None:
        return None
    record = BadgeRecord(user_id=user_id, badge_type=badge_type, awarded_at=awarded_at)
    session.add(record)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        return None
    return record
