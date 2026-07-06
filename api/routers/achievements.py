from fastapi import APIRouter, Depends
from api.auth_utils import verify_token
from engine.achievement_engine import check_achievements, get_achievements_status

router = APIRouter(tags=["Achievements"])


@router.get("/mine")
def my_achievements(token: dict = Depends(verify_token)):
    """Tüm başarımlar — kazanılan + kilitli (gerçek ilerlemeyle).
    Çağrı öncesi hak edilmiş ama işlenmemiş başarımlar idempotent işlenir."""
    check_achievements(token["sub"])
    return get_achievements_status(token["sub"])
