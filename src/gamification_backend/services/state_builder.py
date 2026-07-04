"""Build the engine's ``DailyUserState`` from database watch events.

This is the bridge between the live platform and the deterministic engine:
raw ``watch_events`` rows are aggregated into exactly the typed state object
the engine's rule evaluator consumes. Seconds are converted to whole minutes
with integer division (engine rule: integers over floats).
"""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from gamification_backend.db.models import VideoRecord, WatchEventRecord
from gamification_backend.repositories.events import EventType
from gamification_engine.domain.models import DailyUserState


def build_daily_state(
    session: Session, *, user_id: str, target_date: date
) -> DailyUserState:
    """Aggregate the user's events into the engine's daily state."""

    week_start = target_date - timedelta(days=6)
    today = _totals(session, user_id, target_date, target_date)
    week = _totals(session, user_id, week_start, target_date)

    return DailyUserState(
        user_id=user_id,
        state_date=target_date,
        watch_minutes_today=today.watch_seconds // 60,
        watch_minutes_7d=week.watch_seconds // 60,
        episodes_completed_today=today.episodes,
        episodes_completed_7d=week.episodes,
        unique_genres_today=_unique_genres(session, user_id, target_date),
        watch_party_minutes_today=today.party_seconds // 60,
        ratings_today=today.ratings,
        ratings_7d=week.ratings,
        watch_streak_days=_watch_streak(session, user_id, target_date),
    )


class _Totals:
    """Aggregated event sums for a date window."""

    def __init__(
        self, watch_seconds: int, episodes: int, party_seconds: int, ratings: int
    ) -> None:
        self.watch_seconds = watch_seconds
        self.episodes = episodes
        self.party_seconds = party_seconds
        self.ratings = ratings


def _totals(session: Session, user_id: str, start: date, end: date) -> _Totals:
    rating_case = case(
        (WatchEventRecord.event_type == EventType.RATING.value, 1), else_=0
    )
    stmt = select(
        func.coalesce(func.sum(WatchEventRecord.watch_seconds), 0),
        func.coalesce(func.sum(WatchEventRecord.episodes_completed), 0),
        func.coalesce(func.sum(WatchEventRecord.watch_party_seconds), 0),
        func.coalesce(func.sum(rating_case), 0),
    ).where(
        WatchEventRecord.user_id == user_id,
        WatchEventRecord.event_date >= start,
        WatchEventRecord.event_date <= end,
    )
    row = session.execute(stmt).one()
    return _Totals(int(row[0]), int(row[1]), int(row[2]), int(row[3]))


def _unique_genres(session: Session, user_id: str, target_date: date) -> int:
    stmt = (
        select(func.count(func.distinct(VideoRecord.genre)))
        .select_from(WatchEventRecord)
        .join(VideoRecord, WatchEventRecord.video_id == VideoRecord.id)
        .where(
            WatchEventRecord.user_id == user_id,
            WatchEventRecord.event_date == target_date,
        )
    )
    return int(session.execute(stmt).scalar_one())


def _watch_streak(session: Session, user_id: str, target_date: date) -> int:
    """Consecutive days with watch activity, counting back from today."""

    stmt = (
        select(WatchEventRecord.event_date)
        .where(
            WatchEventRecord.user_id == user_id,
            WatchEventRecord.watch_seconds > 0,
            WatchEventRecord.event_date <= target_date,
        )
        .distinct()
        .order_by(WatchEventRecord.event_date.desc())
    )
    streak = 0
    expected = target_date
    for event_date in session.execute(stmt).scalars():
        if event_date != expected:
            break
        streak += 1
        expected -= timedelta(days=1)
    return streak
