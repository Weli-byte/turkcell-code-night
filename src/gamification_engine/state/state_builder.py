"""Build typed daily user state from raw user activities."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date

from gamification_engine.domain.models import DailyUserState, UserActivity
from gamification_engine.state.metrics import (
    aggregate_daily_metrics,
    get_metric_for_date,
    get_user_ids,
    sum_metric_in_window,
)
from gamification_engine.state.streaks import (
    DEFAULT_STREAK_MIN_WATCH_MINUTES,
    calculate_watch_streak_days,
)


def build_daily_user_states(
    activities: Iterable[UserActivity],
    run_date: date,
    streak_min_watch_minutes: int = DEFAULT_STREAK_MIN_WATCH_MINUTES,
) -> list[DailyUserState]:
    """Build deterministic daily state rows for every user in activity data.

    Args:
        activities: Raw activity records.
        run_date: Reference date for today, rolling window, and streak metrics.
        streak_min_watch_minutes: Minimum daily watch minutes required to count
            toward the watch streak.

    Returns:
        State rows sorted by ``user_id``.
    """

    daily_metrics = aggregate_daily_metrics(activities)
    states: list[DailyUserState] = []

    for user_id in get_user_ids(daily_metrics):
        today_metrics = get_metric_for_date(daily_metrics, user_id, run_date)

        states.append(
            DailyUserState(
                user_id=user_id,
                state_date=run_date,
                watch_minutes_today=(
                    today_metrics.watch_minutes if today_metrics is not None else 0
                ),
                watch_minutes_7d=sum_metric_in_window(
                    daily_metrics,
                    user_id,
                    run_date,
                    window_days=7,
                    metric_name="watch_minutes",
                ),
                episodes_completed_today=(
                    today_metrics.episodes_completed if today_metrics is not None else 0
                ),
                episodes_completed_7d=sum_metric_in_window(
                    daily_metrics,
                    user_id,
                    run_date,
                    window_days=7,
                    metric_name="episodes_completed",
                ),
                unique_genres_today=(
                    today_metrics.unique_genres if today_metrics is not None else 0
                ),
                watch_party_minutes_today=(
                    today_metrics.watch_party_minutes
                    if today_metrics is not None
                    else 0
                ),
                ratings_today=(
                    today_metrics.ratings_given if today_metrics is not None else 0
                ),
                ratings_7d=sum_metric_in_window(
                    daily_metrics,
                    user_id,
                    run_date,
                    window_days=7,
                    metric_name="ratings_given",
                ),
                watch_streak_days=calculate_watch_streak_days(
                    daily_metrics,
                    user_id,
                    run_date,
                    min_watch_minutes=streak_min_watch_minutes,
                ),
            )
        )

    return states
