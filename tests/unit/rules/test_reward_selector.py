"""Tests for reward selection."""

from datetime import date

from gamification_engine.domain.enums import ChallengeType
from gamification_engine.domain.models import ChallengeDefinition
from gamification_engine.rules.reward_selector import select_reward


def _challenge(
    challenge_id: str,
    priority: int,
    reward_points: int = 100,
) -> ChallengeDefinition:
    return ChallengeDefinition(
        challenge_id=challenge_id,
        name=challenge_id,
        challenge_type=ChallengeType.DAILY,
        condition="watch_minutes_today >= 60",
        reward_points=reward_points,
        priority=priority,
        is_active=True,
    )


def test_select_reward_returns_none_without_triggers() -> None:
    """No triggered challenge means no reward."""

    assert select_reward("U1", date(2026, 3, 14), []) is None


def test_select_reward_uses_lowest_priority_number() -> None:
    """Lower numeric priority should win."""

    reward = select_reward(
        "U1",
        date(2026, 3, 14),
        [
            _challenge("C-01", priority=5, reward_points=80),
            _challenge("C-02", priority=1, reward_points=200),
            _challenge("C-03", priority=3, reward_points=120),
        ],
    )

    assert reward is not None
    assert reward.challenge_id == "C-02"
    assert reward.reward_points == 200
    assert reward.suppressed_challenge_ids == ("C-03", "C-01")


def test_select_reward_ties_by_challenge_id_and_uses_deterministic_id() -> None:
    """Equal priorities should resolve by challenge ID and stable reward ID."""

    reward_1 = select_reward(
        "U1",
        date(2026, 3, 14),
        [_challenge("C-02", priority=1), _challenge("C-01", priority=1)],
    )
    reward_2 = select_reward(
        "U1",
        date(2026, 3, 14),
        [_challenge("C-01", priority=1), _challenge("C-02", priority=1)],
    )

    assert reward_1 is not None
    assert reward_2 is not None
    assert reward_1.challenge_id == "C-01"
    assert reward_1.reward_id == reward_2.reward_id
    assert reward_1.reward_id.startswith("reward-")

