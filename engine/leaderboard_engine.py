"""
Deterministik leaderboard engine.
Sıralama kuralı:
  1. Toplam puan DESC (yüksekten düşüğe)
  2. Eşit puanda: user_id ASC (alfabetik)
random kullanılmaz, her çalışmada aynı sonuç üretilir.
"""

from database.setup import get_db


def get_leaderboard(limit: int = 100) -> list:
    """
    Tüm kullanıcıları deterministik kuralla sıralar.
    Eşit puanda user_id alfabetik — random yok.
    """
    db = get_db()
    rows = db.execute("""
        SELECT
            u.id,
            u.username,
            COALESCE(SUM(pl.points), 0) AS total_points,
            GROUP_CONCAT(ub.badge_tier, ',') AS badges_raw
        FROM users u
        LEFT JOIN points_ledger pl ON pl.user_id = u.id
        LEFT JOIN user_badges ub ON ub.user_id = u.id
        GROUP BY u.id, u.username
        ORDER BY total_points DESC, u.id ASC
        LIMIT ?
    """, (limit,)).fetchall()
    db.close()

    result = []
    for i, row in enumerate(rows):
        badges = []
        if row["badges_raw"]:
            seen = set()
            for b in row["badges_raw"].split(","):
                if b and b not in seen:
                    badges.append(b)
                    seen.add(b)
        result.append({
            "rank":         i + 1,
            "user_id":      row["id"],
            "username":     row["username"],
            "total_points": int(row["total_points"]),
            "badges":       badges,
        })
    return result
