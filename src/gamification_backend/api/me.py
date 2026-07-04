"""Endpoints about the authenticated user."""

from __future__ import annotations

from fastapi import APIRouter

from gamification_backend.api.deps import CurrentUserDep, SessionDep
from gamification_backend.api.schemas import (
    BadgeResponse,
    ChallengeProgressResponse,
    LedgerEntryResponse,
    NotificationResponse,
    PointsResponse,
    UserResponse,
)
from gamification_backend.repositories.badges import badges_for_user
from gamification_backend.repositories.challenges import list_active_challenges
from gamification_backend.repositories.events import today_utc
from gamification_backend.repositories.ledger import AppendOnlyLedgerRepository
from gamification_backend.repositories.notifications import notifications_for_user
from gamification_backend.repositories.rewards import get_reward_for_date
from gamification_backend.services.state_builder import build_daily_state
from gamification_engine.rules.condition_parser import (
    ComparisonOperator,
    parse_condition,
)
from gamification_engine.rules.evaluator import evaluate_condition

router = APIRouter(prefix="/me", tags=["me"])

_UPWARD_OPERATORS = (
    ComparisonOperator.GREATER_THAN_OR_EQUAL,
    ComparisonOperator.GREATER_THAN,
)


@router.get("")
def read_me(user: CurrentUserDep) -> UserResponse:
    """Return the authenticated user's profile."""

    return UserResponse.model_validate(user)


@router.get("/points")
def read_points(user: CurrentUserDep, session: SessionDep) -> PointsResponse:
    """Point total plus the full append-only transaction history."""

    repo = AppendOnlyLedgerRepository(session)
    return PointsResponse(
        total_points=repo.total_points(user.id),
        entries=[
            LedgerEntryResponse.model_validate(entry)
            for entry in repo.entries_for_user(user.id)
        ],
    )


@router.get("/badges")
def read_badges(user: CurrentUserDep, session: SessionDep) -> list[BadgeResponse]:
    """Badges owned by the user."""

    return [
        BadgeResponse.model_validate(badge)
        for badge in badges_for_user(session, user.id)
    ]


@router.get("/challenges")
def read_challenges(
    user: CurrentUserDep, session: SessionDep
) -> list[ChallengeProgressResponse]:
    """Active challenges with live progress computed from today's state."""

    today = today_utc()
    state = build_daily_state(session, user_id=user.id, target_date=today)
    context = state.to_rule_context()
    reward = get_reward_for_date(session, user.id, today)

    progress: list[ChallengeProgressResponse] = []
    for record in list_active_challenges(session):
        parsed = parse_condition(record.condition, allowed_fields=set(context))
        current = context[parsed.field_name]
        target = parsed.literal_value
        satisfied = evaluate_condition(parsed, context)
        if parsed.operator in _UPWARD_OPERATORS and target > 0:
            percent = min(100, (current * 100) // target)
        else:
            percent = 100 if satisfied else 0
        progress.append(
            ChallengeProgressResponse(
                challenge_id=record.challenge_id,
                name=record.name,
                condition=record.condition,
                reward_points=record.reward_points,
                priority=record.priority,
                progress_current=current,
                progress_target=target,
                progress_percent=percent,
                satisfied=satisfied,
                won_today=(
                    reward is not None and reward.challenge_id == record.challenge_id
                ),
            )
        )
    return progress


@router.get("/notifications")
def read_notifications(
    user: CurrentUserDep, session: SessionDep
) -> list[NotificationResponse]:
    """The user's notifications, newest first."""

    return [
        NotificationResponse.model_validate(record)
        for record in notifications_for_user(session, user.id)
    ]
