from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from api.auth_utils import verify_token
from engine.explanation_engine import explain
from engine.recommendation_engine import get_recommendations
from engine.challenge_tips_engine import get_challenge_tips
from engine.digest_engine import build_digest
from engine.llm_adapter import get_llm_status

router = APIRouter(tags=["AI"])


class ExplainBody(BaseModel):
    question: str = Field(..., min_length=2, max_length=500)


@router.post("/explain")
def ai_explain(body: ExplainBody, token: dict = Depends(verify_token)):
    return explain(body.question, token["sub"])


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
