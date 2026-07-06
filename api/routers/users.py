from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from api.auth_utils import verify_token, hash_password
from engine.state_builder import build_user_state
from engine.leaderboard_engine import get_leaderboard
from engine.badge_engine import get_badge_progress
from engine.level_engine import get_level
from engine.ledger import get_history
from database.setup import get_db
from datetime import datetime, timedelta

router = APIRouter(tags=["Users"])


class PasswordChange(BaseModel):
    old_password: str = Field(..., min_length=4)
    new_password: str = Field(..., min_length=4, max_length=128)


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
        "level":               get_level(state["total_points"]),
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


@router.get("/me/weekly")
def weekly_activity(token: dict = Depends(verify_token)):
    """Son 7 günün günlük izleme + puan verisi — panel grafiği için."""
    user_id = token["sub"]
    now     = datetime.now()
    db      = get_db()
    days    = []

    for i in range(6, -1, -1):
        d = (now - timedelta(days=i)).strftime("%Y-%m-%d")

        act = db.execute("""
            SELECT COALESCE(SUM(watch_minutes), 0)      AS minutes,
                   COALESCE(SUM(episodes_completed), 0) AS episodes
            FROM user_activities
            WHERE user_id = ? AND activity_date = ?
        """, (user_id, d)).fetchone()

        pts = db.execute("""
            SELECT COALESCE(SUM(points), 0) AS total
            FROM points_ledger
            WHERE user_id = ? AND activity_date = ?
        """, (user_id, d)).fetchone()

        days.append({
            "date":     d,
            "minutes":  round(float(act["minutes"]), 1),
            "episodes": int(act["episodes"]),
            "points":   int(pts["total"]),
        })

    db.close()
    max_min = max((d["minutes"] for d in days), default=1) or 1
    for d in days:
        d["pct"] = round(d["minutes"] / max_min * 100, 1)

    return {"days": days, "max_minutes": max_min}


@router.get("/me/profile")
def my_full_profile(token: dict = Depends(verify_token)):
    """Tek çağrıda tam profil — profil sayfası için."""
    user_id = token["sub"]
    now     = datetime.now()
    today   = now.strftime("%Y-%m-%d")
    state   = build_user_state(user_id, today)

    board      = get_leaderboard(10000)
    rank       = next((e["rank"] for e in board if e["user_id"] == user_id), len(board) + 1)
    total_u    = len(board)
    percentile = round((1 - (rank - 1) / max(total_u, 1)) * 100)
    progress   = get_badge_progress(user_id, state["total_points"])

    db = get_db()

    user_row = db.execute(
        "SELECT created_at FROM users WHERE id=?", (user_id,)
    ).fetchone()

    stats = db.execute("""
        SELECT COALESCE(SUM(watch_minutes),0)      AS total_minutes,
               COALESCE(SUM(episodes_completed),0) AS total_episodes,
               COUNT(DISTINCT activity_date)        AS active_days
        FROM user_activities WHERE user_id=?
    """, (user_id,)).fetchone()

    sessions = db.execute(
        "SELECT COUNT(*) AS cnt FROM watch_sessions WHERE user_id=? AND ended_at IS NOT NULL",
        (user_id,),
    ).fetchone()

    badges = db.execute(
        "SELECT badge_tier, awarded_at FROM user_badges WHERE user_id=? ORDER BY awarded_at",
        (user_id,),
    ).fetchall()

    history = db.execute(
        "SELECT points, reason, activity_date FROM points_ledger "
        "WHERE user_id=? ORDER BY created_at DESC LIMIT 10",
        (user_id,),
    ).fetchall()

    # Weekly chart data
    week_days = []
    for i in range(6, -1, -1):
        d   = (now - timedelta(days=i)).strftime("%Y-%m-%d")
        act = db.execute(
            "SELECT COALESCE(SUM(watch_minutes),0) AS minutes FROM user_activities "
            "WHERE user_id=? AND activity_date=?", (user_id, d),
        ).fetchone()
        pts = db.execute(
            "SELECT COALESCE(SUM(points),0) AS total FROM points_ledger "
            "WHERE user_id=? AND activity_date=?", (user_id, d),
        ).fetchone()
        week_days.append({"date": d, "minutes": round(float(act["minutes"]), 1),
                          "points": int(pts["total"])})

    follower_cnt = db.execute(
        "SELECT COUNT(*) AS c FROM follows WHERE following_id=?", (user_id,)
    ).fetchone()["c"]
    following_cnt = db.execute(
        "SELECT COUNT(*) AS c FROM follows WHERE follower_id=?", (user_id,)
    ).fetchone()["c"]

    db.close()

    max_min = max((d["minutes"] for d in week_days), default=1) or 1
    for d in week_days:
        d["pct"] = round(d["minutes"] / max_min * 100, 1)

    return {
        "user_id":          user_id,
        "username":         token["username"],
        "role":             token.get("role", "user"),
        "created_at":       user_row["created_at"] if user_row else None,
        "rank":             rank,
        "total_users":      total_u,
        "percentile":       percentile,
        "total_points":     state["total_points"],
        "today_points":     state["today_points"],
        "streak_days":      state["streak_days"],
        "watch_minutes_today": state["watch_minutes_today"],
        "total_watch_minutes": round(float(stats["total_minutes"]), 1),
        "total_episodes":   int(stats["total_episodes"]),
        "total_sessions":   int(sessions["cnt"]),
        "active_days":      int(stats["active_days"]),
        "current_badge":    progress["current_badge"],
        "next_badge":       progress["next_badge"],
        "points_to_next":   progress["points_needed"],
        "next_threshold":   progress["next_threshold"],
        "badges":           [{"tier": b["badge_tier"], "awarded_at": b["awarded_at"]} for b in badges],
        "recent_points":    [dict(h) for h in history],
        "weekly":           week_days,
        "level":            get_level(state["total_points"]),
        "follower_count":   int(follower_cnt),
        "following_count":  int(following_cnt),
    }


@router.put("/me/password")
def change_password(body: PasswordChange, token: dict = Depends(verify_token)):
    db   = get_db()
    user = db.execute(
        "SELECT id, password_hash FROM users WHERE id=?", (token["sub"],)
    ).fetchone()
    if not user or user["password_hash"] != hash_password(body.old_password):
        db.close()
        raise HTTPException(401, "Mevcut şifre yanlış")
    db.execute(
        "UPDATE users SET password_hash=? WHERE id=?",
        (hash_password(body.new_password), token["sub"]),
    )
    db.commit()
    db.close()
    return {"ok": True, "message": "Şifre değiştirildi"}


@router.get("/public/{username}")
def public_profile(username: str, token: dict = Depends(verify_token)):
    """Başka kullanıcının herkese açık profili."""
    db   = get_db()
    user = db.execute(
        "SELECT id, username, created_at FROM users WHERE username=?", (username,)
    ).fetchone()
    if not user:
        db.close()
        raise HTTPException(404, "Kullanıcı bulunamadı")

    uid   = user["id"]
    today = datetime.now().strftime("%Y-%m-%d")
    state = build_user_state(uid, today)

    board      = get_leaderboard(10000)
    rank       = next((e["rank"] for e in board if e["user_id"] == uid), len(board) + 1)
    total_u    = len(board)
    percentile = round((1 - (rank - 1) / max(total_u, 1)) * 100)
    progress   = get_badge_progress(uid, state["total_points"])

    stats = db.execute("""
        SELECT COALESCE(SUM(watch_minutes),0)      AS total_minutes,
               COALESCE(SUM(episodes_completed),0) AS total_episodes,
               COUNT(DISTINCT activity_date)        AS active_days
        FROM user_activities WHERE user_id=?
    """, (uid,)).fetchone()

    badges = db.execute(
        "SELECT badge_tier, awarded_at FROM user_badges WHERE user_id=? ORDER BY awarded_at",
        (uid,),
    ).fetchall()

    follower_cnt = db.execute(
        "SELECT COUNT(*) AS c FROM follows WHERE following_id=?", (uid,)
    ).fetchone()["c"]
    following_cnt = db.execute(
        "SELECT COUNT(*) AS c FROM follows WHERE follower_id=?", (uid,)
    ).fetchone()["c"]
    is_following = db.execute(
        "SELECT 1 FROM follows WHERE follower_id=? AND following_id=?",
        (token["sub"], uid),
    ).fetchone() is not None

    db.close()

    return {
        "username":          user["username"],
        "created_at":        user["created_at"],
        "follower_count":    int(follower_cnt),
        "following_count":   int(following_cnt),
        "is_following":      is_following,
        "rank":              rank,
        "total_users":       total_u,
        "percentile":        percentile,
        "total_points":      state["total_points"],
        "streak_days":       state["streak_days"],
        "total_watch_minutes": round(float(stats["total_minutes"]), 1),
        "total_episodes":    int(stats["total_episodes"]),
        "active_days":       int(stats["active_days"]),
        "current_badge":     progress["current_badge"],
        "next_badge":        progress["next_badge"],
        "badges":            [{"tier": b["badge_tier"], "awarded_at": b["awarded_at"]} for b in badges],
        "is_self":           uid == token["sub"],
        "level":             get_level(state["total_points"]),
    }
