"""Tests for challenge evaluation."""

from datetime import date

import pytest

from gamification_engine.domain.enums import ChallengeType
from gamification_engine.domain.errors import RuleEvaluationError
from gamification_engine.domain.models import ChallengeDefinition, DailyUserState
from gamification_engine.rules.evaluator import (
    evaluate_challenge,
    evaluate_challenges_for_state,
)


def _state() -> DailyUserState:
    return DailyUserState(
        user_id="U1",
        state_date=date(2026, 3, 14),
        watch_minutes_today=70,
        watch_minutes_7d=400,
        episodes_completed_today=2,
        episodes_completed_7d=8,
        unique_genres_today=3,
        watch_party_minutes_today=10,
        ratings_today=1,
        ratings_7d=4,
        watch_streak_days=3,
    )


def _challenge(
    challenge_id: str,
    condition: str,
    priority: int = 1,
    is_active: bool = True,
) -> ChallengeDefinition:
    return ChallengeDefinition(
        challenge_id=challenge_id,
        name=challenge_id,
        challenge_type=ChallengeType.DAILY,
        condition=condition,
        reward_points=100,
        priority=priority,
        is_active=is_active,
    )


def test_evaluate_challenge_returns_true_for_matching_state() -> None:
    """A valid matching condition should trigger."""

    assert evaluate_challenge(
        _state(),
        _challenge("C-01", "watch_minutes_today >= 60"),
    )


def test_evaluate_challenge_returns_false_for_inactive_challenge() -> None:
    """Inactive challenges should not trigger."""

    assert not evaluate_challenge(
        _state(),
        _challenge("C-01", "watch_minutes_today >= 60", is_active=False),
    )


@pytest.mark.parametrize(
    ("condition", "expected"),
    [
        ("watch_minutes_today > 70", False),
        ("watch_minutes_today <= 70", True),
        ("ratings_7d == 4", True),
        ("ratings_7d != 4", False),
    ],
)
def test_evaluate_challenge_supports_all_comparison_operators(
    condition: str,
    expected: bool,
) -> None:
    """All MVP comparison operators should evaluate correctly."""

    assert evaluate_challenge(_state(), _challenge("C-01", condition)) is expected


def test_evaluate_challenges_for_state_returns_priority_sorted_triggers() -> None:
    """Triggered challenges should be sorted by priority and challenge ID."""

    triggered = evaluate_challenges_for_state(
        _state(),
        [
            _challenge("C-03", "watch_minutes_today >= 60", priority=3),
            _challenge("C-01", "ratings_7d >= 4", priority=1),
            _challenge("C-02", "watch_streak_days >= 99", priority=2),
        ],
    )

    assert [challenge.challenge_id for challenge in triggered] == ["C-01", "C-03"]


def test_evaluate_challenge_raises_for_invalid_condition() -> None:
    """Invalid rule syntax should fail explicitly."""

    with pytest.raises(RuleEvaluationError):
        evaluate_challenge(_state(), _challenge("C-01", "watch_minutes_today + 1"))
