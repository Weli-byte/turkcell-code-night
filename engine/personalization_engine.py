"""
engine/personalization_engine.py — Icerik/onerileri kullanici profiline gore
yeniden siralar. Tum skorlar gercek DB + hafiza verisinden deterministik.
"""

from datetime import datetime, timedelta

from database.setup import get_db
from engine.memory_store import get as mem_get
from engine.state_builder import build_user_state

DATE_FMT = "%Y-%m-%d"

YORGUNLUK_ESIGI_DK = 120   # bugun bu kadar izlediyse kisa videolara -1
YUKSEK_ODUL_ESIGI = 150    # competitive kullanici icin +2 esigi


def _today() -> str:
    return datetime.now().strftime(DATE_FMT)


def _watched_ids(user_id: str) -> set:
    db = get_db()
    try:
        return {
            r["content_id"] for r in db.execute(
                "SELECT DISTINCT content_id FROM watch_sessions "
                "WHERE user_id=? AND watch_minutes > 0",
                (user_id,),
            ).fetchall()
        }
    finally:
        db.close()


def personalize_content(user_id: str, items: list) -> list:
    """
    Herhangi bir item listesini profile gore yeniden siralar.
    Video: tur tercihi +3, yorgunlukta kisa video -1, izlenmemis +1.
    Challenge: %70-99 +3, competitive+yuksek odul +2, reddedilmis -5.
    Diger itemlar: skor 0 (orijinal sira korunur; stable sort).
    """
    memory = mem_get(user_id)
    state = build_user_state(user_id, _today())

    preferred = memory.get("genre_preferences", [])
    if not isinstance(preferred, list):
        preferred = []
    rejected = memory.get("rejected_suggestions", [])
    if not isinstance(rejected, list):
        rejected = []
    motivation = memory.get("motivation_type")

    watched = _watched_ids(user_id)
    yorgun = float(state.get("watch_minutes_today", 0)) > YORGUNLUK_ESIGI_DK

    result = []
    for orig in items:
        item = dict(orig)
        score = 0.0

        if "genre" in item and "duration_minutes" in item:
            # Video item
            if item.get("genre") in preferred:
                score += 3
            if item.get("duration_minutes", 0) < 30 and yorgun:
                score -= 1  # yorgunluk onleme
            if item.get("id") not in watched:
                score += 1
        elif "condition" in item or "percentage" in item:
            # Challenge item
            pct = int(item.get("percentage", 0) or 0)
            if 70 <= pct <= 99:
                score += 3
            if motivation == "competitive" and \
               int(item.get("reward_points", 0) or 0) >= YUKSEK_ODUL_ESIGI:
                score += 2
            if item.get("id") in rejected:
                score -= 5
        # Diger tipler: skor 0

        item["personalization_score"] = score
        result.append(item)

    # Stable sort: esit skorda orijinal sira korunur
    result.sort(key=lambda x: -x["personalization_score"])
    return result


def get_user_profile_summary(user_id: str) -> dict:
    """Kisisellestirme profil ozeti (AI ve raporlar icin). Hepsi DB+hafizadan."""
    today = _today()
    state = build_user_state(user_id, today)
    memory = mem_get(user_id)

    now = datetime.now()
    monday = (now - timedelta(days=now.weekday())).strftime(DATE_FMT)

    db = get_db()
    try:
        fav = db.execute(
            """
            SELECT cc.genre AS genre, COALESCE(SUM(ws.watch_minutes),0) AS mins
            FROM watch_sessions ws
            JOIN content_catalog cc ON cc.id = ws.content_id
            WHERE ws.user_id=? AND cc.genre IS NOT NULL
            GROUP BY cc.genre ORDER BY mins DESC, cc.genre ASC LIMIT 1
            """,
            (user_id,),
        ).fetchone()
        favorite_genre = fav["genre"] if fav and float(fav["mins"]) > 0 else None

        completed = db.execute(
            "SELECT COUNT(DISTINCT challenge_id) AS n FROM points_ledger "
            "WHERE user_id=? AND challenge_id IS NOT NULL",
            (user_id,),
        ).fetchone()["n"]
        total_ch = db.execute(
            "SELECT COUNT(*) AS n FROM challenges WHERE is_active=1"
        ).fetchone()["n"]

        active_days_week = db.execute(
            "SELECT COUNT(DISTINCT activity_date) AS n FROM user_activities "
            "WHERE user_id=? AND activity_date >= ? AND watch_minutes > 0",
            (user_id, monday),
        ).fetchone()["n"]
    finally:
        db.close()

    rate = round(int(completed) / int(total_ch), 3) if int(total_ch) > 0 else 0.0

    return {
        "user_id": user_id,
        "total_points": state["total_points"],
        "watch_minutes_7d": state["watch_minutes_7d"],
        "favorite_genre": favorite_genre,
        "challenge_success_rate": rate,
        "active_days_week": int(active_days_week),
        "motivation_type": memory.get("motivation_type"),
        "streak_days": state["streak_days"],
        "badges": state["badges"],
    }
