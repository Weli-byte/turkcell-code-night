from fastapi import APIRouter, Depends
from api.auth_utils import verify_token
from engine.leaderboard_engine import get_leaderboard
from database.setup import get_db
from datetime import datetime, timedelta

router = APIRouter(tags=["Leaderboard"])


@router.get("")
def leaderboard(
    limit: int = 50,
    token: dict = Depends(verify_token),
):
    board   = get_leaderboard(limit)
    user_id = token["sub"]
    for entry in board:
        entry["is_current_user"] = (entry["user_id"] == user_id)
    return board


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
    return [
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
