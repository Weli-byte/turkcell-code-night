"""
api/routers/ai_stream.py — Gercek GPT-4o streaming (SSE) + multi-agent endpoint.

Akis: intent -> evidence -> GPT-4o stream chunk'lari -> grounding -> memory -> done.
Her chunk OpenAI stream API'sinden gelir; yapay gecikme/daktilografi efekti yoktur.

GUVENLIK NOTU (bilincli tradeoff): EventSource header tasiyamaz; plan geregi token
query parametresiyle gelir ve sunucu loglarina dusebilir. Production'da kisa omurlu
tek kullanimlik SSE nonce'u kullanilmali.
"""

import os
import json

import jwt as pyjwt
from dotenv import load_dotenv
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from openai import OpenAI

from engine.explanation_engine import (
    detect_intent, gather_evidence, build_grounded_answer, check_grounding,
)
from engine.memory_store import update as mem_update
from api.auth_utils import SECRET_KEY, ALGORITHM, verify_token

load_dotenv()

router = APIRouter(tags=["ai-stream"])

LLM_MODEL = os.environ.get("LLM_MODEL", "gpt-4o")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

_SYSTEM_PROMPT = (
    "Sen bir video platformu oyunlastirma asistanisin. "
    "SADECE verilen evidence verilerini kullan. "
    "Sayilari degistirme. Maksimum 3 cumle. Turkce yaz."
)


def _sse(event: str, data) -> str:
    """Tek SSE veri satiri: data: {"event":..., "data":...}\\n\\n"""
    return f'data: {json.dumps({"event": event, "data": data}, ensure_ascii=False)}\n\n'


@router.get("/stream")
async def ai_stream(question: str, token: str):
    # Token query param'dan dogrulanir (EventSource header tasiyamaz).
    try:
        payload = pyjwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload["sub"]
    except pyjwt.InvalidTokenError:
        async def auth_error():
            yield _sse("error", "Gecersiz token")
            yield _sse("done", "[DONE]")
        return StreamingResponse(auth_error(), media_type="text/event-stream")

    async def generate(question: str, user_id: str):
        # ADIM 1 — Intent (LLM ile)
        intent = detect_intent(question, user_id)
        yield _sse("intent", intent)

        # ADIM 2 — Evidence (DB'den)
        evidence = gather_evidence(intent, user_id)
        yield _sse("evidence", evidence)

        # ADIM 3 — GPT-4o gercek stream
        if not OPENAI_API_KEY:
            yield _sse("chunk", "LLM anahtari tanimli degil.")
            yield _sse("done", "[DONE]")
            return

        client = OpenAI(api_key=OPENAI_API_KEY)
        stream = client.chat.completions.create(
            model=LLM_MODEL,
            stream=True,
            max_tokens=300,
            temperature=0.4,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": (
                    f"Soru: {question}\n"
                    f"Evidence (bu verileri kullan, sayilari degistirme):\n"
                    f"{json.dumps(evidence, ensure_ascii=False)}"
                )},
            ],
        )

        full_answer = ""
        for chunk in stream:
            delta = chunk.choices[0].delta.content if chunk.choices else None
            if delta:
                full_answer += delta
                yield _sse("chunk", delta)

        # ADIM 4 — Grounding kontrolu
        evaluation = check_grounding(full_answer, evidence)
        yield _sse("grounding", {
            "score": evaluation["grounding"],
            "hallucination": evaluation["hallucination_detected"],
        })

        # ADIM 5 — Memory guncelle (Learning)
        mem_update(user_id, "last_question", question)
        mem_update(user_id, "last_intent", intent)

        # ADIM 6 — Done
        yield _sse("done", "[DONE]")

    return StreamingResponse(
        generate(question, user_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


class AgentBody(BaseModel):
    question: str
    context: dict = None


@router.post("/agent")
def ai_agent(body: AgentBody, token: dict = Depends(verify_token)):
    """Multi-agent akis: Intent -> Evidence -> Response -> Evaluation -> Memory."""
    user_id = token["sub"]

    intent = detect_intent(body.question, user_id)                              # Intent Agent
    evidence = gather_evidence(intent, user_id)                                 # Evidence Agent
    answer = build_grounded_answer(body.question, intent, evidence, user_id)    # Response Agent (stream=False)
    evaluation = check_grounding(answer, evidence)                              # Evaluation Agent
    mem_update(user_id, "last_question", body.question)                         # Memory Agent
    mem_update(user_id, "last_intent", intent)

    return {
        "answer": answer,
        "intent": intent,
        "evidence": evidence,
        "grounding_score": evaluation["grounding"],
        "hallucination_detected": evaluation["hallucination_detected"],
        "agents_used": [
            "intent_agent", "evidence_agent", "response_agent",
            "evaluation_agent", "memory_agent",
        ],
        "model": LLM_MODEL,
        "llm_enhanced": True,
    }
