"""Tests for the live leaderboard endpoint."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from gamification_backend.config import BackendSettings
from gamification_backend.db.models import BadgeRecord, UserRecord
from gamification_backend.main import create_app
from gamification_backend.repositories.ledger import AppendOnlyLedgerRepository


@pytest.fixture()
def client_headers(
    test_settings: BackendSettings,
) -> Iterator[tuple[TestClient, dict[str, str]]]:
    app = create_app(test_settings)
    with TestClient(app) as client:
        token = client.post(
            "/auth/register",
            json={"username": "izleyici", "password": "cok-gizli-parola"},
        ).json()["access_token"]
        yield client, {"Authorization": f"Bearer {token}"}


def _factory(client: TestClient) -> sessionmaker[Session]:
    factory: sessionmaker[Session] = client.app.state.session_factory  # type: ignore[attr-defined]
    return factory


def _add_scored_user(
    client: TestClient,
    user_id: str,
    points: int,
    *,
    is_bot: bool = False,
    badge: str | None = None,
) -> None:
    with _factory(client)() as session:
        session.add(UserRecord(id=user_id, username=user_id, is_bot=is_bot))
        session.commit()
        AppendOnlyLedgerRepository(session).append(
            ledger_id=f"L-{user_id}",
            user_id=user_id,
            points_delta=points,
            source="CHALLENGE_COMPLETED",
            source_ref=f"seed:{user_id}",
            created_at=datetime(2026, 7, 4, tzinfo=UTC),
        )
        if badge is not None:
            session.add(
                BadgeRecord(
                    user_id=user_id,
                    badge_type=badge,
                    awarded_at=date(2026, 7, 4),
                )
            )
            session.commit()


def test_leaderboard_requires_auth(
    client_headers: tuple[TestClient, dict[str, str]],
) -> None:
    client, _ = client_headers

    assert client.get("/leaderboard").status_code == 401


def test_ranking_order_and_tiebreak(
    client_headers: tuple[TestClient, dict[str, str]],
) -> None:
    client, headers = client_headers
    _add_scored_user(client, "cansu", 100)
    _add_scored_user(client, "berk", 200, badge="BRONZE")
    _add_scored_user(client, "ali", 100)

    body = client.get("/leaderboard", headers=headers).json()

    assert [(row["rank"], row["username"], row["total_points"]) for row in body] == [
        (1, "berk", 200),
        (2, "ali", 100),
        (3, "cansu", 100),
    ]
    assert body[0]["badges"] == ["BRONZE"]


def test_users_without_points_are_excluded(
    client_headers: tuple[TestClient, dict[str, str]],
) -> None:
    client, headers = client_headers
    _add_scored_user(client, "puanli", 50)

    body = client.get("/leaderboard", headers=headers).json()

    usernames = [row["username"] for row in body]
    assert usernames == ["puanli"]
    assert "izleyici" not in usernames  # registered user has no points yet


def test_limit_parameter(
    client_headers: tuple[TestClient, dict[str, str]],
) -> None:
    client, headers = client_headers
    for index in range(5):
        _add_scored_user(client, f"u{index}", 100 * (index + 1))

    body = client.get("/leaderboard", params={"limit": 2}, headers=headers).json()

    assert len(body) == 2
    assert body[0]["username"] == "u4"


def test_bots_are_flagged(
    client_headers: tuple[TestClient, dict[str, str]],
) -> None:
    client, headers = client_headers
    _add_scored_user(client, "bot-1", 300, is_bot=True)

    body = client.get("/leaderboard", headers=headers).json()

    assert body[0]["is_bot"] is True
