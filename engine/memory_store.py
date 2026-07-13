"""
engine/memory_store.py — Kullanici AI hafizasi (short-term + long-term).

Kalici katman ai_memory tablosunda tutulur (key-value, JSON deger). ai_memory mutable
oldugu icin guncelleme serbesttir (append-only olan points_ledger degildir).
Rastgelelik yok; cikarimlar gercek DB aktivitelerinden.
"""

import json
from datetime import datetime

from database.setup import get_db

WEEKDAYS = ["pazartesi", "sali", "carsamba", "persembe", "cuma", "cumartesi", "pazar"]


def get(user_id: str) -> dict:
    """ai_memory'den kullanicinin tum hafizasini dict olarak dondurur. Yoksa {}."""
    db = get_db()
    try:
        rows = db.execute(
            "SELECT key, value FROM ai_memory WHERE user_id=? ORDER BY updated_at, id",
            (user_id,),
        ).fetchall()
        memory = {}
        for r in rows:
            raw = r["value"]
            try:
                memory[r["key"]] = json.loads(raw) if raw is not None else None
            except (json.JSONDecodeError, TypeError):
                memory[r["key"]] = raw
        return memory
    finally:
        db.close()


def update(user_id: str, key: str, value) -> bool:
    """
    Bir hafiza anahtarini yazar. UNIQUE(user_id,key) + ON CONFLICT DO UPDATE ile upsert.
    ai_memory mutable oldugu icin bu serbesttir (points_ledger degildir).
    """
    db = get_db()
    try:
        db.execute(
            """
            INSERT INTO ai_memory (user_id, key, value, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id, key) DO UPDATE SET
                value = excluded.value,
                updated_at = excluded.updated_at
            """,
            (user_id, key, json.dumps(value, ensure_ascii=False), datetime.now().isoformat()),
        )
        db.commit()
        return True
    except Exception as e:
        print("[memory_store] update hatasi:", e)
        return False
    finally:
        db.close()


def update_batch(user_id: str, updates: dict) -> bool:
    """Birden fazla key-value'yu gunceller. Hepsi basariliysa True."""
    ok = True
    for key, value in updates.items():
        if not update(user_id, key, value):
            ok = False
    return ok


def _append_unique(user_id: str, key: str, suggestion: str) -> bool:
    """Bir liste-hafiza alanina tekrarsiz ekleme yardimcisi."""
    memory = get(user_id)
    current = memory.get(key, [])
    if not isinstance(current, list):
        current = []
    if suggestion not in current:
        current.append(suggestion)
    return update(user_id, key, current)


def add_rejected_suggestion(user_id: str, suggestion: str) -> bool:
    """Reddedilen oneriyi listeye ekler (tekrarsiz)."""
    return _append_unique(user_id, "rejected_suggestions", suggestion)


def add_accepted_suggestion(user_id: str, suggestion: str) -> bool:
    """Begenilen oneriyi listeye ekler (tekrarsiz)."""
    return _append_unique(user_id, "accepted_suggestions", suggestion)


def infer_and_update(user_id: str) -> dict:
    """
    Kullanicinin gercek DB aktivitelerinden hafiza cikarir ve gunceller.
    - En cok izlenen genre (watch_sessions JOIN content_catalog)
    - En aktif saat araligi (watch_sessions.started_at)
    - En aktif gunler (user_activities.activity_date)
    Doner: guncellenen alanlar dict.
    """
    db = get_db()
    inferred = {}
    try:
        # En cok izlenen genre (izleme dakikasina gore)
        genre_rows = db.execute(
            """
            SELECT cc.genre AS genre, COALESCE(SUM(ws.watch_minutes),0) AS mins
            FROM watch_sessions ws
            JOIN content_catalog cc ON cc.id = ws.content_id
            WHERE cc.genre IS NOT NULL
            GROUP BY cc.genre
            ORDER BY mins DESC, cc.genre ASC
            """,
        ).fetchall()
        genres = [r["genre"] for r in genre_rows if float(r["mins"]) > 0]
        if genres:
            inferred["genre_preferences"] = genres

        # En aktif saat araligi (session baslangic saatleri)
        hour_rows = db.execute(
            "SELECT started_at FROM watch_sessions WHERE user_id=?",
            (user_id,),
        ).fetchall()
        hours = {}
        for r in hour_rows:
            try:
                h = datetime.fromisoformat(r["started_at"]).hour
                hours[h] = hours.get(h, 0) + 1
            except (ValueError, TypeError):
                continue
        if hours:
            top_hours = sorted(hours.items(), key=lambda kv: (-kv[1], kv[0]))
            inferred["watch_hours"] = [h for h, _ in top_hours[:3]]

        # En aktif gunler (gercek izleme olan gunler)
        day_rows = db.execute(
            "SELECT DISTINCT activity_date FROM user_activities "
            "WHERE user_id=? AND watch_minutes > 0",
            (user_id,),
        ).fetchall()
        day_names = []
        for r in day_rows:
            try:
                wd = datetime.strptime(r["activity_date"], "%Y-%m-%d").weekday()
                name = WEEKDAYS[wd]
                if name not in day_names:
                    day_names.append(name)
            except (ValueError, TypeError):
                continue
        if day_names:
            inferred["active_days"] = day_names
    finally:
        db.close()

    if inferred:
        update_batch(user_id, inferred)
    return inferred
