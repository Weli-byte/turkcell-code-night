"""Application factory and health endpoint tests."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select

from gamification_backend.config import BackendSettings
from gamification_backend.db.models import ChallengeRecord
from gamification_backend.main import create_app


def test_health_endpoint_reports_ok(test_settings: BackendSettings) -> None:
    app = create_app(test_settings)

    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


def test_startup_seeds_challenges(test_settings: BackendSettings) -> None:
    app = create_app(test_settings)

    with TestClient(app):
        with app.state.session_factory() as session:
            rows = list(session.execute(select(ChallengeRecord)).scalars())

    assert len(rows) == 6
    assert {row.challenge_id for row in rows} == {
        "CH-001",
        "CH-002",
        "CH-003",
        "CH-004",
        "CH-005",
        "CH-006",
    }


def test_seed_can_be_disabled(test_settings: BackendSettings) -> None:
    settings = test_settings.model_copy(update={"seed_on_startup": False})
    app = create_app(settings)

    with TestClient(app):
        with app.state.session_factory() as session:
            rows = list(session.execute(select(ChallengeRecord)).scalars())

    assert rows == []


def test_cors_preflight_allows_frontend_origin(
    test_settings: BackendSettings,
) -> None:
    app = create_app(test_settings)

    with TestClient(app) as client:
        response = client.options(
            "/health",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_cors_settings_parse_list() -> None:
    settings = BackendSettings(cors_origins=" http://a.dev , http://b.dev ,")

    assert settings.cors_origin_list() == ["http://a.dev", "http://b.dev"]


def test_unknown_route_returns_404(test_settings: BackendSettings) -> None:
    app = create_app(test_settings)

    with TestClient(app) as client:
        response = client.get("/nope")

    assert response.status_code == 404
