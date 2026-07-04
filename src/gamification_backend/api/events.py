"""Activity-event ingestion endpoints.

The authenticated user is always the event's subject — ``user_id`` never
comes from the request body, so accounts cannot report activity for each
other. Event dates are assigned server-side (UTC).
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlalchemy.orm import Session

from gamification_backend.api.deps import CurrentUserDep, SessionDep
from gamification_backend.api.schemas import (
    CompleteRequest,
    EventResponse,
    HeartbeatRequest,
    RatingRequest,
    WatchPartyRequest,
)
from gamification_backend.db.models import VideoRecord
from gamification_backend.repositories.catalog import get_video
from gamification_backend.repositories.events import EventRepository, today_utc

router = APIRouter(prefix="/events", tags=["events"])


def _video_or_404(session: Session, video_id: str) -> VideoRecord:
    video = get_video(session, video_id)
    if video is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Video bulunamadı."
        )
    return video


@router.post("/heartbeat")
def heartbeat(
    body: HeartbeatRequest, session: SessionDep, user: CurrentUserDep
) -> EventResponse:
    """Report watched seconds since the previous heartbeat."""

    video = _video_or_404(session, body.video_id)
    counted = EventRepository(session).record_heartbeat(
        user_id=user.id,
        video=video,
        watch_seconds=body.watch_seconds,
        event_date=today_utc(),
    )
    return EventResponse(status="ok", counted=counted)


@router.post("/complete")
def complete(
    body: CompleteRequest, session: SessionDep, user: CurrentUserDep
) -> EventResponse:
    """Report a finished video/episode (one per video per day)."""

    video = _video_or_404(session, body.video_id)
    counted = EventRepository(session).record_complete(
        user_id=user.id, video=video, event_date=today_utc()
    )
    return EventResponse(status="ok", counted=counted)


@router.post("/rating")
def rating(
    body: RatingRequest, session: SessionDep, user: CurrentUserDep
) -> EventResponse:
    """Rate a video 1-5 (a video can be rated only once per user)."""

    video = _video_or_404(session, body.video_id)
    counted = EventRepository(session).record_rating(
        user_id=user.id, video=video, rating=body.rating, event_date=today_utc()
    )
    return EventResponse(status="ok", counted=counted)


@router.post("/watch-party")
def watch_party(
    body: WatchPartyRequest, session: SessionDep, user: CurrentUserDep
) -> EventResponse:
    """Report watch-party seconds since the previous report."""

    video = _video_or_404(session, body.video_id)
    counted = EventRepository(session).record_watch_party(
        user_id=user.id,
        video=video,
        party_seconds=body.party_seconds,
        event_date=today_utc(),
    )
    return EventResponse(status="ok", counted=counted)
