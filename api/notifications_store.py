"""
Bildirim mağazası — Sprint 16'da kalıcı hale getirildi.

push_notification iki iş yapar:
1. Thread-safe in-memory kuyruğa ekler → SSE anlık iletir (mevcut davranış).
2. notifications tablosuna kalıcı yazar → bildirim merkezi, okundu yönetimi.

Böylece kullanıcı çevrimdışıyken üretilen bildirimler kaybolmaz.
"""

import json
import threading
from datetime import datetime
from typing import Any

from database.setup import get_db

_store: dict[str, list[dict[str, Any]]] = {}
_lock  = threading.Lock()

# type → kalıcı kayıt için başlık üretimi (gerçek payload'dan)
def _derive_title_message(data: dict[str, Any]) -> tuple[str, str]:
    t = data.get("type", "info")
    if t == "points":
        return ("Puan Kazandın",
                f"{data.get('reason', 'Görev tamamlandı')} (+{data.get('points', 0)} puan)")
    if t == "badge":
        return ("Yeni Rozet", str(data.get("badge", "")))
    if t == "challenge":
        return (str(data.get("challenge_name", "Görev tamamlandı")),
                str(data.get("message", "")))
    if t == "party":
        return ("Watch Party", str(data.get("message", "")))
    if t == "level":
        return ("Seviye Atladın!", str(data.get("message", "")))
    return ("Bildirim", str(data.get("message", "")))


def push_notification(user_id: str, data: dict[str, Any]) -> None:
    """Kuyruğa (SSE) + DB'ye (kalıcı) bildirim ekle."""
    with _lock:
        if user_id not in _store:
            _store[user_id] = []
        _store[user_id].append(data)

    # Kalıcı kayıt — SSE'den bağımsız; hata SSE akışını bozmasın
    try:
        title, message = _derive_title_message(data)
        db = get_db()
        db.execute(
            "INSERT INTO notifications (user_id, type, title, message, payload, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, data.get("type", "info"), title, message,
             json.dumps(data, ensure_ascii=False), datetime.now().isoformat()),
        )
        db.commit()
        db.close()
    except Exception:
        pass


def pop_notifications(user_id: str) -> list[dict[str, Any]]:
    """Kuyruktaki tüm bildirimleri al ve temizle."""
    with _lock:
        return _store.pop(user_id, [])


def peek_count(user_id: str) -> int:
    """Kuyruktaki bildirim sayısını döner (silmez)."""
    with _lock:
        return len(_store.get(user_id, []))
