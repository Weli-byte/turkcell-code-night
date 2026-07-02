"""Safe parser for simple challenge conditions."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

from gamification_engine.domain.errors import RuleEvaluationError


class ComparisonOperator(StrEnum):
    """Supported condition comparison operators."""

    GREATER_THAN_OR_EQUAL = ">="
    GREATER_THAN = ">"
    LESS_THAN_OR_EQUAL = "<="
    LESS_THAN = "<"
    EQUAL = "=="
    NOT_EQUAL = "!="


@dataclass(frozen=True, slots=True)
class ParsedCondition:
    """Parsed representation of a safe challenge condition."""

    field_name: str
    operator: ComparisonOperator
    literal_value: int


CONDITION_PATTERN = re.compile(
    r"^\s*(?P<field>[A-Za-z_][A-Za-z0-9_]*)\s*"
    r"(?P<operator>>=|<=|==|!=|>|<)\s*"
    r"(?P<literal>-?\d+)\s*$"
)


def parse_condition(condition: str, allowed_fields: set[str]) -> ParsedCondition:
    """Parse a simple condition string without using ``eval``.

    Supported MVP shape:

    ```text
    field operator integer_literal
    ```

    Args:
        condition: Raw challenge condition.
        allowed_fields: Whitelist of state fields that rules may reference.

    Raises:
        RuleEvaluationError: If the expression is unsupported or references an
            unknown field.
    """

    match = CONDITION_PATTERN.fullmatch(condition)
    if match is None:
        raise RuleEvaluationError(
            "Condition must match: field operator integer_literal."
        )

    field_name = match.group("field")
    if field_name not in allowed_fields:
        raise RuleEvaluationError(f"Unsupported condition field: {field_name}.")

    return ParsedCondition(
        field_name=field_name,
        operator=ComparisonOperator(match.group("operator")),
        literal_value=int(match.group("literal")),
    )

