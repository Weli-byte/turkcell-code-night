"""
engine/event_bus.py — Basit event bus (hackathon: senkron dispatch, thread-safe kayit).

Her kullanici aksiyonu event olarak yayinlanir (or. video_ended). Aboneler sirayla
cagrilir; bir abonenin hatasi digerlerini engellemez.
"""

import threading
from datetime import datetime

_lock = threading.Lock()
_subscribers = {}   # event_name -> [handler, ...]
_event_log = []     # son olaylar (in-memory audit)

MAX_LOG = 200


def subscribe(event_name: str, handler) -> None:
    """Bir event'e handler kaydeder."""
    with _lock:
        _subscribers.setdefault(event_name, []).append(handler)


def publish(event_name: str, payload: dict) -> int:
    """
    Event yayinlar; kayitli handler'lari cagirir.
    Doner: cagrilan handler sayisi.
    """
    with _lock:
        handlers = list(_subscribers.get(event_name, []))
        _event_log.append({
            "event": event_name,
            "payload": payload,
            "at": datetime.now().isoformat(),
        })
        if len(_event_log) > MAX_LOG:
            del _event_log[: len(_event_log) - MAX_LOG]

    called = 0
    for h in handlers:
        try:
            h(payload)
            called += 1
        except Exception as e:
            print(f"[event_bus] handler hatasi ({event_name}):", e)
    return called


def recent_events(n: int = 20) -> list:
    """Son n event (audit/gozlem icin)."""
    with _lock:
        return list(_event_log[-n:])
