"""
api/routers/ai_explain.py — AI aciklama, durum, tool listesi, challenge uretimi,
kategori leaderboard, oneriler, hafiza. Tum cevaplar gercek veriye dayali.
"""

import os
import time
from datetime import datetime, timedelta

from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from database.setup import get_db
from engine.explanation_engine import explain
from engine.ai_challenge_engine import generate_personal_challenges
from engine.ai_leaderboard import get_category_leaderboard
from engine.recommendation_engine import recommend_all, recommend, RECOMMENDATION_TYPES
from engine import memory_store
from ai.tool_registry import list_tools
from api.auth_utils import verify_token

load_dotenv()

router = APIRouter(prefix="/api/ai", tags=["ai"])


class QuestionBody(BaseModel):
    question: str


def _log_ai_call(model, latency_ms, grounding_score, user_id, intent):
    """Her AI cagrisini ai_calls_log'a yazar (audit). Token/maliyet takibi Sprint 5D'de."""
    db = get_db()
    try:
        db.execute(
            "INSERT INTO ai_calls_log "
            "(model, tokens_in, tokens_out, latency_ms, grounding_score, cost, "
            " user_id, intent, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
            (model, 0, 0, int(latency_ms), grounding_score, 0.0,
             user_id, intent, datetime.now().isoformat()),
        )
        db.commit()
    finally:
        db.close()


@router.post("/explain")
def ai_explain(body: QuestionBody, token: dict = Depends(verify_token)):
    t0 = time.perf_counter()
    result = explain(body.question, token["sub"])
    latency = (time.perf_counter() - t0) * 1000

    _log_ai_call(result["model"], latency, result["grounding_score"],
                 token["sub"], result["intent"])

    return {
        "answer": result["answer"],
        "evidence": result["evidence"],
        "intent": result["intent"],
        "grounding_score": result["grounding_score"],
        "hallucination_detected": result["hallucination_detected"],
        "llm_enhanced": result["llm_enhanced"],
        "model": result["model"],
    }


@router.get("/status")
def ai_status(token: dict = Depends(verify_token)):
    llm_enabled = os.environ.get("LLM_ENABLED", "false").lower() == "true"
    model = os.environ.get("LLM_MODEL", "gpt-4o")
    llm_available = llm_enabled and bool(os.environ.get("OPENAI_API_KEY"))

    since = (datetime.now() - timedelta(hours=24)).isoformat()
    db = get_db()
    try:
        row = db.execute(
            """
            SELECT COUNT(*)                          AS total_calls,
                   COALESCE(AVG(latency_ms), 0)      AS avg_latency_ms,
                   COALESCE(AVG(grounding_score), 0) AS avg_grounding_score,
                   COALESCE(SUM(cost), 0)            AS total_cost,
                   COALESCE(SUM(tokens_in + tokens_out), 0) AS total_tokens
            FROM ai_calls_log WHERE created_at >= ?
            """,
            (since,),
        ).fetchone()
    finally:
        db.close()

    return {
        "llm_enabled": llm_enabled,
        "llm_available": llm_available,
        "model": model,
        "provider": "openai",
        "stats_24h": {
            "total_calls": int(row["total_calls"]),
            "avg_latency_ms": round(float(row["avg_latency_ms"]), 1),
            "avg_grounding_score": round(float(row["avg_grounding_score"]), 3),
            "total_cost": round(float(row["total_cost"]), 6),
            "total_tokens": int(row["total_tokens"]),
        },
    }


@router.get("/tools")
def ai_tools(token: dict = Depends(verify_token)):
    return list_tools()


@router.post("/challenge/generate")
def ai_challenge_generate(token: dict = Depends(verify_token)):
    user_id = token["sub"]
    challenges = generate_personal_challenges(user_id)
    return {
        "user_id": user_id,
        "challenges": challenges,
        "generated_at": datetime.now().isoformat(),
    }


@router.get("/leaderboard/{category}")
def ai_leaderboard(category: str, limit: int = 50, token: dict = Depends(verify_token)):
    try:
        board = get_category_leaderboard(category, limit)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    for entry in board:
        entry["is_current_user"] = entry["user_id"] == token["sub"]
    return board


@router.get("/recommendations")
def ai_recommendations(type: str = None, n: int = 5, token: dict = Depends(verify_token)):
    user_id = token["sub"]
    if type:
        if type not in RECOMMENDATION_TYPES:
            raise HTTPException(status_code=400, detail=f"Gecersiz tip: {type}")
        recs = {type: recommend(user_id, type, n)}
    else:
        recs = recommend_all(user_id, n)
    return {"user_id": user_id, "recommendations": recs}


@router.get("/memory/{user_id}")
def ai_memory(user_id: str, token: dict = Depends(verify_token)):
    # Admin her hafizayi gorebilir; kullanici sadece kendisininkini.
    if token.get("role") != "admin" and token["sub"] != user_id:
        raise HTTPException(status_code=403, detail="Bu hafizaya erisim yetkin yok")
    return {"user_id": user_id, "memory": memory_store.get(user_id)}
