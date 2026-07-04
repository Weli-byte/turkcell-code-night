"""Tests for the traffic simulator service and its admin endpoints."""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session, sessionmaker

from gamification_backend.config import BackendSettings
from gamification_backend.db.base import create_session_factory
from gamification_backend.db.models import UserRecord, WatchEventRecord
from gamification_backend.main import create_app
from gamification_backend.repositories.catalog import seed_catalog_from_json
from gamification_backend.repositories.challenges import seed_challenges_from_csv
from gamification_backend.repositories.leaderboard import build_leaderboard
from gamification_backend.services.simulator import PERSONAS, TrafficSimulator

from .conftest import CHALLENGES_CSV
from .test_catalog import CATALOG_JSON


@pytest.fixture()
def seeded_factory(engine: Engine, session: Session) -> sessionmaker[Session]:
    """Session factory over a database seeded with challenges + catalog."""

    seed_challenges_from_csv(session, CHALLENGES_CSV)
    seed_catalog_from_json(session, CATALOG_JSON)
    return create_session_factory(engine)


def test_ensure_bots_creates_flagged_accounts(
    seeded_factory: sessionmaker[Session],
) -> None:
    simulator = TrafficSimulator(seeded_factory)

    simulator.ensure_bots(6)

    with seeded_factory() as session:
        bots = list(
            session.execute(
                select(UserRecord).where(UserRecord.is_bot.is_(True))
            ).scalars()
        )
    assert len(bots) == 6
    assert all(bot.password_hash is None for bot in bots)
    assert all(bot.username.startswith("sim-") for bot in bots)


def test_ensure_bots_is_idempotent(
    seeded_factory: sessionmaker[Session],
) -> None:
    simulator = TrafficSimulator(seeded_factory)
    simulator.ensure_bots(4)
    simulator.ensure_bots(4)

    with seeded_factory() as session:
        count = len(
            list(
                session.execute(
                    select(UserRecord.id).where(UserRecord.is_bot.is_(True))
                ).scalars()
            )
        )
    assert count == 4


def test_personas_cycle_across_bots(
    seeded_factory: sessionmaker[Session],
) -> None:
    simulator = TrafficSimulator(seeded_factory)
    simulator.ensure_bots(len(PERSONAS) * 2)

    with seeded_factory() as session:
        usernames = sorted(
            session.execute(
                select(UserRecord.username).where(UserRecord.is_bot.is_(True))
            ).scalars()
        )
    for persona in PERSONAS:
        assert sum(1 for name in usernames if f"-{persona.key}-" in name) == 2


def test_ticks_record_events_and_grant_points(
    seeded_factory: sessionmaker[Session],
) -> None:
    simulator = TrafficSimulator(seeded_factory, seed=7)
    simulator.ensure_bots(6)

    for _ in range(10):
        simulator._tick()  # noqa: SLF001 (deliberate synchronous drive)

    state = simulator.status()
    assert state.ticks_completed == 10
    assert state.events_recorded > 0
    with seeded_factory() as session:
        events = list(session.execute(select(WatchEventRecord.id)).scalars())
        assert len(events) > 0
        leaderboard = build_leaderboard(session)
    # Binge bots watch every tick; ten ticks comfortably cross CH-001.
    assert any(row.is_bot for row in leaderboard)


def test_same_seed_produces_same_traffic(
    seeded_factory: sessionmaker[Session], second_database: Session
) -> None:
    from gamification_backend.db.base import create_session_factory as csf

    seed_challenges_from_csv(second_database, CHALLENGES_CSV)
    seed_catalog_from_json(second_database, CATALOG_JSON)
    second_factory = csf(second_database.get_bind())  # type: ignore[arg-type]

    first = TrafficSimulator(seeded_factory, seed=42)
    second = TrafficSimulator(second_factory, seed=42)
    first.ensure_bots(6)
    second.ensure_bots(6)
    for _ in range(5):
        first._tick()  # noqa: SLF001
        second._tick()  # noqa: SLF001

    assert first.status().events_recorded == second.status().events_recorded


def test_loop_runs_and_stops(seeded_factory: sessionmaker[Session]) -> None:
    simulator = TrafficSimulator(seeded_factory, seed=3)

    async def scenario() -> None:
        started = await simulator.start(bot_count=3, tick_seconds=0.01)
        assert started is True
        assert await simulator.start(bot_count=3, tick_seconds=0.01) is False
        await asyncio.sleep(0.3)
        await simulator.stop()
        await simulator.stop()  # idempotent

    asyncio.run(scenario())

    assert simulator.running is False
    assert simulator.status().ticks_completed >= 1


@pytest.fixture()
def admin_client(
    challenges_csv: Path,
) -> Iterator[tuple[TestClient, dict[str, str]]]:
    settings = BackendSettings(
        database_url="sqlite://",
        challenges_csv=challenges_csv,
        seed_on_startup=True,
        jwt_secret="test-secret",  # noqa: S106
        bcrypt_rounds=4,
        scheduler_enabled=False,
        admin_username="boss",
        admin_password="admin-parola-1",  # noqa: S106
    )
    app = create_app(settings)
    with TestClient(app) as client:
        token = client.post(
            "/auth/login",
            json={"username": "boss", "password": "admin-parola-1"},
        ).json()["access_token"]
        yield client, {"Authorization": f"Bearer {token}"}


def test_simulator_api_start_stop(
    admin_client: tuple[TestClient, dict[str, str]],
) -> None:
    client, headers = admin_client

    started = client.post(
        "/admin/simulator/start",
        json={"bot_count": 4, "tick_seconds": 60},
        headers=headers,
    )
    assert started.status_code == 200
    assert started.json()["running"] is True
    assert started.json()["bot_count"] == 4

    duplicate = client.post("/admin/simulator/start", json={}, headers=headers)
    assert duplicate.status_code == 409

    stopped = client.post("/admin/simulator/stop", headers=headers)
    assert stopped.status_code == 200
    assert stopped.json()["running"] is False

    again = client.post("/admin/simulator/stop", headers=headers)
    assert again.status_code == 200


def test_simulator_api_validates_bounds(
    admin_client: tuple[TestClient, dict[str, str]],
) -> None:
    client, headers = admin_client

    response = client.post(
        "/admin/simulator/start",
        json={"bot_count": 999},
        headers=headers,
    )

    assert response.status_code == 422
