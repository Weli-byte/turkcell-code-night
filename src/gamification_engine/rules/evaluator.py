"""Evaluate challenge definitions against typed user state."""

from __future__ import annotations

from gamification_engine.domain.errors import RuleEvaluationError
from gamification_engine.domain.models import ChallengeDefinition, DailyUserState
from gamification_engine.rules.condition_parser import (
    ComparisonOperator,
    ParsedCondition,
    parse_condition,
)


def evaluate_condition(
    parsed_condition: ParsedCondition,
    rule_context: dict[str, int],
) -> bool:
    """Evaluate a parsed condition against a state rule context."""

    left_value = rule_context[parsed_condition.field_name]
    right_value = parsed_condition.literal_value

    match parsed_condition.operator:
        case ComparisonOperator.GREATER_THAN_OR_EQUAL:
            return left_value >= right_value
        case ComparisonOperator.GREATER_THAN:
            return left_value > right_value
        case ComparisonOperator.LESS_THAN_OR_EQUAL:
            return left_value <= right_value
        case ComparisonOperator.LESS_THAN:
            return left_value < right_value
        case ComparisonOperator.EQUAL:
            return left_value == right_value
        case ComparisonOperator.NOT_EQUAL:
            return left_value != right_value


def evaluate_challenge(
    state: DailyUserState,
    challenge: ChallengeDefinition,
) -> bool:
    """Evaluate one active challenge against a user's state.

    Inactive challenges always return ``False``.
    """

    if not challenge.is_active:
        return False

    rule_context = state.to_rule_context()
    parsed_condition = parse_condition(
        challenge.condition,
        allowed_fields=set(rule_context),
    )
    return evaluate_condition(parsed_condition, rule_context)


def evaluate_challenges_for_state(
    state: DailyUserState,
    challenges: list[ChallengeDefinition],
) -> list[ChallengeDefinition]:
    """Return active challenges triggered for one user state.

    The returned list is sorted deterministically by priority ascending and then
    challenge ID ascending.
    """

    triggered: list[ChallengeDefinition] = []
    for challenge in challenges:
        try:
            if evaluate_challenge(state, challenge):
                triggered.append(challenge)
        except RuleEvaluationError:
            raise

    return sorted(triggered, key=lambda item: (item.priority, item.challenge_id))

