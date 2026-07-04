"""Bridge the live database to the engine's deterministic explanation layer.

Database rows are mapped into the engine's domain models and handed to
``explain_user_query``; the optional LLM adapter may then rephrase the
answer (never the decision — any LLM failure falls back to the
deterministic text, exactly as in the batch CLI).

Identity note: all domain objects are keyed by ``username`` rather than the
internal user id, so answers and evidence (e.g. "the user one rank above
you") reference names the user actually sees on the leaderboard.
"""

from __future__ import annotations

from dataclasses import replace

from sqlalchemy.orm import Session

from gamification_backend.db.models import ChallengeRecord, UserRecord
from gamification_backend.repositories.badges import badges_for_user
from gamification_backend.repositories.events import today_utc
from gamification_backend.repositories.leaderboard import build_leaderboard
from gamification_backend.repositories.ledger import AppendOnlyLedgerRepository
from gamification_backend.repositories.rewards import rewards_for_user
from gamification_backend.services.live_evaluator import to_challenge_definition
from gamification_backend.services.state_builder import build_daily_state
from gamification_engine.ai.explanation_engine import explain_user_query
from gamification_engine.ai.llm_adapter import create_llm_adapter_from_env
from gamification_engine.domain.enums import BadgeType, RewardReason
from gamification_engine.domain.models import (
    BadgeAssignment,
    ExplanationResponse,
    LeaderboardEntry,
    PointsLedgerEntry,
    RewardEvent,
)


def explain_for_user(
    session: Session, *, user: UserRecord, question: str
) -> ExplanationResponse:
    """Answer a user's question from live data; optionally LLM-rephrased."""

    display_id = user.username

    state = build_daily_state(session, user_id=user.id, target_date=today_utc())
    state = replace(state, user_id=display_id)

    ledger_entries = [
        PointsLedgerEntry(
            ledger_id=entry.ledger_id,
            user_id=display_id,
            points_delta=entry.points_delta,
            source=RewardReason(entry.source),
            source_ref=entry.source_ref,
            created_at=entry.created_at,
        )
        for entry in AppendOnlyLedgerRepository(session).entries_for_user(user.id)
    ]

    badges = [
        BadgeAssignment(
            user_id=display_id,
            badge_type=BadgeType(record.badge_type),
            awarded_at=record.awarded_at,
            badge_id=None,
        )
        for record in badges_for_user(session, user.id)
    ]

    leaderboard = [
        LeaderboardEntry(
            rank=row.rank,
            user_id=row.username,
            total_points=row.total_points,
            badges=tuple(BadgeType(badge) for badge in row.badges),
        )
        for row in build_leaderboard(session)
    ]

    rewards = [
        RewardEvent(
            reward_id=record.reward_id,
            user_id=display_id,
            challenge_id=record.challenge_id,
            reward_points=record.reward_points,
            reward_date=record.reward_date,
            reason=RewardReason.CHALLENGE_COMPLETED,
            suppressed_challenge_ids=tuple(
                item for item in record.suppressed_challenge_ids.split(",") if item
            ),
        )
        for record in rewards_for_user(session, user.id)
    ]

    challenges = [
        to_challenge_definition(record)
        for record in session.query(ChallengeRecord).order_by(
            ChallengeRecord.challenge_id
        )
    ]

    response = explain_user_query(
        question=question,
        user_id=display_id,
        state=state,
        ledger_entries=ledger_entries,
        badges=badges,
        leaderboard=leaderboard,
        challenges=challenges,
        rewards=rewards,
    )
    # Optional linguistic polish only; failures fall back deterministically.
    return create_llm_adapter_from_env().enhance(response)
