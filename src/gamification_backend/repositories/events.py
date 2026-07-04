"""Watch-event ingestion with anti-abuse guards.

Rules enforced here (beyond pydantic's per-request bounds):

- Daily watch/party seconds per user+video are capped at three times the
  video duration; excess reports are ignored (``counted=False``), never
  stored. Rewatching is allowed, unbounded farming is not.
- One ``complete`` per user+video+day.
- One ``rating`` per user+video ever.

The event date is always assigned by the server (UTC), so clients cannot
back- or forward-date their activity.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from enum import StrEnum

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from gamification_backend.db.models import VideoRecord, WatchEventRecord

DAILY_WATCH_CAP_FACTOR = 3


class EventType(StrEnum):
    """Kinds of activity events reported by the player or simulator."""

    HEARTBEAT = "heartbeat"
    COMPLETE = "complete"
    RATING = "rating"
    WATCH_PARTY = "watch_party"


def today_utc() -> date:
    """Server-assigned event date (UTC)."""

    return datetime.now(UTC).date()


class EventRepository:
    """Validated writes to the ``watch_events`` table."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def record_heartbeat(
        self,
        *,
        user_id: str,
        video: VideoRecord,
        watch_seconds: int,
        event_date: date,
    ) -> bool:
        """Store watched seconds; False when the daily cap would be exceeded."""

        if self._daily_cap_exceeded(
            user_id, video, extra=watch_seconds, event_date=event_date
        ):
            return False
        self._add(
            user_id=user_id,
            video_id=video.id,
            event_type=EventType.HEARTBEAT,
            event_date=event_date,
            watch_seconds=watch_seconds,
        )
        return True

    def record_complete(
        self, *, user_id: str, video: VideoRecord, event_date: date
    ) -> bool:
        """Count an episode completion; one per user+video+day."""

        stmt = select(WatchEventRecord.id).where(
            WatchEventRecord.user_id == user_id,
            WatchEventRecord.video_id == video.id,
            WatchEventRecord.event_type == EventType.COMPLETE.value,
            WatchEventRecord.event_date == event_date,
        )
        if self._session.execute(stmt).first() is not None:
            return False
        self._add(
            user_id=user_id,
            video_id=video.id,
            event_type=EventType.COMPLETE,
            event_date=event_date,
            episodes_completed=1,
        )
        return True

    def record_rating(
        self, *, user_id: str, video: VideoRecord, rating: int, event_date: date
    ) -> bool:
        """Store a 1-5 rating; a user rates a given video only once."""

        stmt = select(WatchEventRecord.id).where(
            WatchEventRecord.user_id == user_id,
            WatchEventRecord.video_id == video.id,
            WatchEventRecord.event_type == EventType.RATING.value,
        )
        if self._session.execute(stmt).first() is not None:
            return False
        self._add(
            user_id=user_id,
            video_id=video.id,
            event_type=EventType.RATING,
            event_date=event_date,
            rating_value=rating,
        )
        return True

    def record_watch_party(
        self,
        *,
        user_id: str,
        video: VideoRecord,
        party_seconds: int,
        event_date: date,
    ) -> bool:
        """Store watch-party seconds; same daily cap as heartbeats."""

        if self._daily_cap_exceeded(
            user_id, video, extra=party_seconds, event_date=event_date
        ):
            return False
        self._add(
            user_id=user_id,
            video_id=video.id,
            event_type=EventType.WATCH_PARTY,
            event_date=event_date,
            watch_party_seconds=party_seconds,
        )
        return True

    def _daily_cap_exceeded(
        self, user_id: str, video: VideoRecord, *, extra: int, event_date: date
    ) -> bool:
        cap = video.duration_seconds * DAILY_WATCH_CAP_FACTOR
        total = func.coalesce(
            func.sum(
                WatchEventRecord.watch_seconds + WatchEventRecord.watch_party_seconds
            ),
            0,
        )
        stmt = select(total).where(
            WatchEventRecord.user_id == user_id,
            WatchEventRecord.video_id == video.id,
            WatchEventRecord.event_date == event_date,
        )
        current = int(self._session.execute(stmt).scalar_one())
        return current + extra > cap

    def _add(
        self,
        *,
        user_id: str,
        video_id: str,
        event_type: EventType,
        event_date: date,
        watch_seconds: int = 0,
        episodes_completed: int = 0,
        watch_party_seconds: int = 0,
        rating_value: int | None = None,
    ) -> None:
        self._session.add(
            WatchEventRecord(
                user_id=user_id,
                video_id=video_id,
                event_type=event_type.value,
                event_date=event_date,
                watch_seconds=watch_seconds,
                episodes_completed=episodes_completed,
                watch_party_seconds=watch_party_seconds,
                rating_value=rating_value,
            )
        )
        self._session.commit()
