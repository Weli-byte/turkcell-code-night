"""
Global Arama — Sprint 23.
Tek sorguda videolar + kullanıcılar (Ctrl+K komut paleti).
Tüm sonuçlar gerçek DB'den; videolar izlenmeye, kullanıcılar puana göre sıralı.
"""

from fastapi import APIRouter, Depends, Query
from api.auth_utils import verify_token
from database.setup import get_db
from engine.level_engine import get_level

router = APIRouter(tags=["Search"])


@router.get("/ai")
def ai_natural_search(
    q: str = Query(..., min_length=3, max_length=120),
    token: dict = Depends(verify_token),
):
    """Doğal dil araması (Sprint 25) — GPT-4o sorguyu filtreye çevirir,
    sonuçlar gerçek parametreli SQL'den gelir."""
    from engine.nl_search_engine import nl_search
    return nl_search(q, token["sub"])


@router.get("")
def global_search(
    q: str = Query(..., min_length=1, max_length=60),
    token: dict = Depends(verify_token),
):
    term = f"%{q.strip()}%"
    db   = get_db()

    videos = db.execute("""
        SELECT cc.id, cc.title, cc.genre, cc.duration_minutes, cc.thumbnail_color,
               (SELECT COUNT(*) FROM watch_sessions ws
                WHERE ws.content_id=cc.id AND ws.ended_at IS NOT NULL) AS watches,
               (SELECT COALESCE(AVG(rating),0) FROM content_ratings cr
                WHERE cr.content_id=cc.id) AS avg_rating
        FROM content_catalog cc
        WHERE cc.title LIKE ? OR cc.genre LIKE ?
        ORDER BY watches DESC, cc.title ASC
        LIMIT 6
    """, (term, term)).fetchall()

    users = db.execute("""
        SELECT u.id, u.username,
               COALESCE((SELECT SUM(points) FROM points_ledger
                         WHERE user_id=u.id), 0) AS total_points
        FROM users u
        WHERE u.username LIKE ?
        ORDER BY total_points DESC, u.username ASC
        LIMIT 5
    """, (term,)).fetchall()

    db.close()

    return {
        "query": q,
        "videos": [
            {
                "id": v["id"], "title": v["title"], "genre": v["genre"],
                "duration_minutes": v["duration_minutes"],
                "thumbnail_color": v["thumbnail_color"],
                "watches": int(v["watches"]),
                "avg_rating": round(float(v["avg_rating"]), 1),
            }
            for v in videos
        ],
        "users": [
            {
                "username": u["username"],
                "total_points": int(u["total_points"]),
                "level": get_level(int(u["total_points"]))["level"],
                "is_me": u["id"] == token["sub"],
            }
            for u in users
        ],
    }
