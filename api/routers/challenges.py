"""api/routers/challenges.py — aktif challenge'lar + kullanici ilerlemesi."""

from datetime import datetime

from fastapi import APIRouter, Depends

from database.setup import get_db
from engine.state_builder import build_user_state
from engine.condition_parser import parse_condition, get_progress
from engine.ledger import already_rewarded
from api.auth_utils import verify_token

router = APIRouter(prefix="/api/challenges", tags=["challenges"])

DATE_FMT = "%Y-%m-%d"


@router.get("/active")
def active_challenges(token: dict = Depends(verify_token)):
    user_id = token["sub"]
    today = datetime.now().strftime(DATE_FMT)
    state = build_user_state(user_id, today)

    db = get_db()
    try:
        rows = db.execute(
            "SELECT id, name, condition, reward_points, priority "
            "FROM challenges WHERE is_active=1 ORDER BY priority DESC, id",
        ).fetchall()
    finally:
        db.close()

    result = []
    for r in rows:
        ch = dict(r)
        try:
            passed = parse_condition(ch["condition"], state)
            prog = get_progress(ch["condition"], state)
            current_value = prog["current"]
            target_value = prog["target"]
            percentage = prog["percentage"]
        except Exception:
            passed = False
            current_value = target_value = None
            percentage = 0

        result.append({
            "id": ch["id"],
            "name": ch["name"],
            "condition": ch["condition"],
            "reward_points": ch["reward_points"],
            "priority": ch["priority"],
            "passed": bool(passed),
            "rewarded_today": already_rewarded(user_id, ch["id"], today),
            "current_value": current_value,
            "target_value": target_value,
            "percentage": percentage,
            "is_ai_generated": ch["id"].startswith("ai_ch_"),
        })
    return result
