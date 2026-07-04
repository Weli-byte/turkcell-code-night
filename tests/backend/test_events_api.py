"""End-to-end tests for activity-event ingestion."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from gamification_backend.config import BackendSettings
from gamification_backend.db.models import WatchEventRecord
from gamification_backend.main import create_app
from gamification_backend.repositories.events import today_utc


@pytest.fixture()
def app_and_client(
    test_settings: BackendSettings,
) -> Iterator[tuple[TestClient, dict[str, str]]]:
    """Client plus auth headers for a freshly registered user."""

    app = create_app(test_settings)
    with TestClient(app) as client:
        token = client.post(
            "/auth/register",
            json={"username": "veli", "password": "cok-gizli-parola"},
        ).json()["access_token"]
        yield client, {"Authorization": f"Bearer {token}"}


def test_events_require_auth(app_and_client: tuple[TestClient, dict[str, str]]) -> None:
    client, _ = app_and_client

    response = client.post(
        "/events/heartbeat", json={"video_id": "V-BBB", "watch_seconds": 30}
    )

    assert response.status_code == 401


def test_heartbeat_is_stored_with_server_date(
    app_and_client: tuple[TestClient, dict[str, str]],
) -> None:
    client, headers = app_and_client

    response = client.post(
        "/events/heartbeat",
        json={"video_id": "V-BBB", "watch_seconds": 30},
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "counted": True}
    with client.app.state.session_factory() as session:  # type: ignore[attr-defined]
        event = session.execute(select(WatchEventRecord)).scalar_one()
        assert event.event_type == "heartbeat"
        assert event.watch_seconds == 30
        assert event.event_date == today_utc()
        assert event.user_id.startswith("u-")


def test_heartbeat_rejects_non_positive_and_oversized(
    app_and_client: tuple[TestClient, dict[str, str]],
) -> None:
    client, headers = app_and_client

    for seconds in (0, -10, 301):
        response = client.post(
            "/events/heartbeat",
            json={"video_id": "V-BBB", "watch_seconds": seconds},
            headers=headers,
        )
        assert response.status_code == 422


def test_heartbeat_unknown_video_404(
    app_and_client: tuple[TestClient, dict[str, str]],
) -> None:
    client, headers = app_and_client

    response = client.post(
        "/events/heartbeat",
        json={"video_id": "V-YOK", "watch_seconds": 30},
        headers=headers,
    )

    assert response.status_code == 404


def test_daily_watch_cap_stops_farming(
    app_and_client: tuple[TestClient, dict[str, str]],
) -> None:
    """V-S1E1 lasts 15s -> daily cap 45s; the 46th second is ignored."""

    client, headers = app_and_client

    accepted = [
        client.post(
            "/events/heartbeat",
            json={"video_id": "V-S1E1", "watch_seconds": 15},
            headers=headers,
        ).json()["counted"]
        for _ in range(4)
    ]

    assert accepted == [True, True, True, False]


def test_complete_once_per_video_per_day(
    app_and_client: tuple[TestClient, dict[str, str]],
) -> None:
    client, headers = app_and_client
    body = {"video_id": "V-S1E1"}

    first = client.post("/events/complete", json=body, headers=headers)
    second = client.post("/events/complete", json=body, headers=headers)

    assert first.json()["counted"] is True
    assert second.json()["counted"] is False


def test_complete_different_videos_both_count(
    app_and_client: tuple[TestClient, dict[str, str]],
) -> None:
    client, headers = app_and_client

    first = client.post(
        "/events/complete", json={"video_id": "V-S1E1"}, headers=headers
    )
    second = client.post(
        "/events/complete", json={"video_id": "V-S1E2"}, headers=headers
    )

    assert first.json()["counted"] is True
    assert second.json()["counted"] is True


def test_rating_bounds_enforced(
    app_and_client: tuple[TestClient, dict[str, str]],
) -> None:
    client, headers = app_and_client

    for rating in (0, 6):
        response = client.post(
            "/events/rating",
            json={"video_id": "V-BBB", "rating": rating},
            headers=headers,
        )
        assert response.status_code == 422


def test_rating_only_once_per_video(
    app_and_client: tuple[TestClient, dict[str, str]],
) -> None:
    client, headers = app_and_client
    body = {"video_id": "V-BBB", "rating": 5}

    first = client.post("/events/rating", json=body, headers=headers)
    second = client.post(
        "/events/rating", json={"video_id": "V-BBB", "rating": 1}, headers=headers
    )

    assert first.json()["counted"] is True
    assert second.json()["counted"] is False


def test_watch_party_counts_toward_daily_cap(
    app_and_client: tuple[TestClient, dict[str, str]],
) -> None:
    """Party seconds and watch seconds share the same per-video daily cap."""

    client, headers = app_and_client

    party = client.post(
        "/events/watch-party",
        json={"video_id": "V-S1E1", "party_seconds": 40},
        headers=headers,
    )
    heartbeat = client.post(
        "/events/heartbeat",
        json={"video_id": "V-S1E1", "watch_seconds": 10},
        headers=headers,
    )

    assert party.json()["counted"] is True
    assert heartbeat.json()["counted"] is False
