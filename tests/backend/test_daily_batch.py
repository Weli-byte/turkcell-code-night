"""Tests for the end-of-day batch: gap-filling, idempotency, determinism."""

from __future__ import annotations

import json
from collections.abc import Iterable
from datetime import date

from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from gamification_backend.db.models import (
    PointsLedgerRecord,
    RunRecord,
    WatchEventRecord,
)
from gamification_backend.repositories.badges import badges_for_user
from gamification_backend.repositories.catalog import seed_catalog_from_json
from gamification_backend.repositories.challenges import seed_challenges_from_csv
from gamification_backend.repositories.leaderboard import build_leaderboard
from gamification_backend.services.daily_batch import run_daily_batch
from gamification_backend.services.live_evaluator import evaluate_user_live

from .conftest import CHALLENGES_CSV, UserFactory
from .test_catalog import CATALOG_JSON

RUN_DATE = date(2026, 7, 4)


def _seed_rules(session: Session) -> None:
    seed_challenges_from_csv(session, CHALLENGES_CSV)
    seed_catalog_from_json(session, CATALOG_JSON)


def _add_watch(
    session: Session, user_id: str, seconds: int, video_id: str = "V-BBB"
) -> None:
    session.add(
        WatchEventRecord(
            user_id=user_id,
            video_id=video_id,
            event_type="heartbeat",
            event_date=RUN_DATE,
            watch_seconds=seconds,
        )
    )
    session.commit()


def test_batch_fills_missing_rewards(session: Session, make_user: UserFactory) -> None:
    """Events without live evaluation still earn rewards at day end."""

    _seed_rules(session)
    make_user("u001")
    _add_watch(session, "u001", 3600)

    summary = run_daily_batch(session, run_date=RUN_DATE)

    assert summary.users_processed == 1
    assert summary.new_rewards == 1
    assert summary.leaderboard_size == 1
    entries = list(session.execute(select(PointsLedgerRecord)).scalars())
    assert len(entries) == 1
    assert entries[0].points_delta == 80


def test_batch_is_idempotent(session: Session, make_user: UserFactory) -> None:
    _seed_rules(session)
    make_user("u001")
    _add_watch(session, "u001", 3600)

    run_daily_batch(session, run_date=RUN_DATE)
    second = run_daily_batch(session, run_date=RUN_DATE)

    assert second.new_rewards == 0
    assert second.new_badges == 0
    entries = list(session.execute(select(PointsLedgerRecord)).scalars())
    assert len(entries) == 1


def test_batch_never_contradicts_live_evaluation(
    session: Session, make_user: UserFactory
) -> None:
    _seed_rules(session)
    make_user("u001")
    _add_watch(session, "u001", 3600)
    live = evaluate_user_live(session, user_id="u001", event_date=RUN_DATE)
    assert live.reward is not None

    summary = run_daily_batch(session, run_date=RUN_DATE)

    assert summary.new_rewards == 0
    entries = list(session.execute(select(PointsLedgerRecord)).scalars())
    assert len(entries) == 1
    assert entries[0].points_delta == 80


def test_batch_writes_run_record(session: Session, make_user: UserFactory) -> None:
    _seed_rules(session)
    make_user("u001")

    run_daily_batch(session, run_date=RUN_DATE)

    record = session.execute(select(RunRecord)).scalar_one()
    assert record.run_type == "daily"
    assert record.status == "success"
    assert record.run_date == RUN_DATE
    assert record.summary_json is not None
    assert json.loads(record.summary_json)["run_date"] == "2026-07-04"


def _run_scenario(session: Session, event_order: Iterable[tuple[str, int]]) -> None:
    """Seed three users + events in the given order, then run the batch."""

    from gamification_backend.db.models import UserRecord

    for user_id in ("u-a", "u-b", "u-c"):
        session.add(UserRecord(id=user_id, username=user_id))
    session.commit()
    _seed_rules(session)
    for user_id, seconds in event_order:
        _add_watch(session, user_id, seconds)
    run_daily_batch(session, run_date=RUN_DATE)


def _snapshot(session: Session) -> list[tuple[int, str, int, tuple[str, ...]]]:
    return [
        (row.rank, row.username, row.total_points, row.badges)
        for row in build_leaderboard(session)
    ]


def test_same_events_produce_identical_results(
    engine: Engine, session: Session, second_database: Session
) -> None:
    """Two databases, same events in reversed insertion order ⇒ same output."""

    events = [("u-a", 18000), ("u-b", 3600), ("u-c", 3600)]

    _run_scenario(session, events)
    _run_scenario(second_database, list(reversed(events)))

    assert _snapshot(session) == _snapshot(second_database)
    assert _snapshot(session) == [
        (1, "u-a", 800, ("BRONZE",)),
        (2, "u-b", 80, ()),
        (3, "u-c", 80, ()),
    ]
    for user_id in ("u-a", "u-b", "u-c"):
        first = [b.badge_type for b in badges_for_user(session, user_id)]
        second = [b.badge_type for b in badges_for_user(second_database, user_id)]
        assert first == second
