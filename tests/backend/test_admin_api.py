"""Tests for the admin panel API (challenges, users, simulator)."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from gamification_backend.config import BackendSettings
from gamification_backend.main import create_app
from gamification_backend.services.condition_validation import (
    allowed_condition_fields,
    validate_condition,
)

NEW_CHALLENGE = {
    "challenge_id": "CH-100",
    "name": "Tur Kasifi",
    "challenge_type": "DAILY",
    "condition": "unique_genres_today >= 3",
    "reward_points": 250,
    "priority": 7,
    "is_active": True,
}


@pytest.fixture()
def admin_client(
    challenges_csv: object,
) -> Iterator[tuple[TestClient, dict[str, str], dict[str, str]]]:
    """Client + admin headers + regular-user headers."""

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
    with TestClient(app) as client:
        admin_token = client.post(
            "/auth/login",
            json={"username": "boss", "password": "admin-parola-1"},
        ).json()["access_token"]
        user_token = client.post(
            "/auth/register",
            json={"username": "veli", "password": "cok-gizli-parola"},
        ).json()["access_token"]
        yield (
            client,
            {"Authorization": f"Bearer {admin_token}"},
            {"Authorization": f"Bearer {user_token}"},
        )


def test_validate_condition_helper() -> None:
    assert validate_condition("watch_minutes_today >= 60") is None
    assert validate_condition("__import__('os')") is not None
    assert validate_condition("bilinmeyen_alan >= 1") is not None
    assert validate_condition("watch_minutes_today >= abc") is not None
    assert "watch_streak_days" in allowed_condition_fields()


def test_list_challenges_includes_inactive(
    admin_client: tuple[TestClient, dict[str, str], dict[str, str]],
) -> None:
    client, admin, _ = admin_client

    body = client.get("/admin/challenges", headers=admin).json()

    assert len(body) == 6
    inactive = [row for row in body if not row["is_active"]]
    assert [row["challenge_id"] for row in inactive] == ["CH-006"]


def test_admin_endpoints_forbidden_for_regular_users(
    admin_client: tuple[TestClient, dict[str, str], dict[str, str]],
) -> None:
    client, _, user = admin_client

    for method, path in (
        ("GET", "/admin/challenges"),
        ("POST", "/admin/challenges"),
        ("GET", "/admin/users"),
        ("GET", "/admin/simulator"),
    ):
        response = client.request(method, path, headers=user, json=NEW_CHALLENGE)
        assert response.status_code == 403, path


def test_create_challenge(
    admin_client: tuple[TestClient, dict[str, str], dict[str, str]],
) -> None:
    client, admin, _ = admin_client

    response = client.post("/admin/challenges", json=NEW_CHALLENGE, headers=admin)

    assert response.status_code == 201
    assert response.json()["challenge_id"] == "CH-100"
    listed = client.get("/admin/challenges", headers=admin).json()
    assert any(row["challenge_id"] == "CH-100" for row in listed)


def test_create_challenge_duplicate_conflicts(
    admin_client: tuple[TestClient, dict[str, str], dict[str, str]],
) -> None:
    client, admin, _ = admin_client
    client.post("/admin/challenges", json=NEW_CHALLENGE, headers=admin)

    response = client.post("/admin/challenges", json=NEW_CHALLENGE, headers=admin)

    assert response.status_code == 409


def test_create_challenge_rejects_unsafe_condition(
    admin_client: tuple[TestClient, dict[str, str], dict[str, str]],
) -> None:
    client, admin, _ = admin_client

    for condition in (
        "__import__('os').system('x')",
        "bilinmeyen_alan >= 5",
        "watch_minutes_today >= watch_minutes_7d",
    ):
        body = {**NEW_CHALLENGE, "condition": condition}
        response = client.post("/admin/challenges", json=body, headers=admin)
        assert response.status_code == 422, condition
        assert "Geçersiz koşul" in response.json()["detail"]


def test_create_challenge_rejects_non_positive_points(
    admin_client: tuple[TestClient, dict[str, str], dict[str, str]],
) -> None:
    client, admin, _ = admin_client

    body = {**NEW_CHALLENGE, "reward_points": 0}
    response = client.post("/admin/challenges", json=body, headers=admin)

    assert response.status_code == 422


def test_update_challenge_partial(
    admin_client: tuple[TestClient, dict[str, str], dict[str, str]],
) -> None:
    client, admin, _ = admin_client

    response = client.put(
        "/admin/challenges/CH-001",
        json={"reward_points": 120, "is_active": False},
        headers=admin,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["reward_points"] == 120
    assert body["is_active"] is False
    assert body["condition"] == "watch_minutes_today >= 60"  # unchanged


def test_update_challenge_validates_condition(
    admin_client: tuple[TestClient, dict[str, str], dict[str, str]],
) -> None:
    client, admin, _ = admin_client

    response = client.put(
        "/admin/challenges/CH-001",
        json={"condition": "hack >= 1"},
        headers=admin,
    )

    assert response.status_code == 422


def test_update_unknown_challenge_404(
    admin_client: tuple[TestClient, dict[str, str], dict[str, str]],
) -> None:
    client, admin, _ = admin_client

    response = client.put("/admin/challenges/CH-YOK", json={"name": "x"}, headers=admin)

    assert response.status_code == 404


def test_deactivated_challenge_leaves_user_view(
    admin_client: tuple[TestClient, dict[str, str], dict[str, str]],
) -> None:
    client, admin, user = admin_client
    client.put("/admin/challenges/CH-001", json={"is_active": False}, headers=admin)

    challenges = client.get("/me/challenges", headers=user).json()

    assert all(row["challenge_id"] != "CH-001" for row in challenges)


def test_list_users_with_totals(
    admin_client: tuple[TestClient, dict[str, str], dict[str, str]],
) -> None:
    client, admin, _ = admin_client

    body = client.get("/admin/users", headers=admin).json()

    usernames = [row["username"] for row in body]
    assert usernames == sorted(usernames)
    assert {"boss", "veli"}.issubset(set(usernames))
    boss = next(row for row in body if row["username"] == "boss")
    assert boss["is_admin"] is True
    assert boss["total_points"] == 0


def test_simulator_status_skeleton(
    admin_client: tuple[TestClient, dict[str, str], dict[str, str]],
) -> None:
    client, admin, _ = admin_client

    body = client.get("/admin/simulator", headers=admin).json()

    assert body["running"] is False
    assert body["bot_count"] == 0
