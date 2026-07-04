"""Tests for the stdlib daily scheduler and its app wiring."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from gamification_backend.config import BackendSettings
from gamification_backend.main import create_app
from gamification_backend.services import scheduler as scheduler_module
from gamification_backend.services.scheduler import (
    DailyJobScheduler,
    seconds_until_next_run,
)


def test_seconds_until_next_run_same_day() -> None:
    now = datetime(2026, 7, 4, 10, 0, 0, tzinfo=UTC)

    delay = seconds_until_next_run(now, hour=23, minute=55)

    assert delay == (13 * 3600) + (55 * 60)


def test_seconds_until_next_run_rolls_to_tomorrow() -> None:
    now = datetime(2026, 7, 4, 23, 56, 0, tzinfo=UTC)

    delay = seconds_until_next_run(now, hour=23, minute=55)

    assert delay == (24 * 3600) - 60


def test_exactly_at_target_schedules_tomorrow() -> None:
    now = datetime(2026, 7, 4, 23, 55, 0, tzinfo=UTC)

    delay = seconds_until_next_run(now, hour=23, minute=55)

    assert delay == 24 * 3600


def test_scheduler_runs_job_and_stops(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        scheduler_module, "seconds_until_next_run", lambda *a, **k: 0.01
    )
    calls: list[int] = []
    scheduler = DailyJobScheduler(lambda: calls.append(1), hour=0, minute=0)

    async def scenario() -> None:
        scheduler.start()
        await asyncio.sleep(0.2)
        await scheduler.stop()

    asyncio.run(scenario())

    assert len(calls) >= 1


def test_scheduler_survives_job_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        scheduler_module, "seconds_until_next_run", lambda *a, **k: 0.01
    )
    calls: list[int] = []

    def flaky_job() -> None:
        calls.append(1)
        raise RuntimeError("boom")

    scheduler = DailyJobScheduler(flaky_job, hour=0, minute=0)

    async def scenario() -> None:
        scheduler.start()
        await asyncio.sleep(0.2)
        await scheduler.stop()

    asyncio.run(scenario())

    assert len(calls) >= 2  # kept running after the first failure


def test_app_without_scheduler(test_settings: BackendSettings) -> None:
    app = create_app(test_settings)

    with TestClient(app):
        assert app.state.scheduler is None


def test_app_with_scheduler_starts_and_stops(
    test_settings: BackendSettings,
) -> None:
    settings = test_settings.model_copy(update={"scheduler_enabled": True})
    app = create_app(settings)

    with TestClient(app):
        assert app.state.scheduler is not None
