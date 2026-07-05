from fastapi import APIRouter, Depends
from api.auth_utils import verify_token
from engine.leaderboard_engine import get_leaderboard

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
