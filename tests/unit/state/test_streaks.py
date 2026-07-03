"""Tests for watch streak calculations."""

from datetime import date

from gamification_engine.domain.models import UserActivity
from gamification_engine.state.metrics import aggregate_daily_metrics
from gamification_engine.state.streaks import calculate_watch_streak_days


def test_calculate_watch_streak_counts_back_from_run_date() -> None:
    """Streak should count consecutive qualifying days ending on run date."""

    activities = [
        UserActivity(
            user_id="U1",
            activity_date=date(2026, 3, 12),
            watch_minutes=30,
            episodes_completed=0,
            unique_genres=0,
            watch_party_minutes=0,
            ratings_given=0,
        ),
        UserActivity(
            user_id="U1",
            activity_date=date(2026, 3, 13),
            watch_minutes=45,
            episodes_completed=0,
            unique_genres=0,
            watch_party_minutes=0,
            ratings_given=0,
        ),
        UserActivity(
            user_id="U1",
            activity_date=date(2026, 3, 14),
            watch_minutes=60,
            episodes_completed=0,
            unique_genres=0,
            watch_party_minutes=0,
            ratings_given=0,
        ),
    ]

    assert (
        calculate_watch_streak_days(
            aggregate_daily_metrics(activities),
            user_id="U1",
            run_date=date(2026, 3, 14),
        )
        == 3
    )


def test_calculate_watch_streak_breaks_on_low_watch_day() -> None:
    """A low-watch day should break the streak."""

    activities = [
        UserActivity(
            user_id="U1",
            activity_date=date(2026, 3, 13),
            watch_minutes=29,
            episodes_completed=0,
            unique_genres=0,
            watch_party_minutes=0,
            ratings_given=0,
        ),
        UserActivity(
            user_id="U1",
            activity_date=date(2026, 3, 14),
            watch_minutes=60,
            episodes_completed=0,
            unique_genres=0,
            watch_party_minutes=0,
            ratings_given=0,
        ),
    ]

    assert (
        calculate_watch_streak_days(
            aggregate_daily_metrics(activities),
            user_id="U1",
            run_date=date(2026, 3, 14),
        )
        == 1
    )


def test_calculate_watch_streak_is_zero_when_run_date_is_missing() -> None:
    """A user needs qualifying activity on the run date to have a streak."""

    activities = [
        UserActivity(
            user_id="U1",
            activity_date=date(2026, 3, 13),
            watch_minutes=60,
            episodes_completed=0,
            unique_genres=0,
            watch_party_minutes=0,
            ratings_given=0,
        )
    ]

    assert (
        calculate_watch_streak_days(
            aggregate_daily_metrics(activities),
            user_id="U1",
            run_date=date(2026, 3, 14),
        )
        == 0
    )
