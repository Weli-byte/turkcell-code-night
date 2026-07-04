"""Tests for the notification broker and the SSE endpoint's auth."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from gamification_backend.config import BackendSettings
from gamification_backend.main import create_app
from gamification_backend.services.notifier import NotificationBroker, format_sse


def test_publish_reaches_only_matching_user() -> None:
    broker = NotificationBroker()
    _, veli_queue = broker.subscribe("veli")
    _, ayse_queue = broker.subscribe("ayse")

    delivered = broker.publish("veli", {"message": "merhaba"})

    assert delivered == 1
    assert veli_queue.get_nowait() == {"message": "merhaba"}
    assert ayse_queue.empty()


def test_multiple_subscribers_all_receive() -> None:
    broker = NotificationBroker()
    _, first = broker.subscribe("veli")
    _, second = broker.subscribe("veli")

    delivered = broker.publish("veli", {"n": 1})

    assert delivered == 2
    assert first.get_nowait() == {"n": 1}
    assert second.get_nowait() == {"n": 1}


def test_unsubscribe_stops_delivery() -> None:
    broker = NotificationBroker()
    subscription_id, queue = broker.subscribe("veli")
    broker.unsubscribe(subscription_id)
    broker.unsubscribe(subscription_id)  # idempotent

    assert broker.publish("veli", {"n": 1}) == 0
    assert queue.empty()


def test_format_sse_shape() -> None:
    chunk = format_sse({"message": "🏆 rozet", "type": "BADGE_EARNED"})

    assert chunk.startswith("event: notification\ndata: ")
    assert chunk.endswith("\n\n")
    assert "🏆 rozet" in chunk


@pytest.fixture()
def client(test_settings: BackendSettings) -> Iterator[TestClient]:
    app = create_app(test_settings)
    with TestClient(app) as client:
        yield client


def test_sse_rejects_invalid_token(client: TestClient) -> None:
    response = client.get("/sse/notifications", params={"token": "bozuk"})

    assert response.status_code == 401


def test_sse_requires_token_param(client: TestClient) -> None:
    response = client.get("/sse/notifications")

    assert response.status_code == 422
