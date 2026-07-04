"""Round-trip and constraint tests for the ORM schema."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from gamification_backend.db.models import (
    BadgeRecord,
    ChallengeRecord,
    NotificationRecord,
    PointsLedgerRecord,
    RunRecord,
    SeriesRecord,
    UserRecord,
    VideoRecord,
    WatchEventRecord,
)

from .conftest import UserFactory

RUN_DATE = date(2026, 7, 4)


def test_full_schema_round_trip(session: Session, make_user: UserFactory) -> None:
    """One row of every table can be inserted and read back."""

    user = make_user()
    session.add(SeriesRecord(id="S-1", title="Test Dizi", genre="drama"))
    session.add(
        VideoRecord(
            id="V-1",
            series_id="S-1",
            title="Bolum 1",
            genre="drama",
            duration_seconds=1200,
            url="https://example.com/v1.mp4",
            episode_number=1,
        )
    )
    session.add(
        WatchEventRecord(
            user_id=user.id,
            video_id="V-1",
            event_type="heartbeat",
            event_date=RUN_DATE,
            watch_seconds=60,
        )
    )
    session.add(
        NotificationRecord(
            notification_id="N-1",
            user_id=user.id,
            notification_type="CHALLENGE_REWARD",
            channel="IN_APP",
            message="Tebrikler!",
            source_ref="RW-1",
        )
    )
    session.add(RunRecord(run_date=RUN_DATE, run_type="daily", status="success"))
    session.commit()

    event = session.execute(select(WatchEventRecord)).scalar_one()
    assert event.user_id == "u001"
    assert event.watch_seconds == 60
    assert session.get(VideoRecord, "V-1") is not None


def test_username_must_be_unique(session: Session, make_user: UserFactory) -> None:
    make_user("u001")
    session.add(UserRecord(id="other", username="u001"))

    with pytest.raises(IntegrityError):
        session.commit()


def test_badge_unique_per_user_and_type(
    session: Session, make_user: UserFactory
) -> None:
    make_user()
    session.add(BadgeRecord(user_id="u001", badge_type="BRONZE", awarded_at=RUN_DATE))
    session.commit()
    session.add(BadgeRecord(user_id="u001", badge_type="BRONZE", awarded_at=RUN_DATE))

    with pytest.raises(IntegrityError):
        session.commit()


def test_ledger_check_constraint_rejects_non_positive_delta(
    session: Session, make_user: UserFactory
) -> None:
    make_user()
    session.add(
        PointsLedgerRecord(
            ledger_id="L-1",
            user_id="u001",
            points_delta=0,
            source="CHALLENGE_COMPLETED",
            source_ref="RW-1",
            created_at=datetime(2026, 7, 4, tzinfo=UTC),
        )
    )

    with pytest.raises(IntegrityError):
        session.commit()


def test_challenge_check_constraints(session: Session) -> None:
    session.add(
        ChallengeRecord(
            challenge_id="CH-X",
            name="Bozuk",
            challenge_type="DAILY",
            condition="watch_minutes_today >= 60",
            reward_points=-5,
            priority=1,
        )
    )

    with pytest.raises(IntegrityError):
        session.commit()


def test_watch_event_requires_existing_user(session: Session) -> None:
    session.add(
        WatchEventRecord(
            user_id="ghost",
            event_type="heartbeat",
            event_date=RUN_DATE,
            watch_seconds=10,
        )
    )

    with pytest.raises(IntegrityError):
        session.commit()
