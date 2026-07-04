"""Live challenge evaluation: runs after every accepted activity event.

Pipeline (all business decisions made by the deterministic engine):

1. Aggregate DB events into ``DailyUserState`` (state_builder).
2. Engine ``evaluate_challenges_for_state`` finds triggered challenges.
3. Engine ``select_reward`` picks one by priority (tie-break challenge_id).
4. Persist the reward — ``UNIQUE(user_id, reward_date)`` guarantees the
   "one reward per user per day" rule even under concurrent requests.
5. Append points to the insert-only ledger (idempotent via source_ref).
6. Check badge thresholds on the new total; award missing tiers.
7. Record deduplicated notifications for anything newly granted.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime

from sqlalchemy.orm import Session

from gamification_backend.db.models import (
    BadgeRecord,
    ChallengeRecord,
    NotificationRecord,
    RewardEventRecord,
)
from gamification_backend.repositories.badges import add_badge
from gamification_backend.repositories.challenges import list_active_challenges
from gamification_backend.repositories.ledger import AppendOnlyLedgerRepository
from gamification_backend.repositories.notifications import add_notification
from gamification_backend.repositories.rewards import (
    get_reward_for_date,
    insert_reward,
)
from gamification_backend.services.state_builder import build_daily_state
from gamification_engine.config.badge_config import BADGE_THRESHOLDS
from gamification_engine.domain.enums import ChallengeType
from gamification_engine.domain.models import ChallengeDefinition
from gamification_engine.rules.evaluator import evaluate_challenges_for_state
from gamification_engine.rules.reward_selector import select_reward


@dataclass(frozen=True)
class LiveEvaluationResult:
    """Everything newly granted by one evaluation pass."""

    reward: RewardEventRecord | None = None
    new_badges: list[BadgeRecord] = field(default_factory=list)
    notifications: list[NotificationRecord] = field(default_factory=list)


def to_challenge_definition(record: ChallengeRecord) -> ChallengeDefinition:
    """Map a database challenge row to the engine's domain model."""

    return ChallengeDefinition(
        challenge_id=record.challenge_id,
        name=record.name,
        challenge_type=ChallengeType(record.challenge_type),
        condition=record.condition,
        reward_points=record.reward_points,
        priority=record.priority,
        is_active=record.is_active,
    )


def evaluate_user_live(
    session: Session, *, user_id: str, event_date: date
) -> LiveEvaluationResult:
    """Evaluate challenges for the user's current daily state."""

    state = build_daily_state(session, user_id=user_id, target_date=event_date)
    definitions = [
        to_challenge_definition(record) for record in list_active_challenges(session)
    ]
    triggered = evaluate_challenges_for_state(state, definitions)

    notifications: list[NotificationRecord] = []
    reward_record: RewardEventRecord | None = None

    reward = (
        select_reward(user_id, event_date, triggered)
        if triggered and get_reward_for_date(session, user_id, event_date) is None
        else None
    )
    if reward is not None:
        reward_record = insert_reward(session, reward)
        if reward_record is not None:
            AppendOnlyLedgerRepository(session).append(
                ledger_id=reward.reward_id,
                user_id=user_id,
                points_delta=reward.reward_points,
                source=reward.reason.value,
                source_ref=f"reward:{event_date.isoformat()}",
                created_at=datetime.now(UTC),
            )
            challenge = session.get(ChallengeRecord, reward.challenge_id)
            challenge_name = challenge.name if challenge else reward.challenge_id
            note = add_notification(
                session,
                notification_id=f"{user_id}:reward:{event_date.isoformat()}",
                user_id=user_id,
                notification_type="CHALLENGE_REWARD",
                message=(
                    f"🎉 '{challenge_name}' tamamlandı: +{reward.reward_points} puan!"
                ),
                source_ref=reward.reward_id,
            )
            if note is not None:
                notifications.append(note)

    new_badges = _award_missing_badges(
        session, user_id=user_id, event_date=event_date, notes=notifications
    )
    return LiveEvaluationResult(
        reward=reward_record, new_badges=new_badges, notifications=notifications
    )


def _award_missing_badges(
    session: Session,
    *,
    user_id: str,
    event_date: date,
    notes: list[NotificationRecord],
) -> list[BadgeRecord]:
    total = AppendOnlyLedgerRepository(session).total_points(user_id)
    new_badges: list[BadgeRecord] = []
    for threshold in BADGE_THRESHOLDS:
        if total < threshold.required_points:
            continue
        badge = add_badge(
            session,
            user_id=user_id,
            badge_type=threshold.badge_type.value,
            awarded_at=event_date,
        )
        if badge is None:
            continue
        new_badges.append(badge)
        note = add_notification(
            session,
            notification_id=f"{user_id}:badge:{badge.badge_type}",
            user_id=user_id,
            notification_type="BADGE_EARNED",
            message=f"🏆 {badge.badge_type} rozetini kazandın!",
            source_ref=f"badge:{badge.badge_type}",
        )
        if note is not None:
            notes.append(note)
    return new_badges
