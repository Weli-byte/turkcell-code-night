from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from api.auth_utils import verify_token
from engine.explanation_engine import explain

router = APIRouter(tags=["AI"])


class ExplainBody(BaseModel):
    question: str = Field(..., min_length=2, max_length=500)


@router.post("/explain")
def ai_explain(
    body: ExplainBody,
    token: dict = Depends(verify_token),
):
    return explain(body.question, token["sub"])
