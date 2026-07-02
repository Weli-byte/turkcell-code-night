"""Tests for state metric aggregation helpers."""

from datetime import date

from gamification_engine.domain.models import UserActivity
from gamification_engine.state.metrics import (
    aggregate_daily_metrics,
    get_user_ids,
    sum_metric_in_window,
)


def test_aggregate_daily_metrics_sums_duplicate_user_dates() -> None:
    """Multiple activity rows on the same day should be aggregated."""

    activities = [
        UserActivity(
            user_id="U1",
            activity_date=date(2026, 3, 14),
            watch_minutes=20,
            episodes_completed=1,
            unique_genres=1,
            watch_party_minutes=5,
            ratings_given=1,
        ),
        UserActivity(
            user_id="U1",
            activity_date=date(2026, 3, 14),
            watch_minutes=40,
            episodes_completed=2,
            unique_genres=2,
            watch_party_minutes=15,
            ratings_given=0,
        ),
    ]

    metrics = aggregate_daily_metrics(activities)
    aggregated = metrics[("U1", date(2026, 3, 14))]

    assert aggregated.watch_minutes == 60
    assert aggregated.episodes_completed == 3
    assert aggregated.unique_genres == 3
    assert aggregated.watch_party_minutes == 20
    assert aggregated.ratings_given == 1


def test_sum_metric_in_window_uses_inclusive_7_day_window() -> None:
    """The rolling window should include run date and previous six days."""

    activities = [
        UserActivity(
            user_id="U1",
            activity_date=date(2026, 3, 8),
            watch_minutes=999,
            episodes_completed=0,
            unique_genres=0,
            watch_party_minutes=0,
            ratings_given=0,
        ),
        UserActivity(
            user_id="U1",
            activity_date=date(2026, 3, 9),
            watch_minutes=10,
            episodes_completed=0,
            unique_genres=0,
            watch_party_minutes=0,
            ratings_given=0,
        ),
        UserActivity(
            user_id="U1",
            activity_date=date(2026, 3, 15),
            watch_minutes=20,
            episodes_completed=0,
            unique_genres=0,
            watch_party_minutes=0,
            ratings_given=0,
        ),
    ]

    metrics = aggregate_daily_metrics(activities)

    assert (
        sum_metric_in_window(
            metrics,
            user_id="U1",
            end_date=date(2026, 3, 15),
            window_days=7,
            metric_name="watch_minutes",
        )
        == 30
    )


def test_get_user_ids_returns_sorted_unique_users() -> None:
    """User IDs should be stable for deterministic state output."""

    activities = [
        UserActivity(
            user_id="U2",
            activity_date=date(2026, 3, 14),
            watch_minutes=1,
            episodes_completed=0,
            unique_genres=0,
            watch_party_minutes=0,
            ratings_given=0,
        ),
        UserActivity(
            user_id="U1",
            activity_date=date(2026, 3, 14),
            watch_minutes=1,
            episodes_completed=0,
            unique_genres=0,
            watch_party_minutes=0,
            ratings_given=0,
        ),
    ]

    assert get_user_ids(aggregate_daily_metrics(activities)) == ["U1", "U2"]

