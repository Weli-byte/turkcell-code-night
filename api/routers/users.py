from fastapi import APIRouter, Depends
from api.auth_utils import verify_token
from engine.state_builder import build_user_state
from engine.leaderboard_engine import get_leaderboard
from engine.ledger import get_history
from datetime import datetime

router = APIRouter(tags=["Users"])


@router.get("/me")
def get_me(token: dict = Depends(verify_token)):
    user_id = token["sub"]
    today   = datetime.now().strftime("%Y-%m-%d")
    state   = build_user_state(user_id, today)

    board = get_leaderboard(10000)
    rank  = next(
        (e["rank"] for e in board if e["user_id"] == user_id),
        len(board) + 1
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
