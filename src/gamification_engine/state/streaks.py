"""Watch streak calculation helpers."""

from __future__ import annotations

from datetime import date, timedelta

from gamification_engine.state.metrics import DailyActivityMetrics


DEFAULT_STREAK_MIN_WATCH_MINUTES = 30


def calculate_watch_streak_days(
    daily_metrics: dict[tuple[str, date], DailyActivityMetrics],
    user_id: str,
    run_date: date,
    min_watch_minutes: int = DEFAULT_STREAK_MIN_WATCH_MINUTES,
) -> int:
    """Calculate consecutive qualifying watch days ending on ``run_date``.

    A day qualifies when the user's total watch minutes for that day is greater
    than or equal to ``min_watch_minutes``. Missing days and low-watch days both
    break the streak.
    """

    streak_days = 0
    current_date = run_date

    while True:
        metrics = daily_metrics.get((user_id, current_date))
        if metrics is None:
            break
        if metrics.watch_minutes < min_watch_minutes:
            break

        streak_days += 1
        current_date -= timedelta(days=1)

    return streak_days

