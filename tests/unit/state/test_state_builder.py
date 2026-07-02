"""Tests for building DailyUserState rows."""

from datetime import date

from gamification_engine.domain.models import UserActivity
from gamification_engine.state.state_builder import build_daily_user_states


def test_build_daily_user_states_calculates_today_rolling_and_streak() -> None:
    """State builder should produce complete metrics for each user."""

    activities = [
        UserActivity(
            user_id="U1",
            activity_date=date(2026, 3, 12),
            watch_minutes=30,
            episodes_completed=1,
            unique_genres=1,
            watch_party_minutes=0,
            ratings_given=1,
        ),
        UserActivity(
            user_id="U1",
            activity_date=date(2026, 3, 13),
            watch_minutes=45,
            episodes_completed=2,
            unique_genres=2,
            watch_party_minutes=10,
            ratings_given=0,
        ),
        UserActivity(
            user_id="U1",
            activity_date=date(2026, 3, 14),
            watch_minutes=60,
            episodes_completed=3,
            unique_genres=2,
            watch_party_minutes=20,
            ratings_given=2,
        ),
        UserActivity(
            user_id="U2",
            activity_date=date(2026, 3, 13),
            watch_minutes=90,
            episodes_completed=1,
            unique_genres=1,
            watch_party_minutes=0,
            ratings_given=1,
        ),
    ]

    states = build_daily_user_states(activities, run_date=date(2026, 3, 14))

    assert [state.user_id for state in states] == ["U1", "U2"]
    assert states[0].to_dict() == {
        "user_id": "U1",
        "state_date": "2026-03-14",
        "watch_minutes_today": 60,
        "watch_minutes_7d": 135,
        "episodes_completed_today": 3,
        "episodes_completed_7d": 6,
        "unique_genres_today": 2,
        "watch_party_minutes_today": 20,
        "ratings_today": 2,
        "ratings_7d": 3,
        "watch_streak_days": 3,
    }
    assert states[1].watch_minutes_today == 0
    assert states[1].watch_minutes_7d == 90
    assert states[1].watch_streak_days == 0


def test_build_daily_user_states_returns_empty_list_for_empty_input() -> None:
    """Empty activity input should produce no states."""

    assert build_daily_user_states([], run_date=date(2026, 3, 14)) == []


def test_build_daily_user_states_aggregates_duplicate_run_date_rows() -> None:
    """Duplicate same-day rows should be summed before state creation."""

    activities = [
        UserActivity(
            user_id="U1",
            activity_date=date(2026, 3, 14),
            watch_minutes=20,
            episodes_completed=1,
            unique_genres=1,
            watch_party_minutes=10,
            ratings_given=1,
        ),
        UserActivity(
            user_id="U1",
            activity_date=date(2026, 3, 14),
            watch_minutes=40,
            episodes_completed=2,
            unique_genres=2,
            watch_party_minutes=20,
            ratings_given=2,
        ),
    ]

    [state] = build_daily_user_states(activities, run_date=date(2026, 3, 14))

    assert state.watch_minutes_today == 60
    assert state.episodes_completed_today == 3
    assert state.unique_genres_today == 3
    assert state.watch_party_minutes_today == 30
    assert state.ratings_today == 3
    assert state.watch_streak_days == 1

