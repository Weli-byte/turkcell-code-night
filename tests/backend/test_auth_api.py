"""End-to-end tests for register/login/me/admin endpoints."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from gamification_backend.config import BackendSettings
from gamification_backend.main import create_app

REGISTER = {"username": "veli", "password": "cok-gizli-parola"}


@pytest.fixture()
def client(test_settings: BackendSettings) -> Iterator[TestClient]:
    """Test client over a fresh in-memory app (lifespan active)."""

    app = create_app(test_settings)
    with TestClient(app) as client:
        yield client


@pytest.fixture()
def admin_client() -> Iterator[TestClient]:
    """Client for an app bootstrapped with an admin account."""

    settings = BackendSettings(
        database_url="sqlite://",
        seed_on_startup=False,
        jwt_secret="test-secret",  # noqa: S106
        bcrypt_rounds=4,
        admin_username="boss",
        admin_password="admin-parola-1",  # noqa: S106
    )
    app = create_app(settings)
    with TestClient(app) as client:
        yield client


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_register_returns_token_and_user(client: TestClient) -> None:
    response = client.post("/auth/register", json=REGISTER)

    assert response.status_code == 201
    body = response.json()
    assert body["token_type"] == "bearer"  # noqa: S105
    assert body["user"]["username"] == "veli"
    assert body["user"]["is_admin"] is False
    assert "password" not in body["user"]
    assert "password_hash" not in body["user"]


def test_register_duplicate_username_conflicts(client: TestClient) -> None:
    client.post("/auth/register", json=REGISTER)

    response = client.post("/auth/register", json=REGISTER)

    assert response.status_code == 409


def test_register_short_password_rejected(client: TestClient) -> None:
    response = client.post(
        "/auth/register", json={"username": "veli", "password": "kisa"}
    )

    assert response.status_code == 422


def test_register_invalid_username_rejected(client: TestClient) -> None:
    response = client.post(
        "/auth/register",
        json={"username": "veli parlak!", "password": "cok-gizli-parola"},
    )

    assert response.status_code == 422


def test_login_with_valid_credentials(client: TestClient) -> None:
    client.post("/auth/register", json=REGISTER)

    response = client.post("/auth/login", json=REGISTER)

    assert response.status_code == 200
    assert response.json()["user"]["username"] == "veli"


def test_login_wrong_password_unauthorized(client: TestClient) -> None:
    client.post("/auth/register", json=REGISTER)

    response = client.post(
        "/auth/login", json={"username": "veli", "password": "yanlis-parola"}
    )

    assert response.status_code == 401


def test_login_unknown_user_unauthorized(client: TestClient) -> None:
    response = client.post("/auth/login", json=REGISTER)

    assert response.status_code == 401


def test_me_returns_profile(client: TestClient) -> None:
    token = client.post("/auth/register", json=REGISTER).json()["access_token"]

    response = client.get("/me", headers=_auth_header(token))

    assert response.status_code == 200
    assert response.json()["username"] == "veli"


def test_me_without_token_unauthorized(client: TestClient) -> None:
    response = client.get("/me")

    assert response.status_code == 401


def test_me_with_invalid_token_unauthorized(client: TestClient) -> None:
    response = client.get("/me", headers=_auth_header("bozuk-token"))

    assert response.status_code == 401


def test_admin_ping_forbidden_for_regular_user(client: TestClient) -> None:
    token = client.post("/auth/register", json=REGISTER).json()["access_token"]

    response = client.get("/admin/ping", headers=_auth_header(token))

    assert response.status_code == 403


def test_admin_bootstrap_and_ping(admin_client: TestClient) -> None:
    login = admin_client.post(
        "/auth/login", json={"username": "boss", "password": "admin-parola-1"}
    )
    assert login.status_code == 200
    assert login.json()["user"]["is_admin"] is True

    response = admin_client.get(
        "/admin/ping", headers=_auth_header(login.json()["access_token"])
    )

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "admin": "boss"}
