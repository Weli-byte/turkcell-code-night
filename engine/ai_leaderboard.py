"""
engine/ai_leaderboard.py — Coklu deterministik leaderboard.

Tum siralamalar deterministik: metrik DESC, esitlikte user_id ASC. Rastgelelik yok.
Tum degerler DB'den hesaplanir (points_ledger, user_activities, users, watch_sessions).
"""

from datetime import datetime, timedelta

from database.setup import get_db
from engine.state_builder import _calculate_streak

LEADERBOARD_TYPES = [
    "en_aktif", "en_sosyal", "en_istikrarli",
    "en_hizli_gelisen", "kesfedici",
    "yeni_baslayanlar", "ai_score",
    "consistency_score", "discovery_score",
]

DATE_FMT = "%Y-%m-%d"


def _monday_of(run_date: str) -> str:
    d = datetime.strptime(run_date, DATE_FMT)
    monday = d - timedelta(days=d.weekday())
    return monday.strftime(DATE_FMT)


def _badges_for(db, user_id: str) -> list:
    rows = db.execute(
        "SELECT badge_tier FROM user_badges WHERE user_id=? ORDER BY total_points_at_award, id",
        (user_id,),
    ).fetchall()
    return [r["badge_tier"] for r in rows]


def get_leaderboard(limit: int = 50) -> list:
    """Genel leaderboard: toplam puan DESC, esitlikte user_id ASC (deterministik)."""
    db = get_db()
    try:
        rows = db.execute(
            """
            SELECT u.id AS user_id, u.username,
                   COALESCE(SUM(pl.points), 0) AS total_points
            FROM users u
            LEFT JOIN points_ledger pl ON pl.user_id = u.id
            GROUP BY u.id, u.username
            ORDER BY total_points DESC, u.id ASC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        result = []
        for i, r in enumerate(rows):
            result.append({
                "rank": i + 1,
                "user_id": r["user_id"],
                "username": r["username"],
                "total_points": int(r["total_points"]),
                "badges": _badges_for(db, r["user_id"]),
            })
        return result
    finally:
        db.close()


def get_weekly_leaderboard(limit: int = 50) -> list:
    """Bu haftanin (Pazartesi->bugun) puanlari. Deterministik siralama."""
    today = datetime.now().strftime(DATE_FMT)
    week_start = _monday_of(today)
    db = get_db()
    try:
        rows = db.execute(
            """
            SELECT u.id AS user_id, u.username, COALESCE(w.pts, 0) AS weekly_points
            FROM users u
            LEFT JOIN (
                SELECT user_id, SUM(points) AS pts
                FROM points_ledger
                WHERE activity_date >= ? AND activity_date <= ?
                GROUP BY user_id
            ) w ON w.user_id = u.id
            ORDER BY weekly_points DESC, u.id ASC
            LIMIT ?
            """,
            (week_start, today, limit),
        ).fetchall()
        return [
            {
                "rank": i + 1,
                "user_id": r["user_id"],
                "username": r["username"],
                "weekly_points": int(r["weekly_points"]),
                "week_start": week_start,
            }
            for i, r in enumerate(rows)
        ]
    finally:
        db.close()


def _collect_metrics(db, run_date: str) -> dict:
    """Her kullanici icin metrik toplar (deterministik, DB'den)."""
    today = run_date
    monday = _monday_of(today)
    last_monday = (datetime.strptime(monday, DATE_FMT) - timedelta(days=7)).strftime(DATE_FMT)
    last_sunday = (datetime.strptime(monday, DATE_FMT) - timedelta(days=1)).strftime(DATE_FMT)

    users = db.execute("SELECT id, username, created_at FROM users").fetchall()
    metrics = {}
    for u in users:
        uid = u["id"]
        act = db.execute(
            """
            SELECT
                COALESCE(SUM(watch_minutes), 0) AS wm,
                COALESCE(SUM(watch_party_minutes), 0) AS party,
                COUNT(DISTINCT CASE WHEN watch_minutes > 0 THEN activity_date END) AS active_days
            FROM user_activities WHERE user_id=?
            """,
            (uid,),
        ).fetchone()
        total = db.execute(
            "SELECT COALESCE(SUM(points), 0) AS t FROM points_ledger WHERE user_id=?",
            (uid,),
        ).fetchone()["t"]
        this_week = db.execute(
            "SELECT COALESCE(SUM(watch_minutes),0) AS s FROM user_activities "
            "WHERE user_id=? AND activity_date >= ? AND activity_date <= ?",
            (uid, monday, today),
        ).fetchone()["s"]
        last_week = db.execute(
            "SELECT COALESCE(SUM(watch_minutes),0) AS s FROM user_activities "
            "WHERE user_id=? AND activity_date >= ? AND activity_date <= ?",
            (uid, last_monday, last_sunday),
        ).fetchone()["s"]
        genres = db.execute(
            """
            SELECT COUNT(DISTINCT cc.genre) AS g
            FROM watch_sessions ws
            JOIN content_catalog cc ON cc.id = ws.content_id
            WHERE ws.user_id=? AND cc.genre IS NOT NULL
            """,
            (uid,),
        ).fetchone()["g"]
        streak = _calculate_streak(db, uid, today)

        growth = (float(this_week) / float(last_week)) if float(last_week) > 0 else float(this_week)

        metrics[uid] = {
            "username": u["username"],
            "created_at": u["created_at"],
            "watch_minutes": float(act["wm"]),
            "social": float(act["party"]),
            "active_days": int(act["active_days"]),
            "total_points": int(total),
            "streak": int(streak),
            "genres": int(genres),
            "growth": float(growth),
            "ai_score": float(total) * 0.5 + int(streak) * 10 + float(act["party"]) * 0.3,
        }
    return metrics


def get_category_leaderboard(category: str, limit: int = 50) -> list:
    """
    Kategori bazli leaderboard. Her kategori farkli metrik.
    Gecersiz kategori -> ValueError. Deterministik: skor DESC, user_id ASC.
    """
    if category not in LEADERBOARD_TYPES:
        raise ValueError(f"Gecersiz leaderboard kategorisi: {category}")

    today = datetime.now().strftime(DATE_FMT)
    db = get_db()
    try:
        metrics = _collect_metrics(db, today)
    finally:
        db.close()

    score_key = {
        "en_aktif": "watch_minutes",
        "en_sosyal": "social",
        "en_istikrarli": "streak",
        "en_hizli_gelisen": "growth",
        "kesfedici": "genres",
        "discovery_score": "genres",
        "consistency_score": "active_days",
        "ai_score": "ai_score",
    }

    if category == "yeni_baslayanlar":
        cutoff = (datetime.strptime(today, DATE_FMT) - timedelta(days=7)).strftime(DATE_FMT)
        items = [
            (uid, m["username"], m["created_at"])
            for uid, m in metrics.items()
            if (m["created_at"] or "")[:10] >= cutoff
        ]
        # Deterministik (iki stabil sort): once user_id ASC, sonra created_at DESC
        items.sort(key=lambda x: x[0])                    # user_id ASC (tie-break)
        items.sort(key=lambda x: x[2] or "", reverse=True)  # created_at DESC (birincil)
        return [
            {"rank": i + 1, "user_id": uid, "username": uname, "score": created, "category": category}
            for i, (uid, uname, created) in enumerate(items[:limit])
        ]

    key = score_key[category]
    ranked = sorted(
        metrics.items(),
        key=lambda kv: (-kv[1][key], kv[0]),  # skor DESC, user_id ASC
    )
    return [
        {
            "rank": i + 1,
            "user_id": uid,
            "username": m["username"],
            "score": round(m[key], 3),
            "category": category,
        }
        for i, (uid, m) in enumerate(ranked[:limit])
    ]


def get_user_rank_history(user_id: str, days: int = 7) -> list:
    """
    Son X gunun her gunu icin, o gune kadar birikmis puana gore kullanicinin sirasi.
    Deterministik: birikmis puan DESC, user_id ASC. Doner: [{date, rank}, ...] (eskiden yeniye).
    """
    today = datetime.now()
    db = get_db()
    try:
        user_ids = [r["id"] for r in db.execute("SELECT id FROM users").fetchall()]
        history = []
        for offset in range(days - 1, -1, -1):
            day = (today - timedelta(days=offset)).strftime(DATE_FMT)
            rows = db.execute(
                "SELECT user_id, COALESCE(SUM(points),0) AS pts FROM points_ledger "
                "WHERE activity_date IS NOT NULL AND activity_date <= ? GROUP BY user_id",
                (day,),
            ).fetchall()
            cumulative = {uid: 0 for uid in user_ids}
            for r in rows:
                if r["user_id"] in cumulative:
                    cumulative[r["user_id"]] = int(r["pts"])
            ordered = sorted(cumulative.items(), key=lambda kv: (-kv[1], kv[0]))
            rank = next((i + 1 for i, (uid, _) in enumerate(ordered) if uid == user_id), None)
            history.append({"date": day, "rank": rank})
        return history
    finally:
        db.close()
