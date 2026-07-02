"""Priority-based reward selection for triggered challenges."""

from __future__ import annotations

import hashlib
from datetime import date

from gamification_engine.domain.enums import RewardReason
from gamification_engine.domain.models import ChallengeDefinition, RewardEvent


def select_reward(
    user_id: str,
    reward_date: date,
    triggered_challenges: list[ChallengeDefinition],
) -> RewardEvent | None:
    """Select one reward from triggered challenges using deterministic priority.

    Lower numeric priority means higher business priority. Ties are resolved by
    ``challenge_id`` ascending.
    """

    if not triggered_challenges:
        return None

    sorted_challenges = sorted(
        triggered_challenges,
        key=lambda challenge: (challenge.priority, challenge.challenge_id),
    )
    selected = sorted_challenges[0]
    suppressed = tuple(
        challenge.challenge_id for challenge in sorted_challenges[1:]
    )

    return RewardEvent(
        reward_id=_build_reward_id(user_id, reward_date, selected.challenge_id),
        user_id=user_id,
        challenge_id=selected.challenge_id,
        reward_points=selected.reward_points,
        reward_date=reward_date,
        reason=RewardReason.CHALLENGE_COMPLETED,
        suppressed_challenge_ids=suppressed,
    )


def _build_reward_id(user_id: str, reward_date: date, challenge_id: str) -> str:
    raw_key = f"{user_id}|{reward_date.isoformat()}|{challenge_id}"
    digest = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()[:16]
    return f"reward-{digest}"

