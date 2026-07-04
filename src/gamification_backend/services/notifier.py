"""In-process notification broker for SSE fan-out.

Publishers (event endpoints, running in the request thread pool) push
payloads; each connected SSE client owns a thread-safe queue. Single-process
by design — a multi-worker deployment would swap this for Redis pub/sub
(noted in docs/backlog.md).
"""

from __future__ import annotations

import json
import threading
from collections.abc import Mapping
from queue import SimpleQueue
from typing import Any

Payload = dict[str, Any]


class NotificationBroker:
    """Thread-safe per-user publish/subscribe queues."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._next_id = 1
        self._subscribers: dict[int, tuple[str, SimpleQueue[Payload]]] = {}

    def subscribe(self, user_id: str) -> tuple[int, SimpleQueue[Payload]]:
        """Register a listener; returns its id and message queue."""

        queue: SimpleQueue[Payload] = SimpleQueue()
        with self._lock:
            subscription_id = self._next_id
            self._next_id += 1
            self._subscribers[subscription_id] = (user_id, queue)
        return subscription_id, queue

    def unsubscribe(self, subscription_id: int) -> None:
        """Remove a listener; unknown ids are ignored."""

        with self._lock:
            self._subscribers.pop(subscription_id, None)

    def publish(self, user_id: str, payload: Payload) -> int:
        """Deliver a payload to the user's listeners; returns the count."""

        with self._lock:
            queues = [
                queue
                for subscriber, queue in self._subscribers.values()
                if subscriber == user_id
            ]
        for queue in queues:
            queue.put(payload)
        return len(queues)


def format_sse(payload: Mapping[str, Any]) -> str:
    """Encode a payload as one SSE ``notification`` event."""

    data = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return f"event: notification\ndata: {data}\n\n"
