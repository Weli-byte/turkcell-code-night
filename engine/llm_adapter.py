"""
LLM Adapter — OpenAI GPT-4o entegrasyonu, TEK merkezi çağrı noktası.

Kurallar:
- API key varsa LLM otomatik aktif (LLM_ENABLED=false açıkça yazılırsa kapanır).
- LLM asla iş kararı vermez (puan/rozet/sıra); sadece deterministik motorun
  ürettiği gerçek veriyi doğal dile çevirir veya soruyu sınıflandırır.
- Her hata deterministik fallback'e düşer — sistem LLM'siz de çalışır.
- Bu modül dışında hiçbir dosya doğrudan OpenAI çağrısı yapmaz.
"""

import os
import json
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY  = os.environ.get("OPENAI_API_KEY", "")
# Kill switch: LLM_ENABLED=false açıkça yazılmadıkça key varsa LLM aktif.
LLM_ENABLED     = os.environ.get("LLM_ENABLED", "true").lower() != "false"
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


def is_llm_available() -> bool:
    return LLM_ENABLED and bool(OPENAI_API_KEY)


def llm_call(
    system: str,
    user: str,
    max_tokens: int | None = None,
    temperature: float | None = None,
    history: list[dict] | None = None,
) -> str | None:
    """
    Merkezi GPT-4o çağrısı. Tüm engine'ler bunu kullanır.
    history: çok turlu sohbet için önceki mesajlar
             [{"role": "user"|"assistant", "content": "..."}].
    LLM kapalı/hatalı → None döner; çağıran deterministik fallback uygular.
    """
    if not is_llm_available():
        return None
    try:
        from openai import OpenAI
        client   = OpenAI(api_key=OPENAI_API_KEY)
        messages = [{"role": "system", "content": system}]
        for m in (history or []):
            if m.get("role") in ("user", "assistant") and m.get("content"):
                messages.append({"role": m["role"], "content": m["content"]})
        messages.append({"role": "user", "content": user})
        resp = client.chat.completions.create(
            model       = LLM_MODEL,
            max_tokens  = max_tokens or LLM_MAX_TOKENS,
            temperature = LLM_TEMPERATURE if temperature is None else temperature,
            messages    = messages,
        )
        answer = (resp.choices[0].message.content or "").strip()
        return answer if answer else None
    except Exception:
        return None


def classify_intent_llm(question: str, valid_intents: list[str]) -> str | None:
    """
    Keyword eşleşmesi başarısız olduğunda GPT-4o soruyu sınıflandırır.
    Cevap listede yoksa None → deterministik 'general' fallback.
    """
    intents = ", ".join(valid_intents)
    result  = llm_call(
        system=(
            "Sen bir intent sınıflandırıcısın. Kullanıcının Türkçe sorusunu "
            "verilen kategorilerden birine ata. SADECE kategori adını yaz, "
            "başka hiçbir şey yazma."
        ),
        user=f"Kategoriler: {intents}\n\nSoru: {question}\n\nKategori:",
        max_tokens=12,
        temperature=0.0,
    )
    if result:
        cleaned = result.strip().lower().strip(".:\"' ")
        if cleaned in valid_intents:
            return cleaned
    return None


def enhance_with_llm(
    question: str,
    template_answer: str,
    evidence: dict,
    intent: str,
) -> dict:
    """Deterministik cevabı GPT-4o ile doğallaştırır. Hata → template."""
    user_msg = (
        f"Kullanıcı sorusu: {question}\n\n"
        f"Engine analizi:\n{template_answer}\n\n"
        f"Kanıt veriler (sayıları değiştirme):\n"
        f"{json.dumps(evidence, ensure_ascii=False, indent=2)}\n\n"
        f"Soruyu doğal Türkçeyle yanıtla. "
        f"Sayıları kesinlikle değiştirme. Maks 3 cümle."
    )
    answer = llm_call(SYSTEM_PROMPT, user_msg)

    if answer is None or len(answer) < 10:
        return {
            "answer":       template_answer,
            "llm_enhanced": False,
            "llm_error":    None if not is_llm_available() else "LLM cevabı alınamadı",
            "model":        "template" if not is_llm_available() else LLM_MODEL,
        }
    return {
        "answer":       answer,
        "llm_enhanced": True,
        "llm_error":    None,
        "model":        LLM_MODEL,
    }


def get_llm_status() -> dict:
    return {
        "llm_enabled":   LLM_ENABLED,
        "llm_available": is_llm_available(),
        "model":         LLM_MODEL,
        "provider":      "openai" if is_llm_available() else "template",
        "max_tokens":    LLM_MAX_TOKENS,
        "temperature":   LLM_TEMPERATURE,
    }
