from fastapi import APIRouter, Depends, Query
from typing import Optional
from api.auth_utils import verify_token
from engine.leaderboard_engine import get_leaderboard
from database.setup import get_db
from datetime import datetime, timedelta

router = APIRouter(tags=["Leaderboard"])


@router.get("")
def leaderboard(
    limit: int = 100,
    q: Optional[str] = Query(None, description="Username arama"),
    token: dict = Depends(verify_token),
):
    board   = get_leaderboard(limit)
    user_id = token["sub"]
    total   = len(board)

    my_rank = next((e["rank"] for e in board if e["user_id"] == user_id), total + 1)
    percentile = round((1 - (my_rank - 1) / max(total, 1)) * 100) if total else 100

    for entry in board:
        entry["is_current_user"] = (entry["user_id"] == user_id)

    if q:
        board = [e for e in board if q.lower() in (e.get("username") or "").lower()]

    return {
        "leaderboard": board,
        "total_users": total,
        "my_rank":     my_rank,
        "percentile":  percentile,
    }


@router.get("/weekly")
def weekly_leaderboard(token: dict = Depends(verify_token)):
    today  = datetime.now()
    wstart = (today - timedelta(days=today.weekday())).strftime("%Y-%m-%d")
    db     = get_db()
    rows   = db.execute("""
        SELECT u.id, u.username,
               COALESCE(SUM(pl.points), 0) AS weekly_points
        FROM users u
        LEFT JOIN points_ledger pl
          ON pl.user_id = u.id AND pl.activity_date >= ?
        GROUP BY u.id, u.username
        ORDER BY weekly_points DESC, u.id ASC
        LIMIT 50
    """, (wstart,)).fetchall()
    db.close()
    uid = token["sub"]
    result = [
        {
            "rank":            i + 1,
            "user_id":         r["id"],
            "username":        r["username"],
            "weekly_points":   int(r["weekly_points"]),
            "week_start":      wstart,
            "is_current_user": r["id"] == uid,
        }
        for i, r in enumerate(rows)
    ]
    total      = len(result)
    my_rank    = next((e["rank"] for e in result if e["is_current_user"]), total + 1)
    percentile = round((1 - (my_rank - 1) / max(total, 1)) * 100) if total else 100

    # Haftanın bitiş zamanı (Pazar 23:59:59 UTC)
    days_left  = 6 - datetime.now().weekday()
    week_end   = (datetime.now() + timedelta(days=days_left)).replace(
        hour=23, minute=59, second=59
    )
    seconds_left = max(0, int((week_end - datetime.now()).total_seconds()))

    return {
        "leaderboard":   result,
        "total_users":   total,
        "my_rank":       my_rank,
        "percentile":    percentile,
        "week_start":    wstart,
        "seconds_left":  seconds_left,
    }


@router.get("/streaks")
def streak_leaderboard(token: dict = Depends(verify_token)):
    """Streak sıralaması — en uzun ard arda izleme serisi."""
    from engine.state_builder import build_user_state
    db    = get_db()
    today = datetime.now().strftime("%Y-%m-%d")
    users = db.execute("SELECT id, username FROM users ORDER BY id").fetchall()
    db.close()
    uid   = token["sub"]

    rows = []
    for u in users:
        state = build_user_state(u["id"], today)
        rows.append({
            "user_id":  u["id"],
            "username": u["username"],
            "streak":   state["streak_days"],
        })

    rows.sort(key=lambda r: (-r["streak"], r["username"]))
    return [
        {
            "rank":            i + 1,
            "user_id":         r["user_id"],
            "username":        r["username"],
            "streak_days":     r["streak"],
            "is_current_user": r["user_id"] == uid,
        }
        for i, r in enumerate(rows)
    ]


@router.get("/my-history")
def my_rank_history(token: dict = Depends(verify_token)):
    uid = token["sub"]
    db  = get_db()
    out = []
    for i in range(7):
        date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
        row  = db.execute("""
            SELECT COUNT(*) + 1 AS rank FROM users u2
            WHERE (
                SELECT COALESCE(SUM(p2.points), 0)
                FROM points_ledger p2
                WHERE p2.user_id = u2.id
                  AND p2.activity_date <= ?
            ) > (
                SELECT COALESCE(SUM(p3.points), 0)
                FROM points_ledger p3
                WHERE p3.user_id = ?
                  AND p3.activity_date <= ?
            )
        """, (date, uid, date)).fetchone()
        out.append({"date": date, "rank": row["rank"]})
    db.close()
    return out
