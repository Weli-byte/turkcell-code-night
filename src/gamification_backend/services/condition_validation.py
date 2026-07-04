"""Admin-side validation of challenge conditions.

Uses the engine's safe parser (no eval) with the exact whitelist of state
fields the evaluator exposes, so a condition that passes here is guaranteed
to evaluate at runtime.
"""

from __future__ import annotations

from datetime import date

from gamification_engine.domain.errors import RuleEvaluationError
from gamification_engine.domain.models import DailyUserState
from gamification_engine.rules.condition_parser import parse_condition


def allowed_condition_fields() -> set[str]:
    """State fields a challenge condition may reference.

    Derived from a zero-valued ``DailyUserState`` so the whitelist can never
    drift from what the engine actually evaluates.
    """

    probe = DailyUserState(
        user_id="probe",
        state_date=date(2000, 1, 1),
        watch_minutes_today=0,
        watch_minutes_7d=0,
        episodes_completed_today=0,
        episodes_completed_7d=0,
        unique_genres_today=0,
        watch_party_minutes_today=0,
        ratings_today=0,
        ratings_7d=0,
        watch_streak_days=0,
    )
    return set(probe.to_rule_context())


def validate_condition(condition: str) -> str | None:
    """Return an error message for an invalid condition, or None when valid."""

    try:
        parse_condition(condition, allowed_fields=allowed_condition_fields())
    except RuleEvaluationError as exc:
        return str(exc)
    return None
