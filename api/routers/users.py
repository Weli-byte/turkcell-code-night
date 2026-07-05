from fastapi import APIRouter, Depends
from api.auth_utils import verify_token
from engine.state_builder import build_user_state
from engine.leaderboard_engine import get_leaderboard
from engine.ledger import get_history
from database.setup import get_db
from datetime import datetime, timedelta

router = APIRouter(tags=["Users"])


@router.get("/me")
def get_me(token: dict = Depends(verify_token)):
    user_id = token["sub"]
    today   = datetime.now().strftime("%Y-%m-%d")
    state   = build_user_state(user_id, today)

    board = get_leaderboard(10000)
    rank  = next(
        (e["rank"] for e in board if e["user_id"] == user_id),
        len(board) + 1,
    )

    return {
        "user_id":             user_id,
        "username":            token["username"],
        "role":                token.get("role", "user"),
        "total_points":        state["total_points"],
        "today_points":        state["today_points"],
        "rank":                rank,
        "total_users":         len(board),
        "badges":              state["badges"],
        "streak_days":         state["streak_days"],
        "watch_minutes_today": state["watch_minutes_today"],
    }


@router.get("/me/points-history")
def points_history(token: dict = Depends(verify_token)):
    return get_history(token["sub"], limit=100)


@router.get("/me/stats")
def my_stats(token: dict = Depends(verify_token)):
    user_id = token["sub"]
    now     = datetime.now()
    db      = get_db()

    totals = db.execute("""
        SELECT
          COALESCE(SUM(watch_minutes), 0)      AS total_minutes,
          COALESCE(SUM(episodes_completed), 0) AS total_episodes,
          COUNT(DISTINCT activity_date)         AS active_days
        FROM user_activities WHERE user_id = ?
    """, (user_id,)).fetchone()

    sessions = db.execute("""
        SELECT COUNT(*) AS cnt FROM watch_sessions
        WHERE user_id = ? AND ended_at IS NOT NULL
    """, (user_id,)).fetchone()

    best = db.execute("""
        SELECT activity_date,
               SUM(watch_minutes) AS daily_total
        FROM user_activities WHERE user_id = ?
        GROUP BY activity_date
        ORDER BY daily_total DESC LIMIT 1
    """, (user_id,)).fetchone()

    week_start = (
        now - timedelta(days=now.weekday())
    ).strftime("%Y-%m-%d")
    this_week = db.execute("""
        SELECT COALESCE(SUM(watch_minutes), 0) AS total
        FROM user_activities
        WHERE user_id = ? AND activity_date >= ?
    """, (user_id, week_start)).fetchone()

    lw_start = (
        now - timedelta(days=now.weekday() + 7)
    ).strftime("%Y-%m-%d")
    lw_end = (
        now - timedelta(days=now.weekday() + 1)
    ).strftime("%Y-%m-%d")
    last_week = db.execute("""
        SELECT COALESCE(SUM(watch_minutes), 0) AS total
        FROM user_activities
        WHERE user_id = ?
          AND activity_date >= ? AND activity_date <= ?
    """, (user_id, lw_start, lw_end)).fetchone()

    db.close()

    active = int(totals["active_days"])
    avg    = float(totals["total_minutes"]) / active if active > 0 else 0.0
    lw     = float(last_week["total"])
    tw     = float(this_week["total"])
    imp    = round(((tw - lw) / lw * 100) if lw > 0 else 0.0, 1)

    return {
        "total_watch_minutes": round(float(totals["total_minutes"]), 1),
        "total_episodes":      int(totals["total_episodes"]),
        "total_sessions":      int(sessions["cnt"]),
        "avg_daily_minutes":   round(avg, 1),
        "active_days":         active,
        "best_day": {
            "date":          best["activity_date"] if best else None,
            "watch_minutes": round(float(best["daily_total"]), 1) if best else 0.0,
        },
        "this_week_minutes":  round(tw, 1),
        "last_week_minutes":  round(lw, 1),
        "improvement_pct":    imp,
    }
