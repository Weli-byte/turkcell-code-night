"""End-to-end tests for live challenge evaluation on the API."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from gamification_backend.config import BackendSettings
from gamification_backend.db.models import WatchEventRecord
from gamification_backend.main import create_app
from gamification_backend.repositories.events import today_utc


@pytest.fixture()
def client_user(
    test_settings: BackendSettings,
) -> Iterator[tuple[TestClient, dict[str, str], str]]:
    """Client, auth headers and user id for a registered user."""

    app = create_app(test_settings)
    with TestClient(app) as client:
        body = client.post(
            "/auth/register",
            json={"username": "veli", "password": "cok-gizli-parola"},
        ).json()
        headers = {"Authorization": f"Bearer {body['access_token']}"}
        yield client, headers, body["user"]["id"]


def _session_factory(client: TestClient) -> sessionmaker[Session]:
    factory: sessionmaker[Session] = client.app.state.session_factory  # type: ignore[attr-defined]
    return factory


def _seed_watch_seconds(
    client: TestClient,
    user_id: str,
    *,
    seconds: int,
    video_id: str = "V-BBB",
    event_date: date | None = None,
) -> None:
    """Insert raw watch seconds directly (bypasses API request caps)."""

    with _session_factory(client)() as session:
        session.add(
            WatchEventRecord(
                user_id=user_id,
                video_id=video_id,
                event_type="heartbeat",
                event_date=event_date or today_utc(),
                watch_seconds=seconds,
            )
        )
        session.commit()


def _heartbeat(
    client: TestClient, headers: dict[str, str], seconds: int = 30
) -> dict[str, object]:
    response = client.post(
        "/events/heartbeat",
        json={"video_id": "V-ED", "watch_seconds": seconds},
        headers=headers,
    )
    assert response.status_code == 200
    return dict(response.json())


def test_watching_an_hour_grants_daily_challenge(
    client_user: tuple[TestClient, dict[str, str], str],
) -> None:
    client, headers, user_id = client_user
    _seed_watch_seconds(client, user_id, seconds=3570)

    body = _heartbeat(client, headers, seconds=30)

    reward = body["reward"]
    assert isinstance(reward, dict)
    assert reward["challenge_id"] == "CH-001"
    assert reward["challenge_name"] == "Gunun Izleyicisi"
    assert reward["points"] == 80

    points = client.get("/me/points", headers=headers).json()
    assert points["total_points"] == 80
    assert len(points["entries"]) == 1
    assert points["entries"][0]["source"] == "CHALLENGE_COMPLETED"


def test_below_threshold_grants_nothing(
    client_user: tuple[TestClient, dict[str, str], str],
) -> None:
    client, headers, _ = client_user

    body = _heartbeat(client, headers, seconds=30)

    assert body["reward"] is None
    assert body["new_badges"] == []
    assert client.get("/me/points", headers=headers).json()["total_points"] == 0


def test_one_reward_per_day(
    client_user: tuple[TestClient, dict[str, str], str],
) -> None:
    client, headers, user_id = client_user
    _seed_watch_seconds(client, user_id, seconds=3600)

    first = _heartbeat(client, headers)
    second = _heartbeat(client, headers)

    assert isinstance(first["reward"], dict)
    assert second["reward"] is None
    assert client.get("/me/points", headers=headers).json()["total_points"] == 80


def test_high_priority_challenge_awards_bronze_badge(
    client_user: tuple[TestClient, dict[str, str], str],
) -> None:
    """300+ watch minutes triggers CH-004 (800p) which crosses Bronze (500)."""

    client, headers, user_id = client_user
    _seed_watch_seconds(client, user_id, seconds=18000)

    body = _heartbeat(client, headers)

    reward = body["reward"]
    assert isinstance(reward, dict)
    assert reward["challenge_id"] == "CH-004"
    assert reward["points"] == 800
    assert body["new_badges"] == ["BRONZE"]

    badges = client.get("/me/badges", headers=headers).json()
    assert [badge["badge_type"] for badge in badges] == ["BRONZE"]


def test_notifications_are_stored(
    client_user: tuple[TestClient, dict[str, str], str],
) -> None:
    client, headers, user_id = client_user
    _seed_watch_seconds(client, user_id, seconds=18000)

    _heartbeat(client, headers)

    notes = client.get("/me/notifications", headers=headers).json()
    types = [note["notification_type"] for note in notes]
    assert "CHALLENGE_REWARD" in types
    assert "BADGE_EARNED" in types
    messages = " ".join(note["message"] for note in notes)
    assert "Maraton Gunu" in messages
    assert "BRONZE" in messages


def test_challenge_progress_endpoint(
    client_user: tuple[TestClient, dict[str, str], str],
) -> None:
    client, headers, user_id = client_user
    _seed_watch_seconds(client, user_id, seconds=1800)  # 30 min

    challenges = {
        item["challenge_id"]: item
        for item in client.get("/me/challenges", headers=headers).json()
    }

    ch1 = challenges["CH-001"]  # watch_minutes_today >= 60
    assert ch1["progress_current"] == 30
    assert ch1["progress_target"] == 60
    assert ch1["progress_percent"] == 50
    assert ch1["satisfied"] is False
    assert ch1["won_today"] is False
    # Inactive CH-006 must not appear at all.
    assert "CH-006" not in challenges


def test_won_today_flag_set_after_reward(
    client_user: tuple[TestClient, dict[str, str], str],
) -> None:
    client, headers, user_id = client_user
    _seed_watch_seconds(client, user_id, seconds=3600)
    _heartbeat(client, headers)

    challenges = {
        item["challenge_id"]: item
        for item in client.get("/me/challenges", headers=headers).json()
    }

    assert challenges["CH-001"]["won_today"] is True
    assert challenges["CH-001"]["satisfied"] is True


def test_me_endpoints_require_auth(
    client_user: tuple[TestClient, dict[str, str], str],
) -> None:
    client, _, _ = client_user

    for path in ("/me/points", "/me/badges", "/me/challenges", "/me/notifications"):
        assert client.get(path).status_code == 401
