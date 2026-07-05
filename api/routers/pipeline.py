from fastapi import APIRouter, Depends
from api.auth_utils import verify_token, require_admin
from database.setup import get_db
from engine.pipeline import run_pipeline

router = APIRouter(tags=["Admin"])


@router.post("/run")
def trigger_pipeline(token: dict = Depends(verify_token)):
    require_admin(token)
    return run_pipeline()


@router.get("/runs")
def pipeline_history(token: dict = Depends(verify_token)):
    require_admin(token)
    db   = get_db()
    rows = db.execute(
        "SELECT * FROM pipeline_runs ORDER BY ran_at DESC LIMIT 50"
    ).fetchall()
    db.close()
    return [dict(r) for r in rows]


@router.get("/metrics")
def admin_metrics(token: dict = Depends(verify_token)):
    """Canlı platform metrikleri — admin dashboard için."""
    require_admin(token)
    db = get_db()

    totals = db.execute("""
        SELECT
          (SELECT COUNT(*) FROM users)                        AS total_users,
          (SELECT COUNT(*) FROM challenges WHERE is_active=1) AS active_challenges,
          (SELECT COALESCE(SUM(points),0) FROM points_ledger) AS total_points,
          (SELECT COUNT(*) FROM watch_sessions WHERE ended_at IS NOT NULL) AS total_sessions,
          (SELECT COUNT(*) FROM pipeline_runs)               AS pipeline_runs
    """).fetchone()

    from datetime import datetime
    today = datetime.now().strftime("%Y-%m-%d")
    today_row = db.execute("""
        SELECT
          COUNT(DISTINCT user_id)          AS active_users_today,
          COALESCE(SUM(watch_minutes), 0)  AS watch_minutes_today,
          (SELECT COALESCE(SUM(points),0) FROM points_ledger WHERE activity_date=?) AS points_today
        FROM user_activities WHERE activity_date=?
    """, (today, today)).fetchone()

    db.close()
    return {
        "total_users":        totals["total_users"],
        "active_challenges":  totals["active_challenges"],
        "total_points":       int(totals["total_points"]),
        "total_sessions":     totals["total_sessions"],
        "pipeline_runs":      totals["pipeline_runs"],
        "active_users_today": today_row["active_users_today"],
        "watch_minutes_today": round(float(today_row["watch_minutes_today"]), 1),
        "points_today":       int(today_row["points_today"]),
    }
