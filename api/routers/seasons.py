from fastapi import APIRouter, Depends, Query
from api.auth_utils import verify_token
from engine.season_engine import get_season_overview, get_season_history

router = APIRouter(tags=["Seasons"])


@router.get("/current")
def current_season(token: dict = Depends(verify_token)):
    """Aktif sezon: canlı sıralama, kalan süre, ödüller, önceki podium.
    Çağrı sırasında geçmiş kapanmamış sezonlar idempotent kapatılır."""
    return get_season_overview(token["sub"])


@router.get("/history")
def season_history(
    limit: int = Query(12, ge=1, le=52),
    token: dict = Depends(verify_token),
):
    """Kapanmış sezonlar + podyumları."""
    return get_season_history(limit)
