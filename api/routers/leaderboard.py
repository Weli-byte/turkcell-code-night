"""api/routers/leaderboard.py — deterministik liderlik tablolari."""

from fastapi import APIRouter, Depends

from engine.ai_leaderboard import (
    get_leaderboard, get_weekly_leaderboard, get_user_rank_history,
)
from api.auth_utils import verify_token

router = APIRouter(prefix="/api/leaderboard", tags=["leaderboard"])


@router.get("")
def leaderboard(limit: int = 50, token: dict = Depends(verify_token)):
    board = get_leaderboard(limit)
    for entry in board:
        entry["is_current_user"] = entry["user_id"] == token["sub"]
    return board


@router.get("/weekly")
def weekly(limit: int = 50, token: dict = Depends(verify_token)):
    board = get_weekly_leaderboard(limit)
    for entry in board:
        entry["is_current_user"] = entry["user_id"] == token["sub"]
    return board


@router.get("/my-history")
def my_history(days: int = 7, token: dict = Depends(verify_token)):
    return get_user_rank_history(token["sub"], days=days)
