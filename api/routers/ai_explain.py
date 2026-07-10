from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from api.auth_utils import verify_token
from engine.explanation_engine import explain
from engine.recommendation_engine import get_recommendations
from engine.challenge_tips_engine import get_challenge_tips
from engine.digest_engine import build_digest
from engine.chat_engine import chat, get_chat_history, clear_chat_history
from engine.weekly_report_engine import build_weekly_report
from engine.llm_adapter import get_llm_status

router = APIRouter(tags=["AI"])


class ExplainBody(BaseModel):
    question: str = Field(..., min_length=2, max_length=500)


@router.post("/explain")
def ai_explain(body: ExplainBody, token: dict = Depends(verify_token)):
    return explain(body.question, token["sub"])


@router.post("/chat")
def ai_chat(body: ExplainBody, token: dict = Depends(verify_token)):
    """Konuşma hafızalı AI koç — geçmiş DB'den, evidence deterministik."""
    result = chat(token["sub"], body.question)
    # Başarım kontrolü (Meraklı — ilk AI sohbeti)
    from engine.achievement_engine import check_achievements
    check_achievements(token["sub"])
    return result


@router.get("/chat/history")
def ai_chat_history(token: dict = Depends(verify_token)):
    return get_chat_history(token["sub"])


@router.delete("/chat/history")
def ai_chat_clear(token: dict = Depends(verify_token)):
    return clear_chat_history(token["sub"])


@router.get("/weekly-report")
def ai_weekly_report(token: dict = Depends(verify_token)):
    """Son 7 günün gerçek verilerinden GPT-4o haftalık koç raporu."""
    return build_weekly_report(token["sub"])


@router.get("/daily-plan")
def ai_daily_plan(refresh: bool = False, token: dict = Depends(verify_token)):
    """Günün Planı (Sprint 27) — günde bir kez GPT-4o ile üretilir,
    cache'ten servis edilir; refresh=true elle yeniler."""
    from engine.daily_plan_engine import build_daily_plan
    return build_daily_plan(token["sub"], force=refresh)


@router.get("/recommendations")
def ai_recommendations(token: dict = Depends(verify_token)):
    """Gerçek izleme geçmişine dayalı GPT-4o video önerileri."""
    return get_recommendations(token["sub"])


@router.get("/challenge-tips")
def ai_challenge_tips(token: dict = Depends(verify_token)):
    """Her aktif challenge için anlık gap + GPT-4o motivasyon metni."""
    return get_challenge_tips(token["sub"])


@router.post("/digest")
def ai_digest(token: dict = Depends(verify_token)):
    """GPT-4o ile kişisel günlük özet."""
    return build_digest(token["sub"])


@router.get("/status")
def llm_status():
    return get_llm_status()
