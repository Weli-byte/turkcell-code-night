"""api/routers/badges.py — rozetler ve rozet ilerlemesi."""

from fastapi import APIRouter, Depends

from engine.badge_engine import get_user_badges, get_badge_progress
from engine.ledger import get_total_points
from api.auth_utils import verify_token

router = APIRouter(prefix="/api/badges", tags=["badges"])


@router.get("/mine")
def mine(token: dict = Depends(verify_token)):
    return get_user_badges(token["sub"])


@router.get("/progress")
def progress(token: dict = Depends(verify_token)):
    total = get_total_points(token["sub"])
    prog = get_badge_progress(token["sub"], total)
    return {
        "current_points": total,
        "current_badge": prog["current_badge"],
        "next_badge": prog["next_badge"],
        "next_threshold": prog["next_threshold"],
        "points_needed": prog["points_needed"],
        "percentage": prog["percentage"],
        "tiers": prog["tiers"],
    }
