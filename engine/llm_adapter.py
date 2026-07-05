"""
LLM Adapter — OpenAI GPT-4o entegrasyonu.
LLM sadece template cevabı doğal dile çevirir.
Hata olursa template döner, sistem çalışmaya devam eder.
"""

import os
import json
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY  = os.environ.get("OPENAI_API_KEY", "")
LLM_ENABLED     = os.environ.get("LLM_ENABLED", "false").lower() == "true"
LLM_MODEL       = os.environ.get("LLM_MODEL", "gpt-4o")
LLM_MAX_TOKENS  = int(os.environ.get("LLM_MAX_TOKENS", "300"))
LLM_TEMPERATURE = float(os.environ.get("LLM_TEMPERATURE", "0.4"))

SYSTEM_PROMPT = """Sen bir video platformu oyunlaştırma asistanısın.
Kullanıcının puan, rozet ve sıralama verilerine dayanarak
Türkçe, samimi ve motive edici cevaplar veriyorsun.

KESİN KURALLAR:
1. Verilen sayıları asla değiştirme
2. Sadece verilen evidence verilerini kullan
3. Kendi eklediğin veri olmasın
4. Maksimum 3 cümle
5. Samimi ve motive edici ton
6. Türkçe yaz"""


def enhance_with_llm(
    question: str,
    template_answer: str,
    evidence: dict,
    intent: str,
) -> dict:
    if not LLM_ENABLED or not OPENAI_API_KEY:
        return {
            "answer":       template_answer,
            "llm_enhanced": False,
            "llm_error":    None,
            "model":        "template",
        }
    try:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_API_KEY)

        user_msg = (
            f"Kullanıcı sorusu: {question}\n\n"
            f"Engine analizi:\n{template_answer}\n\n"
            f"Kanıt veriler (sayıları değiştirme):\n"
            f"{json.dumps(evidence, ensure_ascii=False, indent=2)}\n\n"
            f"Soruyu doğal Türkçeyle yanıtla. "
            f"Sayıları kesinlikle değiştirme. Maks 3 cümle."
        )

        resp = client.chat.completions.create(
            model       = LLM_MODEL,
            max_tokens  = LLM_MAX_TOKENS,
            temperature = LLM_TEMPERATURE,
            messages    = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": user_msg},
            ],
        )
        answer = resp.choices[0].message.content.strip()

        if len(answer) < 10:
            return {
                "answer":       template_answer,
                "llm_enhanced": False,
                "llm_error":    "Cevap çok kısa",
                "model":        LLM_MODEL,
            }

        return {
            "answer":       answer,
            "llm_enhanced": True,
            "llm_error":    None,
            "model":        LLM_MODEL,
        }

    except Exception as e:
        return {
            "answer":       template_answer,
            "llm_enhanced": False,
            "llm_error":    str(e),
            "model":        LLM_MODEL,
        }


def is_llm_available() -> bool:
    return LLM_ENABLED and bool(OPENAI_API_KEY)


def get_llm_status() -> dict:
    return {
        "llm_enabled":   LLM_ENABLED,
        "llm_available": is_llm_available(),
        "model":         LLM_MODEL,
        "provider":      "openai" if is_llm_available() else "template",
        "max_tokens":    LLM_MAX_TOKENS,
        "temperature":   LLM_TEMPERATURE,
    }
