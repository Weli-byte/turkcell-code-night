"""Metric aggregation helpers for user state calculation."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta

from gamification_engine.domain.models import UserActivity


@dataclass(frozen=True, slots=True)
class DailyActivityMetrics:
    """Aggregated metrics for one user on one calendar date."""

    user_id: str
    activity_date: date
    watch_minutes: int
    episodes_completed: int
    unique_genres: int
    watch_party_minutes: int
    ratings_given: int


def aggregate_daily_metrics(
    activities: Iterable[UserActivity],
) -> dict[tuple[str, date], DailyActivityMetrics]:
    """Aggregate raw activities by user and date.

    Multiple activity records for the same user and date are summed. This keeps
    ingestion simple and gives the state engine one deterministic daily row per
    user/date pair.
    """

    totals: dict[tuple[str, date], dict[str, int]] = defaultdict(
        lambda: {
            "watch_minutes": 0,
            "episodes_completed": 0,
            "unique_genres": 0,
            "watch_party_minutes": 0,
            "ratings_given": 0,
        }
    )

    for activity in activities:
        key = (activity.user_id, activity.activity_date)
        totals[key]["watch_minutes"] += activity.watch_minutes
        totals[key]["episodes_completed"] += activity.episodes_completed
        totals[key]["unique_genres"] += activity.unique_genres
        totals[key]["watch_party_minutes"] += activity.watch_party_minutes
        totals[key]["ratings_given"] += activity.ratings_given

    return {
        key: DailyActivityMetrics(
            user_id=key[0],
            activity_date=key[1],
            watch_minutes=values["watch_minutes"],
            episodes_completed=values["episodes_completed"],
            unique_genres=values["unique_genres"],
            watch_party_minutes=values["watch_party_minutes"],
            ratings_given=values["ratings_given"],
        )
        for key, values in totals.items()
    }


def get_user_ids(
    daily_metrics: dict[tuple[str, date], DailyActivityMetrics],
) -> list[str]:
    """Return deterministic user IDs represented in aggregated metrics."""

    return sorted({user_id for user_id, _ in daily_metrics})


def get_metric_for_date(
    daily_metrics: dict[tuple[str, date], DailyActivityMetrics],
    user_id: str,
    target_date: date,
) -> DailyActivityMetrics | None:
    """Return aggregated metrics for one user/date, if present."""

    return daily_metrics.get((user_id, target_date))


def sum_metric_in_window(
    daily_metrics: dict[tuple[str, date], DailyActivityMetrics],
    user_id: str,
    end_date: date,
    window_days: int,
    metric_name: str,
) -> int:
    """Sum a metric over an inclusive rolling date window."""

    start_date = end_date - timedelta(days=window_days - 1)
    total = 0
    for (candidate_user_id, activity_date), metrics in daily_metrics.items():
        if candidate_user_id != user_id:
            continue
        if start_date <= activity_date <= end_date:
            total += int(getattr(metrics, metric_name))
    return total

