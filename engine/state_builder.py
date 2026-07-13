"""
engine/state_builder.py — Kullanici gunluk state hesabi.

Tum degerler SADECE DB'den (user_activities, points_ledger, user_badges).
Sabit sayi yok, rastgelelik yok. Deterministik: ayni DB + ayni run_date -> ayni state.
"""

from datetime import datetime, timedelta

from database.setup import get_db

DATE_FMT = "%Y-%m-%d"


def _calculate_streak(db, user_id: str, run_date: str) -> int:
    """
    run_date'ten geriye gun gun ilerler. Bir gunde watch_minutes toplami > 0 ise
    streak sayar, ilk bos gunde durur. Maksimum 366 gun. Deterministik.
    """
    base = datetime.strptime(run_date, DATE_FMT)
    streak = 0
    for offset in range(366):
        day = (base - timedelta(days=offset)).strftime(DATE_FMT)
        row = db.execute(
            "SELECT COALESCE(SUM(watch_minutes), 0) AS wm "
            "FROM user_activities WHERE user_id=? AND activity_date=?",
            (user_id, day),
        ).fetchone()
        if float(row["wm"]) > 0:
            streak += 1
        else:
            break
    return streak


def build_user_state(user_id: str, run_date: str) -> dict:
    """
    Kullanicinin run_date'e ait tam state'ini DB'den hesaplar.
    Doner: bugun toplamlari + 7 gun + toplam/bugun puan + rozetler + streak.
    """
    db = get_db()
    try:
        # Bugunun toplamlari (run_date filtreli)
        today = db.execute(
            """
            SELECT
                COALESCE(SUM(watch_minutes), 0)       AS watch_minutes,
                COALESCE(SUM(episodes_completed), 0)  AS episodes,
                COALESCE(SUM(watch_party_minutes), 0) AS party,
                COALESCE(SUM(ratings_given), 0)       AS ratings,
                COALESCE(SUM(genres_watched), 0)      AS genres
            FROM user_activities
            WHERE user_id=? AND activity_date=?
            """,
            (user_id, run_date),
        ).fetchone()

        # Son 7 gun (run_date - 6 ... run_date dahil)
        start_7d = (datetime.strptime(run_date, DATE_FMT) - timedelta(days=6)).strftime(DATE_FMT)
        week = db.execute(
            """
            SELECT COALESCE(SUM(watch_minutes), 0) AS wm
            FROM user_activities
            WHERE user_id=? AND activity_date BETWEEN ? AND ?
            """,
            (user_id, start_7d, run_date),
        ).fetchone()

        # Toplam puan (tum zamanlar)
        total_row = db.execute(
            "SELECT COALESCE(SUM(points), 0) AS total FROM points_ledger WHERE user_id=?",
            (user_id,),
        ).fetchone()

        # Bugun kazanilan puan
        today_pts_row = db.execute(
            "SELECT COALESCE(SUM(points), 0) AS total FROM points_ledger "
            "WHERE user_id=? AND activity_date=?",
            (user_id, run_date),
        ).fetchone()

        # Rozetler
        badge_rows = db.execute(
            "SELECT badge_tier FROM user_badges WHERE user_id=? ORDER BY awarded_at",
            (user_id,),
        ).fetchall()
        badges = [r["badge_tier"] for r in badge_rows]

        # Streak
        streak_days = _calculate_streak(db, user_id, run_date)

        return {
            "user_id": user_id,
            "run_date": run_date,
            "watch_minutes_today": float(today["watch_minutes"]),
            "episodes_completed_today": int(today["episodes"]),
            "watch_party_minutes_today": float(today["party"]),
            "ratings_given_today": int(today["ratings"]),
            "genres_watched_today": int(today["genres"]),
            "watch_minutes_7d": float(week["wm"]),
            "streak_days": int(streak_days),
            "total_points": int(total_row["total"]),
            "today_points": int(today_pts_row["total"]),
            "badges": badges,
        }
    finally:
        db.close()
