"""
Public Platform İstatistikleri — Sprint 23.
Landing/login sayfası vitrini için auth GEREKTİRMEYEN gerçek sayılar.
Kişisel veri içermez — yalnızca toplam agregalar.
"""

from fastapi import APIRouter
from database.setup import get_db

router = APIRouter(tags=["Public"])


@router.get("/public")
def public_stats():
    db = get_db()
    row = db.execute("""
        SELECT
          (SELECT COUNT(*) FROM users)                              AS users,
          (SELECT COUNT(*) FROM content_catalog)                    AS videos,
          (SELECT COALESCE(SUM(points),0) FROM points_ledger)       AS total_points,
          (SELECT COALESCE(SUM(watch_minutes),0) FROM user_activities) AS watch_minutes,
          (SELECT COUNT(*) FROM user_badges)                        AS badges,
          (SELECT COUNT(*) FROM user_achievements)                  AS achievements
    """).fetchone()
    db.close()
    return {
        "users":         int(row["users"]),
        "videos":        int(row["videos"]),
        "total_points":  int(row["total_points"]),
        "watch_minutes": round(float(row["watch_minutes"]), 0),
        "badges":        int(row["badges"]),
        "achievements":  int(row["achievements"]),
    }
