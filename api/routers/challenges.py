from fastapi import APIRouter, Depends
from api.auth_utils import verify_token
from database.setup import get_db
from engine.state_builder import build_user_state
from engine.condition_parser import parse_condition, get_progress
from engine.ledger import already_rewarded
from datetime import datetime

router = APIRouter(tags=["Challenges"])


@router.get("/active")
def active_challenges(token: dict = Depends(verify_token)):
    db    = get_db()
    today = datetime.now().strftime("%Y-%m-%d")
    chs   = db.execute(
        "SELECT * FROM challenges WHERE is_active = 1 ORDER BY priority DESC"
    ).fetchall()
    db.close()

    state  = build_user_state(token["sub"], today)
    result = []

    for ch in chs:
        try:
            passed = parse_condition(ch["condition"], state)
        except ValueError:
            passed = False

        prog     = get_progress(ch["condition"], state)
        rewarded = already_rewarded(token["sub"], ch["id"], today)

        result.append({
            "id":             ch["id"],
            "name":           ch["name"],
            "condition":      ch["condition"],
            "reward_points":  ch["reward_points"],
            "priority":       ch["priority"],
            "passed":         passed,
            "rewarded_today": rewarded,
            "current_value":  prog["current"],
            "target_value":   prog["target"],
            "percentage":     prog["percentage"],
        })

    return result
