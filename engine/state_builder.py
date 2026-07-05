"""
Kullanıcının belirli bir tarih için günlük state'ini
SADECE DB'den hesaplar. Hiçbir hardcode değer yok.
"""

from database.setup import get_db
from datetime import datetime, timedelta


def build_user_state(user_id: str, run_date: str = None) -> dict:
    if run_date is None:
        run_date = datetime.now().strftime("%Y-%m-%d")

    db = get_db()

    today = db.execute("""
        SELECT
            COALESCE(SUM(watch_minutes), 0)       AS watch_minutes,
            COALESCE(SUM(episodes_completed), 0)  AS episodes,
            COALESCE(SUM(watch_party_minutes), 0) AS party_minutes,
            COALESCE(SUM(ratings_given), 0)       AS ratings,
            COALESCE(SUM(genres_watched), 0)      AS genres
        FROM user_activities
        WHERE user_id = ? AND activity_date = ?
    """, (user_id, run_date)).fetchone()

    week_start = (
        datetime.strptime(run_date, "%Y-%m-%d") - timedelta(days=6)
    ).strftime("%Y-%m-%d")

    week = db.execute("""
        SELECT COALESCE(SUM(watch_minutes), 0) AS total
        FROM user_activities
        WHERE user_id = ?
          AND activity_date >= ?
          AND activity_date <= ?
    """, (user_id, week_start, run_date)).fetchone()

    total_pts = db.execute("""
        SELECT COALESCE(SUM(points), 0) AS total
        FROM points_ledger
        WHERE user_id = ?
    """, (user_id,)).fetchone()

    today_pts = db.execute("""
        SELECT COALESCE(SUM(points), 0) AS total
        FROM points_ledger
        WHERE user_id = ? AND activity_date = ?
    """, (user_id, run_date)).fetchone()

    badges = db.execute("""
        SELECT badge_tier
        FROM user_badges
        WHERE user_id = ?
        ORDER BY total_points_at_award ASC
    """, (user_id,)).fetchall()

    streak = _calculate_streak(db, user_id, run_date)

    db.close()

    return {
        "user_id":                    user_id,
        "run_date":                   run_date,
        "watch_minutes_today":        float(today["watch_minutes"]),
        "episodes_completed_today":   int(today["episodes"]),
        "watch_party_minutes_today":  float(today["party_minutes"]),
        "ratings_given_today":        int(today["ratings"]),
        "genres_watched_today":       int(today["genres"]),
        "watch_minutes_7d":           float(week["total"]),
        "streak_days":                streak,
        "total_points":               int(total_pts["total"]),
        "today_points":               int(today_pts["total"]),
        "badges":                     [b["badge_tier"] for b in badges],
    }


def _calculate_streak(db, user_id: str, run_date: str) -> int:
    """Ardışık aktif gün sayısını hesaplar. Random yok, DB'den okur."""
    streak = 0
    check = datetime.strptime(run_date, "%Y-%m-%d")
    for _ in range(366):
        date_str = check.strftime("%Y-%m-%d")
        row = db.execute("""
            SELECT COUNT(*) AS cnt
            FROM user_activities
            WHERE user_id = ?
              AND activity_date = ?
              AND watch_minutes > 0
        """, (user_id, date_str)).fetchone()
        if row["cnt"] == 0:
            break
        streak += 1
        check -= timedelta(days=1)
    return streak
