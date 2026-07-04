"""Activity-event ingestion endpoints.

The authenticated user is always the event's subject — ``user_id`` never
comes from the request body, so accounts cannot report activity for each
other. Event dates are assigned server-side (UTC).
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy.orm import Session

from gamification_backend.api.deps import CurrentUserDep, SessionDep
from gamification_backend.api.schemas import (
    CompleteRequest,
    EventResponse,
    HeartbeatRequest,
    RatingRequest,
    RewardInfo,
    WatchPartyRequest,
)
from gamification_backend.db.models import ChallengeRecord, UserRecord, VideoRecord
from gamification_backend.repositories.catalog import get_video
from gamification_backend.repositories.events import EventRepository, today_utc
from gamification_backend.services.live_evaluator import evaluate_user_live
from gamification_backend.services.notifier import NotificationBroker

router = APIRouter(prefix="/events", tags=["events"])


def _video_or_404(session: Session, video_id: str) -> VideoRecord:
    video = get_video(session, video_id)
    if video is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Video bulunamadı."
        )
    return video


def _respond(
    request: Request, session: Session, user: UserRecord, counted: bool
) -> EventResponse:
    """Run live evaluation for an accepted event and build the response."""

    if not counted:
        return EventResponse(status="ok", counted=False)
    result = evaluate_user_live(session, user_id=user.id, event_date=today_utc())

    broker: NotificationBroker = request.app.state.broker
    for note in result.notifications:
        broker.publish(
            user.id,
            {
                "type": note.notification_type,
                "message": note.message,
                "source_ref": note.source_ref,
                "created_at": note.created_at.isoformat(),
            },
        )

    reward_info: RewardInfo | None = None
    if result.reward is not None:
        reward_info = RewardInfo(
            challenge_id=result.reward.challenge_id,
            challenge_name=_challenge_name(session, result.reward.challenge_id),
            points=result.reward.reward_points,
        )
    return EventResponse(
        status="ok",
        counted=True,
        reward=reward_info,
        new_badges=[badge.badge_type for badge in result.new_badges],
    )


def _challenge_name(session: Session, challenge_id: str) -> str:
    record = session.get(ChallengeRecord, challenge_id)
    return record.name if record is not None else challenge_id


@router.post("/heartbeat")
def heartbeat(
    body: HeartbeatRequest,
    session: SessionDep,
    user: CurrentUserDep,
    request: Request,
) -> EventResponse:
    """Report watched seconds since the previous heartbeat."""

    video = _video_or_404(session, body.video_id)
    counted = EventRepository(session).record_heartbeat(
        user_id=user.id,
        video=video,
        watch_seconds=body.watch_seconds,
        event_date=today_utc(),
    )
    return _respond(request, session, user, counted)


@router.post("/complete")
def complete(
    body: CompleteRequest,
    session: SessionDep,
    user: CurrentUserDep,
    request: Request,
) -> EventResponse:
    """Report a finished video/episode (one per video per day)."""

    video = _video_or_404(session, body.video_id)
    counted = EventRepository(session).record_complete(
        user_id=user.id, video=video, event_date=today_utc()
    )
    return _respond(request, session, user, counted)


@router.post("/rating")
def rating(
    body: RatingRequest,
    session: SessionDep,
    user: CurrentUserDep,
    request: Request,
) -> EventResponse:
    """Rate a video 1-5 (a video can be rated only once per user)."""

    video = _video_or_404(session, body.video_id)
    counted = EventRepository(session).record_rating(
        user_id=user.id, video=video, rating=body.rating, event_date=today_utc()
    )
    return _respond(request, session, user, counted)


@router.post("/watch-party")
def watch_party(
    body: WatchPartyRequest,
    session: SessionDep,
    user: CurrentUserDep,
    request: Request,
) -> EventResponse:
    """Report watch-party seconds since the previous report."""

    video = _video_or_404(session, body.video_id)
    counted = EventRepository(session).record_watch_party(
        user_id=user.id,
        video=video,
        party_seconds=body.party_seconds,
        event_date=today_utc(),
    )
    return _respond(request, session, user, counted)
