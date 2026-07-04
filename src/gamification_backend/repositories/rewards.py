"""Reward event persistence (one reward per user per day)."""

from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from gamification_backend.db.models import RewardEventRecord
from gamification_engine.domain.models import RewardEvent


def get_reward_for_date(
    session: Session, user_id: str, reward_date: date
) -> RewardEventRecord | None:
    """The user's reward for the given day, if already granted."""

    stmt = select(RewardEventRecord).where(
        RewardEventRecord.user_id == user_id,
        RewardEventRecord.reward_date == reward_date,
    )
    return session.execute(stmt).scalar_one_or_none()


def insert_reward(session: Session, reward: RewardEvent) -> RewardEventRecord | None:
    """Persist an engine-selected reward.

    Returns None when the user already has a reward for that day (unique
    constraint), which makes concurrent live evaluations idempotent.
    """

    record = RewardEventRecord(
        reward_id=reward.reward_id,
        user_id=reward.user_id,
        challenge_id=reward.challenge_id,
        reward_points=reward.reward_points,
        reward_date=reward.reward_date,
        suppressed_challenge_ids=",".join(reward.suppressed_challenge_ids),
    )
    session.add(record)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        return None
    return record


def rewards_for_user(session: Session, user_id: str) -> list[RewardEventRecord]:
    """All rewards of the user, oldest first."""

    stmt = (
        select(RewardEventRecord)
        .where(RewardEventRecord.user_id == user_id)
        .order_by(RewardEventRecord.id)
    )
    return list(session.execute(stmt).scalars())
