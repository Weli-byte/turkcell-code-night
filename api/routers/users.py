"""api/routers/users.py — profil, puan gecmisi, istatistik. Tum degerler DB'den."""

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends

from database.setup import get_db
from engine.state_builder import build_user_state
from engine.ledger import get_history
from engine.ai_leaderboard import get_leaderboard
from api.auth_utils import verify_token

router = APIRouter(prefix="/api/users", tags=["users"])

DATE_FMT = "%Y-%m-%d"


@router.get("/me")
def me(token: dict = Depends(verify_token)):
    user_id = token["sub"]
    today = datetime.now().strftime(DATE_FMT)
    state = build_user_state(user_id, today)

    board = get_leaderboard(1000)
    rank = next((e["rank"] for e in board if e["user_id"] == user_id), None)

    return {
        "user_id": user_id,
        "username": token["username"],
        "role": token["role"],
        "total_points": state["total_points"],
        "today_points": state["today_points"],
        "rank": rank,
        "total_users": len(board),
        "badges": state["badges"],
        "streak_days": state["streak_days"],
        "watch_minutes_today": state["watch_minutes_today"],
    }


@router.get("/me/points-history")
def points_history(limit: int = 100, token: dict = Depends(verify_token)):
    return get_history(token["sub"], limit=limit)


@router.get("/me/stats")
def stats(token: dict = Depends(verify_token)):
    user_id = token["sub"]
    now = datetime.now()
    today = now.strftime(DATE_FMT)
    monday = (now - timedelta(days=now.weekday())).strftime(DATE_FMT)
    last_monday = (now - timedelta(days=now.weekday() + 7)).strftime(DATE_FMT)
    last_sunday = (now - timedelta(days=now.weekday() + 1)).strftime(DATE_FMT)

    db = get_db()
    try:
        agg = db.execute(
            """
            SELECT
                COALESCE(SUM(watch_minutes), 0)                 AS total_watch_minutes,
                COALESCE(SUM(episodes_completed), 0)            AS total_episodes,
                COUNT(DISTINCT activity_date)                   AS active_days
            FROM user_activities WHERE user_id=?
            """,
            (user_id,),
        ).fetchone()

        total_sessions = db.execute(
            "SELECT COUNT(*) AS n FROM watch_sessions WHERE user_id=?", (user_id,)
        ).fetchone()["n"]

        best = db.execute(
            """
            SELECT activity_date, SUM(watch_minutes) AS mins
            FROM user_activities WHERE user_id=?
            GROUP BY activity_date
            ORDER BY mins DESC, activity_date ASC LIMIT 1
            """,
            (user_id,),
        ).fetchone()

        this_week = db.execute(
            "SELECT COALESCE(SUM(watch_minutes),0) AS s FROM user_activities "
            "WHERE user_id=? AND activity_date >= ? AND activity_date <= ?",
            (user_id, monday, today),
        ).fetchone()["s"]

        last_week = db.execute(
            "SELECT COALESCE(SUM(watch_minutes),0) AS s FROM user_activities "
            "WHERE user_id=? AND activity_date >= ? AND activity_date <= ?",
            (user_id, last_monday, last_sunday),
        ).fetchone()["s"]
    finally:
        db.close()

    active_days = int(agg["active_days"])
    total_minutes = float(agg["total_watch_minutes"])
    avg_daily = round(total_minutes / active_days, 1) if active_days > 0 else 0.0

    improvement_pct = None
    if float(last_week) > 0:
        improvement_pct = round((float(this_week) - float(last_week)) / float(last_week) * 100, 1)

    return {
        "total_watch_minutes": total_minutes,
        "total_episodes": int(agg["total_episodes"]),
        "total_sessions": int(total_sessions),
        "avg_daily_minutes": avg_daily,
        "active_days": active_days,
        "best_day": dict(best) if best else None,
        "this_week_minutes": float(this_week),
        "last_week_minutes": float(last_week),
        "improvement_pct": improvement_pct,
    }
