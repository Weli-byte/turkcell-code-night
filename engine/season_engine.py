"""
Season Engine — Sprint 17.
ISO hafta bazlı resmi sezonlar (pazartesi 00:00 – pazar 23:59).

Zamanlayıcı YOK — lazy finalization: herhangi bir sezon isteği geldiğinde
geçmiş haftaların kapanmamış sezonları idempotent şekilde kapatılır.
Aynı hafta verisi → aynı sonuç (deterministik):
- Sıralama: haftalık puan DESC, eşitlikte username alfabetik.
- Ödüller ilk 3'e points_ledger'a yazılır (activity_date = sezonun pazar günü,
  böylece hiçbir sonraki haftalık yarışı şişirmez). UNIQUE(season_id, user_id)
  + finalized_at guard'ı çifte dağıtımı engeller.
"""

from datetime import datetime, timedelta
from database.setup import get_db
from api.notifications_store import push_notification

# Sıra → ödül puanı (konfigürasyon)
SEASON_REWARDS = {1: 500, 2: 300, 3: 150}
MEDALS         = {1: "🥇", 2: "🥈", 3: "🥉"}


def season_id_for(dt: datetime) -> str:
    """Tarihin ISO sezon kimliği: '2026-W27'."""
    iso = dt.isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


def week_bounds(dt: datetime) -> tuple[str, str]:
    """dt'nin haftasının (pazartesi, pazar) tarihleri."""
    monday = dt - timedelta(days=dt.weekday())
    sunday = monday + timedelta(days=6)
    return monday.strftime("%Y-%m-%d"), sunday.strftime("%Y-%m-%d")


def _weekly_standings(db, week_start: str, week_end: str) -> list[dict]:
    """Hafta aralığının gerçek puan sıralaması (ledger'dan)."""
    rows = db.execute("""
        SELECT u.id AS user_id, u.username,
               COALESCE(SUM(pl.points), 0) AS points
        FROM users u
        LEFT JOIN points_ledger pl
          ON pl.user_id = u.id
         AND pl.activity_date >= ? AND pl.activity_date <= ?
        GROUP BY u.id, u.username
        ORDER BY points DESC, u.username ASC
    """, (week_start, week_end)).fetchall()
    return [
        {"rank": i + 1, "user_id": r["user_id"],
         "username": r["username"], "points": int(r["points"])}
        for i, r in enumerate(rows)
    ]


def finalize_pending_seasons(now: datetime | None = None) -> list[str]:
    """
    Mevcut haftadan ÖNCEKİ tüm kapanmamış sezonları kapatır.
    İdempotent: kapanan sezon tekrar işlenmez. Kapatılan id listesi döner.
    """
    now = now or datetime.now()
    this_monday = (now - timedelta(days=now.weekday())).strftime("%Y-%m-%d")

    db = get_db()

    # Ledger'daki en eski aktiviteden bugüne kadar geçmiş haftaları bul
    first = db.execute(
        "SELECT MIN(activity_date) AS d FROM points_ledger"
    ).fetchone()
    if not first or not first["d"]:
        db.close()
        return []

    finalized: list[str] = []
    cursor = datetime.strptime(first["d"], "%Y-%m-%d")

    while True:
        w_start, w_end = week_bounds(cursor)
        if w_start >= this_monday:
            break  # mevcut ve gelecek haftalar kapatılmaz

        sid = season_id_for(cursor)
        existing = db.execute(
            "SELECT finalized_at FROM seasons WHERE id=?", (sid,)
        ).fetchone()

        if existing is None or existing["finalized_at"] is None:
            standings = _weekly_standings(db, w_start, w_end)
            has_points = any(s["points"] > 0 for s in standings)

            db.execute(
                "INSERT OR IGNORE INTO seasons (id, week_start, week_end) VALUES (?, ?, ?)",
                (sid, w_start, w_end),
            )

            if has_points:
                now_iso = datetime.now().isoformat()
                for s in standings:
                    reward = SEASON_REWARDS.get(s["rank"], 0) if s["points"] > 0 else 0
                    db.execute(
                        "INSERT OR IGNORE INTO season_results "
                        "(season_id, user_id, rank, points, reward_points) "
                        "VALUES (?, ?, ?, ?, ?)",
                        (sid, s["user_id"], s["rank"], s["points"], reward),
                    )
                    if reward > 0:
                        # Ödül biten haftanın pazar tarihine yazılır —
                        # sonraki haftalık yarışları şişirmez
                        db.execute(
                            "INSERT INTO points_ledger "
                            "(user_id, points, reason, activity_date, created_at) "
                            "VALUES (?, ?, ?, ?, ?)",
                            (s["user_id"], reward,
                             f"Sezon {sid} — {s['rank']}. sıra ödülü",
                             w_end, now_iso),
                        )

            db.execute(
                "UPDATE seasons SET finalized_at=? WHERE id=?",
                (datetime.now().isoformat(), sid),
            )
            db.commit()
            finalized.append(sid)

            # Ödül bildirimleri (commit sonrası — kalıcı bildirim sistemi)
            if has_points:
                for s in standings:
                    reward = SEASON_REWARDS.get(s["rank"], 0) if s["points"] > 0 else 0
                    if reward > 0:
                        push_notification(s["user_id"], {
                            "type":    "points",
                            "points":  reward,
                            "reason":  f"{MEDALS.get(s['rank'], '')} Sezon {sid} — "
                                       f"{s['rank']}. sıra ödülü",
                        })

        cursor += timedelta(days=7)

    db.close()
    return finalized


def get_season_overview(user_id: str, now: datetime | None = None) -> dict:
    """Aktif sezon durumu + önceki sezon şampiyonları."""
    now = now or datetime.now()
    finalize_pending_seasons(now)

    sid            = season_id_for(now)
    w_start, w_end = week_bounds(now)

    db        = get_db()
    standings = _weekly_standings(db, w_start, w_end)

    prev_monday = now - timedelta(days=now.weekday() + 7)
    prev_sid    = season_id_for(prev_monday)
    prev_top    = db.execute("""
        SELECT sr.rank, sr.points, sr.reward_points, u.username
        FROM season_results sr
        JOIN users u ON u.id = sr.user_id
        WHERE sr.season_id = ? AND sr.rank <= 3 AND sr.points > 0
        ORDER BY sr.rank
    """, (prev_sid,)).fetchall()
    db.close()

    for s in standings:
        s["is_current_user"] = s["user_id"] == user_id
        s["reward_if_holds"] = SEASON_REWARDS.get(s["rank"], 0) if s["points"] > 0 else 0

    week_end_dt  = datetime.strptime(w_end, "%Y-%m-%d").replace(
        hour=23, minute=59, second=59)
    seconds_left = max(0, int((week_end_dt - now).total_seconds()))

    my = next((s for s in standings if s["is_current_user"]), None)

    return {
        "season_id":    sid,
        "week_start":   w_start,
        "week_end":     w_end,
        "seconds_left": seconds_left,
        "rewards":      SEASON_REWARDS,
        "standings":    standings[:50],
        "my_rank":      my["rank"] if my else None,
        "my_points":    my["points"] if my else 0,
        "previous": {
            "season_id": prev_sid,
            "podium": [
                {"rank": r["rank"], "username": r["username"],
                 "points": r["points"], "reward_points": r["reward_points"],
                 "medal": MEDALS.get(r["rank"], "")}
                for r in prev_top
            ],
        },
    }


def get_season_history(limit: int = 12) -> dict:
    """Kapanmış sezonlar + podyumları (en yeni önce)."""
    finalize_pending_seasons()

    db      = get_db()
    seasons = db.execute("""
        SELECT id, week_start, week_end, finalized_at
        FROM seasons
        WHERE finalized_at IS NOT NULL
        ORDER BY week_start DESC LIMIT ?
    """, (limit,)).fetchall()

    out = []
    for s in seasons:
        podium = db.execute("""
            SELECT sr.rank, sr.points, sr.reward_points, u.username
            FROM season_results sr
            JOIN users u ON u.id = sr.user_id
            WHERE sr.season_id = ? AND sr.rank <= 3 AND sr.points > 0
            ORDER BY sr.rank
        """, (s["id"],)).fetchall()
        participants = db.execute(
            "SELECT COUNT(*) AS c FROM season_results "
            "WHERE season_id=? AND points > 0",
            (s["id"],),
        ).fetchone()
        out.append({
            "season_id":    s["id"],
            "week_start":   s["week_start"],
            "week_end":     s["week_end"],
            "participants": int(participants["c"]),
            "podium": [
                {"rank": p["rank"], "username": p["username"],
                 "points": p["points"], "reward_points": p["reward_points"],
                 "medal": MEDALS.get(p["rank"], "")}
                for p in podium
            ],
        })
    db.close()
    return {"seasons": out}
