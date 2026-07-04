"""Tests for building the engine's DailyUserState from watch events."""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy.orm import Session

from gamification_backend.db.models import WatchEventRecord
from gamification_backend.repositories.catalog import seed_catalog_from_json
from gamification_backend.services.state_builder import build_daily_state

from .conftest import UserFactory
from .test_catalog import CATALOG_JSON

TODAY = date(2026, 7, 4)


def _add_event(
    session: Session,
    *,
    user_id: str = "u001",
    video_id: str = "V-BBB",
    event_type: str = "heartbeat",
    event_date: date = TODAY,
    watch_seconds: int = 0,
    episodes_completed: int = 0,
    watch_party_seconds: int = 0,
    rating_value: int | None = None,
) -> None:
    session.add(
        WatchEventRecord(
            user_id=user_id,
            video_id=video_id,
            event_type=event_type,
            event_date=event_date,
            watch_seconds=watch_seconds,
            episodes_completed=episodes_completed,
            watch_party_seconds=watch_party_seconds,
            rating_value=rating_value,
        )
    )
    session.commit()


def test_empty_state_is_all_zero(session: Session, make_user: UserFactory) -> None:
    make_user()

    state = build_daily_state(session, user_id="u001", target_date=TODAY)

    assert state.watch_minutes_today == 0
    assert state.watch_minutes_7d == 0
    assert state.watch_streak_days == 0


def test_minutes_use_integer_division(session: Session, make_user: UserFactory) -> None:
    make_user()
    seed_catalog_from_json(session, CATALOG_JSON)
    _add_event(session, watch_seconds=119)

    state = build_daily_state(session, user_id="u001", target_date=TODAY)

    assert state.watch_minutes_today == 1


def test_seven_day_window_excludes_older_events(
    session: Session, make_user: UserFactory
) -> None:
    make_user()
    seed_catalog_from_json(session, CATALOG_JSON)
    _add_event(session, watch_seconds=600)
    _add_event(session, watch_seconds=600, event_date=TODAY - timedelta(days=6))
    _add_event(session, watch_seconds=600, event_date=TODAY - timedelta(days=7))

    state = build_daily_state(session, user_id="u001", target_date=TODAY)

    assert state.watch_minutes_today == 10
    assert state.watch_minutes_7d == 20


def test_episodes_and_ratings_counted(session: Session, make_user: UserFactory) -> None:
    make_user()
    seed_catalog_from_json(session, CATALOG_JSON)
    _add_event(session, event_type="complete", episodes_completed=1)
    _add_event(session, video_id="V-ED", event_type="complete", episodes_completed=1)
    _add_event(session, event_type="rating", rating_value=5)
    _add_event(
        session,
        event_type="rating",
        rating_value=4,
        video_id="V-ED",
        event_date=TODAY - timedelta(days=2),
    )

    state = build_daily_state(session, user_id="u001", target_date=TODAY)

    assert state.episodes_completed_today == 2
    assert state.ratings_today == 1
    assert state.ratings_7d == 2


def test_unique_genres_today(session: Session, make_user: UserFactory) -> None:
    make_user()
    seed_catalog_from_json(session, CATALOG_JSON)
    _add_event(session, video_id="V-BBB", watch_seconds=60)  # animasyon
    _add_event(session, video_id="V-ED", watch_seconds=60)  # bilim-kurgu
    _add_event(session, video_id="V-TOS", watch_seconds=60)  # bilim-kurgu

    state = build_daily_state(session, user_id="u001", target_date=TODAY)

    assert state.unique_genres_today == 2


def test_watch_party_minutes(session: Session, make_user: UserFactory) -> None:
    make_user()
    seed_catalog_from_json(session, CATALOG_JSON)
    _add_event(session, event_type="watch_party", watch_party_seconds=180)

    state = build_daily_state(session, user_id="u001", target_date=TODAY)

    assert state.watch_party_minutes_today == 3


def test_watch_streak_counts_consecutive_days(
    session: Session, make_user: UserFactory
) -> None:
    make_user()
    seed_catalog_from_json(session, CATALOG_JSON)
    for days_ago in (0, 1, 2, 4):
        _add_event(
            session,
            watch_seconds=60,
            event_date=TODAY - timedelta(days=days_ago),
        )

    state = build_daily_state(session, user_id="u001", target_date=TODAY)

    assert state.watch_streak_days == 3


def test_streak_is_zero_without_watching_today(
    session: Session, make_user: UserFactory
) -> None:
    make_user()
    seed_catalog_from_json(session, CATALOG_JSON)
    _add_event(session, watch_seconds=60, event_date=TODAY - timedelta(days=1))

    state = build_daily_state(session, user_id="u001", target_date=TODAY)

    assert state.watch_streak_days == 0
