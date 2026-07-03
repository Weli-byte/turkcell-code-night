"""Tests for challenge repository helpers."""

from gamification_engine.domain.enums import ChallengeType
from gamification_engine.domain.models import ChallengeDefinition
from gamification_engine.rules.challenge_repository import ChallengeRepository


def _challenge(challenge_id: str, is_active: bool) -> ChallengeDefinition:
    return ChallengeDefinition(
        challenge_id=challenge_id,
        name=challenge_id,
        challenge_type=ChallengeType.DAILY,
        condition="watch_minutes_today >= 60",
        reward_points=100,
        priority=1,
        is_active=is_active,
    )


def test_repository_returns_challenges_in_deterministic_order() -> None:
    """Challenge repository should normalize ordering by challenge ID."""

    repository = ChallengeRepository(
        [_challenge("C-02", True), _challenge("C-01", False)]
    )

    assert [challenge.challenge_id for challenge in repository.list_all()] == [
        "C-01",
        "C-02",
    ]
    assert [challenge.challenge_id for challenge in repository.list_active()] == [
        "C-02"
    ]
