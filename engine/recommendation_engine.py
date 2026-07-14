"""
engine/recommendation_engine.py — Kisisel oneri motoru (gercek DB verisiyle).

2B kapsami: video / challenge / badge onerileri, kullanicinin gercek izleme
gecmisi + hafizasi + ilerlemesinden deterministik hesaplanir. Sprint 4'te
vector similarity + AI ranking ile derinlestirilecek.
"""

from datetime import datetime

from database.setup import get_db

RECOMMENDATION_TYPES = ["video", "challenge", "badge"]

DATE_FMT = "%Y-%m-%d"


def _video_recs(user_id: str, n: int) -> list:
    """Izlenmemis videolar; kullanicinin tur tercihine uyanlar one gecer."""
    from engine import memory_store

    memory = memory_store.get(user_id)
    preferred = memory.get("genre_preferences", [])
    if not isinstance(preferred, list):
        preferred = []

    db = get_db()
    try:
        rows = db.execute(
            """
            SELECT id, title, genre, content_type, duration_minutes, thumbnail_color
            FROM content_catalog
            WHERE id NOT IN (
                SELECT DISTINCT content_id FROM watch_sessions
                WHERE user_id=? AND watch_minutes > 0
            )
            ORDER BY title
            """,
            (user_id,),
        ).fetchall()
    finally:
        db.close()

    items = [dict(r) for r in rows]
    # Tercih edilen tur once (deterministik iki stabil sort)
    items.sort(key=lambda v: v["title"])
    items.sort(key=lambda v: preferred.index(v["genre"]) if v["genre"] in preferred else len(preferred))
    for v in items:
        v["reason"] = (
            f"Tur tercihine uyuyor: {v['genre']}" if v["genre"] in preferred
            else "Henuz izlemedin"
        )
    return items[:n]


def _challenge_recs(user_id: str, n: int) -> list:
    """Tamamlanmamis challenge'lar, tamamlanmaya en yakin olan once."""
    from engine.ai_challenge_engine import get_active_challenges

    active = get_active_challenges(user_id)
    incomplete = [c for c in active if c.get("percentage", 0) < 100]
    incomplete.sort(key=lambda c: c["id"])
    incomplete.sort(key=lambda c: -c.get("percentage", 0))
    return [
        {
            "id": c["id"],
            "name": c["name"],
            "condition": c["condition"],
            "reward_points": c["reward_points"],
            "percentage": c.get("percentage", 0),
            "reason": f"%{c.get('percentage', 0)} tamamlandi — bitirmeye yakinsin",
        }
        for c in incomplete[:n]
    ]


def _badge_recs(user_id: str, n: int) -> list:
    """Siradaki ulasilabilir rozet."""
    from engine.badge_engine import get_badge_progress
    from engine.ledger import get_total_points

    total = get_total_points(user_id)
    prog = get_badge_progress(user_id, total)
    if not prog["next_badge"]:
        return []
    return [{
        "badge": prog["next_badge"],
        "threshold": prog["next_threshold"],
        "points_needed": prog["points_needed"],
        "percentage": prog["percentage"],
        "reason": f"{prog['points_needed']} puan sonra {prog['next_badge']} rozet",
    }][:n]


def recommend(user_id: str, rec_type: str, n: int = 5) -> list:
    """
    Tek tip icin kisisel oneri listesi. Gecersiz tip -> ValueError.
    Tum veriler DB + hafizadan; deterministik.
    """
    if rec_type not in RECOMMENDATION_TYPES:
        raise ValueError(f"Gecersiz oneri tipi: {rec_type}")
    if rec_type == "video":
        return _video_recs(user_id, n)
    if rec_type == "challenge":
        return _challenge_recs(user_id, n)
    return _badge_recs(user_id, n)


def recommend_all(user_id: str, n: int = 5) -> dict:
    """Tum tipler icin oneriler."""
    return {t: recommend(user_id, t, n) for t in RECOMMENDATION_TYPES}
