"""Tests for safe condition parsing."""

import pytest

from gamification_engine.domain.errors import RuleEvaluationError
from gamification_engine.rules.condition_parser import (
    ComparisonOperator,
    parse_condition,
)

ALLOWED_FIELDS = {"watch_minutes_today", "ratings_7d"}


def test_parse_condition_accepts_supported_comparison() -> None:
    """A simple condition should parse into a typed representation."""

    parsed = parse_condition("watch_minutes_today >= 60", ALLOWED_FIELDS)

    assert parsed.field_name == "watch_minutes_today"
    assert parsed.operator is ComparisonOperator.GREATER_THAN_OR_EQUAL
    assert parsed.literal_value == 60


def test_parse_condition_rejects_unknown_field() -> None:
    """Conditions may only reference whitelisted state fields."""

    with pytest.raises(RuleEvaluationError, match="Unsupported condition field"):
        parse_condition("unknown_metric >= 60", ALLOWED_FIELDS)


def test_parse_condition_rejects_compound_expression() -> None:
    """MVP rule syntax should not accept compound expressions."""

    with pytest.raises(RuleEvaluationError, match="Condition must match"):
        parse_condition(
            "watch_minutes_today >= 60 and ratings_7d >= 2",
            ALLOWED_FIELDS,
        )


def test_parse_condition_rejects_eval_payload() -> None:
    """Parser should reject Python expressions instead of evaluating them."""

    with pytest.raises(RuleEvaluationError, match="Condition must match"):
        parse_condition("__import__('os').system('echo unsafe')", ALLOWED_FIELDS)
