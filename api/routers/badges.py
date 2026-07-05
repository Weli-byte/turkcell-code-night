from fastapi import APIRouter, Depends
from api.auth_utils import verify_token
from engine.badge_engine import get_user_badges, get_badge_progress
from engine.ledger import get_total_points

router = APIRouter(tags=["Badges"])


@router.get("/mine")
def my_badges(token: dict = Depends(verify_token)):
    return get_user_badges(token["sub"])


@router.get("/progress")
def badge_progress(token: dict = Depends(verify_token)):
    total = get_total_points(token["sub"])
    return get_badge_progress(token["sub"], total)
