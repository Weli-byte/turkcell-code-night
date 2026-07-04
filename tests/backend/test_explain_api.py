"""End-to-end tests for the live explanation endpoint."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from gamification_backend.config import BackendSettings
from gamification_backend.db.models import WatchEventRecord
from gamification_backend.main import create_app
from gamification_backend.repositories.events import today_utc


@pytest.fixture(autouse=True)
def _llm_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep answers purely deterministic regardless of local env vars."""

    monkeypatch.setenv("GAMIFICATION_LLM_ENABLED", "0")


@pytest.fixture()
def client_headers(
    test_settings: BackendSettings,
) -> Iterator[tuple[TestClient, dict[str, str], str]]:
    app = create_app(test_settings)
    with TestClient(app) as client:
        body = client.post(
            "/auth/register",
            json={"username": "veli", "password": "cok-gizli-parola"},
        ).json()
        headers = {"Authorization": f"Bearer {body['access_token']}"}
        yield client, headers, body["user"]["id"]


def _earn_daily_reward(
    client: TestClient, headers: dict[str, str], user_id: str
) -> None:
    """Seed 60 minutes of watching and trigger the live reward (CH-001)."""

    factory: sessionmaker[Session] = client.app.state.session_factory  # type: ignore[attr-defined]
    with factory() as session:
        session.add(
            WatchEventRecord(
                user_id=user_id,
                video_id="V-BBB",
                event_type="heartbeat",
                event_date=today_utc(),
                watch_seconds=3570,
            )
        )
        session.commit()
    client.post(
        "/events/heartbeat",
        json={"video_id": "V-ED", "watch_seconds": 30},
        headers=headers,
    )


def _ask(client: TestClient, headers: dict[str, str], question: str) -> dict:
    response = client.post("/explain", json={"question": question}, headers=headers)
    assert response.status_code == 200
    return dict(response.json())


def test_explain_requires_auth(
    client_headers: tuple[TestClient, dict[str, str], str],
) -> None:
    client, _, _ = client_headers

    response = client.post("/explain", json={"question": "Kaç puanım var?"})

    assert response.status_code == 401


def test_points_question(
    client_headers: tuple[TestClient, dict[str, str], str],
) -> None:
    client, headers, user_id = client_headers
    _earn_daily_reward(client, headers, user_id)

    body = _ask(client, headers, "Kaç puanım var?")

    assert body["user_id"] == "veli"
    assert "80" in body["answer"]
    assert body["evidence"]["total_points"] == 80


def test_rank_question_uses_usernames(
    client_headers: tuple[TestClient, dict[str, str], str],
) -> None:
    client, headers, user_id = client_headers
    _earn_daily_reward(client, headers, user_id)

    body = _ask(client, headers, "Liderlik tablosunda neden bu sıradayım?")

    assert body["evidence"]["rank"] == 1
    assert "1. sıra" in body["answer"]


def test_badge_question(
    client_headers: tuple[TestClient, dict[str, str], str],
) -> None:
    client, headers, user_id = client_headers
    _earn_daily_reward(client, headers, user_id)

    body = _ask(client, headers, "Gold rozetine ulaşmak için ne yapmalıyım?")

    assert "GOLD" in body["answer"].upper()
    assert body["evidence"]["current_points"] == 80


def test_unknown_question_gets_fallback(
    client_headers: tuple[TestClient, dict[str, str], str],
) -> None:
    client, headers, _ = client_headers

    body = _ask(client, headers, "Bugün hava nasıl olacak acaba?")

    assert body["answer"] != ""
    assert body["evidence"] == {} or "intent" not in body["evidence"]


def test_fresh_user_points_question(
    client_headers: tuple[TestClient, dict[str, str], str],
) -> None:
    client, headers, _ = client_headers

    body = _ask(client, headers, "Kaç puanım var?")

    assert body["evidence"]["total_points"] == 0


def test_short_question_rejected(
    client_headers: tuple[TestClient, dict[str, str], str],
) -> None:
    client, headers, _ = client_headers

    response = client.post("/explain", json={"question": "a"}, headers=headers)

    assert response.status_code == 422
