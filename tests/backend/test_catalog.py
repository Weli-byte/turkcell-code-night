"""Tests for catalog seeding and catalog endpoints."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from gamification_backend.config import BackendSettings
from gamification_backend.main import create_app
from gamification_backend.repositories.catalog import seed_catalog_from_json

_REPO_ROOT = Path(__file__).resolve().parents[2]
CATALOG_JSON = _REPO_ROOT / "data" / "input" / "catalog.json"


@pytest.fixture()
def client(test_settings: BackendSettings) -> Iterator[TestClient]:
    app = create_app(test_settings)
    with TestClient(app) as client:
        yield client


def test_seed_inserts_series_and_videos(session: Session) -> None:
    series, videos = seed_catalog_from_json(session, CATALOG_JSON)

    assert series == 2
    assert videos == 12


def test_seed_is_idempotent(session: Session) -> None:
    seed_catalog_from_json(session, CATALOG_JSON)

    assert seed_catalog_from_json(session, CATALOG_JSON) == (0, 0)


def test_catalog_endpoint_structure(client: TestClient) -> None:
    response = client.get("/catalog")

    assert response.status_code == 200
    body = response.json()
    assert [s["id"] for s in body["series"]] == ["S-001", "S-002"]
    assert [f["id"] for f in body["films"]] == ["V-BBB", "V-ED", "V-SIN", "V-TOS"]


def test_catalog_episodes_in_watch_order(client: TestClient) -> None:
    body = client.get("/catalog").json()

    first_series = body["series"][0]
    assert [e["episode_number"] for e in first_series["episodes"]] == [1, 2, 3, 4, 5]
    assert all(e["series_id"] == "S-001" for e in first_series["episodes"])


def test_video_detail(client: TestClient) -> None:
    response = client.get("/catalog/videos/V-BBB")

    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "Big Buck Bunny"
    assert body["genre"] == "animasyon"
    assert body["duration_seconds"] == 596
    assert body["url"].startswith("https://")


def test_video_detail_unknown_returns_404(client: TestClient) -> None:
    response = client.get("/catalog/videos/V-YOK")

    assert response.status_code == 404
