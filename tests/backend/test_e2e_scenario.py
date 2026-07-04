"""Full-journey scenario test: the platform behaves as one coherent system.

Covers: register → browse catalog → watch (heartbeats through the API) →
instant reward → badge → rating/completion rules → leaderboard →
notifications → explanation → end-of-day batch sealing with no changes.
"""

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
    monkeypatch.setenv("GAMIFICATION_LLM_ENABLED", "0")


@pytest.fixture()
def client(challenges_csv: object) -> Iterator[TestClient]:
    from pathlib import Path

    settings = BackendSettings(
        database_url="sqlite://",
        challenges_csv=Path(str(challenges_csv)),
        seed_on_startup=True,
        jwt_secret="test-secret",  # noqa: S106
        bcrypt_rounds=4,
        scheduler_enabled=False,
        admin_username="boss",
        admin_password="admin-parola-1",  # noqa: S106
    )
    app = create_app(settings)
    with TestClient(app) as test_client:
        yield test_client


def _register(client: TestClient, username: str) -> dict[str, str]:
    body = client.post(
        "/auth/register",
        json={"username": username, "password": "cok-gizli-parola"},
    ).json()
    return {"Authorization": f"Bearer {body['access_token']}"}


def _seed_watch(client: TestClient, headers: dict[str, str], seconds: int) -> None:
    """Backfill raw watch seconds (as if watched earlier today), then let
    one API heartbeat trigger live evaluation."""

    me = client.get("/me", headers=headers).json()
    factory: sessionmaker[Session] = client.app.state.session_factory  # type: ignore[attr-defined]
    with factory() as session:
        session.add(
            WatchEventRecord(
                user_id=me["id"],
                video_id="V-BBB",
                event_type="heartbeat",
                event_date=today_utc(),
                watch_seconds=seconds,
            )
        )
        session.commit()


def test_full_user_journey(client: TestClient) -> None:
    # --- kayıt ---
    veli = _register(client, "veli")
    ayse = _register(client, "ayse")

    # --- katalog gerçek ve dolu ---
    catalog = client.get("/catalog").json()
    assert len(catalog["films"]) == 4
    assert len(catalog["series"]) == 2

    # --- veli 300+ dakika izler: CH-004 (800p) + anında BRONZE ---
    _seed_watch(client, veli, 17970)
    response = client.post(
        "/events/heartbeat",
        json={"video_id": "V-ED", "watch_seconds": 30},
        headers=veli,
    ).json()
    assert response["reward"]["challenge_id"] == "CH-004"
    assert response["reward"]["points"] == 800
    assert response["new_badges"] == ["BRONZE"]

    # --- ayse 60 dakika izler: CH-001 (80p) ---
    _seed_watch(client, ayse, 3570)
    response = client.post(
        "/events/heartbeat",
        json={"video_id": "V-SIN", "watch_seconds": 30},
        headers=ayse,
    ).json()
    assert response["reward"]["challenge_id"] == "CH-001"

    # --- bölüm bitirme ve puanlama kuralları ---
    first = client.post(
        "/events/complete", json={"video_id": "V-S1E1"}, headers=ayse
    ).json()
    duplicate = client.post(
        "/events/complete", json={"video_id": "V-S1E1"}, headers=ayse
    ).json()
    assert first["counted"] is True
    assert duplicate["counted"] is False
    rating = client.post(
        "/events/rating", json={"video_id": "V-BBB", "rating": 5}, headers=ayse
    ).json()
    assert rating["counted"] is True

    # --- leaderboard: veli 800p #1, ayse 80p #2 ---
    board = client.get("/leaderboard", headers=veli).json()
    assert [(row["rank"], row["username"], row["total_points"]) for row in board] == [
        (1, "veli", 800),
        (2, "ayse", 80),
    ]
    assert board[0]["badges"] == ["BRONZE"]

    # --- bildirimler kalıcı ---
    notes = client.get("/me/notifications", headers=veli).json()
    types = {note["notification_type"] for note in notes}
    assert types == {"CHALLENGE_REWARD", "BADGE_EARNED"}

    # --- açıklama katmanı canlı veriden cevaplar ---
    explain = client.post(
        "/explain", json={"question": "Kaç puanım var?"}, headers=veli
    ).json()
    assert explain["evidence"]["total_points"] == 800
    assert "800" in explain["answer"]

    # --- gün sonu batch mühürler: hiçbir şeyi değiştirmez ---
    admin = client.post(
        "/auth/login", json={"username": "boss", "password": "admin-parola-1"}
    ).json()
    admin_headers = {"Authorization": f"Bearer {admin['access_token']}"}
    batch = client.post(
        "/admin/batch-run", json={}, headers=admin_headers
    ).json()
    assert batch["new_rewards"] == 0
    assert batch["new_badges"] == 0

    after = client.get("/leaderboard", headers=veli).json()
    assert after == board

    # --- puan geçmişi append-only ve tutarlı ---
    points = client.get("/me/points", headers=veli).json()
    assert points["total_points"] == 800
    assert len(points["entries"]) == 1
    assert points["entries"][0]["source"] == "CHALLENGE_COMPLETED"
