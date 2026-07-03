"""Repository helpers for in-memory challenge definitions."""

from __future__ import annotations

from collections.abc import Iterable

from gamification_engine.domain.errors import RuleEvaluationError
from gamification_engine.domain.models import ChallengeDefinition


class ChallengeRepository:
    """Read-only in-memory challenge repository."""

    def __init__(self, challenges: Iterable[ChallengeDefinition]) -> None:
        """Initialize the repository with deterministic ordering."""

        self._challenges = tuple(
            sorted(challenges, key=lambda challenge: challenge.challenge_id)
        )
        self._validate_unique_ids()

    def list_all(self) -> list[ChallengeDefinition]:
        """Return all challenges sorted by challenge ID."""

        return list(self._challenges)

    def list_active(self) -> list[ChallengeDefinition]:
        """Return active challenges sorted by challenge ID."""

        return [challenge for challenge in self._challenges if challenge.is_active]

    def _validate_unique_ids(self) -> None:
        seen: set[str] = set()
        duplicates: set[str] = set()
        for challenge in self._challenges:
            if challenge.challenge_id in seen:
                duplicates.add(challenge.challenge_id)
            seen.add(challenge.challenge_id)

        if duplicates:
            joined = ", ".join(sorted(duplicates))
            raise RuleEvaluationError(f"Duplicate challenge IDs found: {joined}.")
