"""
Thread-safe in-memory notification queue.
Her kullanıcı için bekleyen bildirimleri tutar.
SSE endpoint pop eder, watch/pipeline push eder.
"""

import threading
from typing import Any

_store: dict[str, list[dict[str, Any]]] = {}
_lock  = threading.Lock()


def push_notification(user_id: str, data: dict[str, Any]) -> None:
    """Kullanıcının kuyruğuna bildirim ekle."""
    with _lock:
        if user_id not in _store:
            _store[user_id] = []
        _store[user_id].append(data)


def pop_notifications(user_id: str) -> list[dict[str, Any]]:
    """Kuyruktaki tüm bildirimleri al ve temizle."""
    with _lock:
        return _store.pop(user_id, [])


def peek_count(user_id: str) -> int:
    """Kuyruktaki bildirim sayısını döner (silmez)."""
    with _lock:
        return len(_store.get(user_id, []))
