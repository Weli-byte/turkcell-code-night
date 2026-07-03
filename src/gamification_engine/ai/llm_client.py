"""Optional LLM client integration using standard library HTTP requests."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

# ---------------------------------------------------------------------------
# Prompt Templates
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = (
    "Sen dijital video platformu oyunlaştırma asistanısın. Görevin, kural "
    "motorundan gelen deterministik teknik cevabı ve kanıtları kullanıcıya "
    "dostane, akıcı ve anlaşılır bir dilde açıklamaktır.\n\n"
    "Uyman gereken kesin kurallar:\n"
    "1. Kural motorunun kararını, sayısal verileri, tarihleri ve puanları "
    "asla değiştirme. Yeni kurallar veya veriler uydurma (halüsinasyon yapma).\n"
    "2. Cevabı daha akıcı, kibar ve doğal bir Türkçe ile yeniden ifade et.\n"
    "3. Kural motorunun cevabı bilinmeyen bir soru/hata mesajı ise, "
    "o mesajı bozmadan aynen koru veya dostane bir şekilde benzer biçimde "
    "uyar.\n"
    "4. Çıktı olarak sadece ama sadece yeniden yazılmış cevabı döndür, "
    "başka hiçbir açıklama, giriş veya geliş cümlesi ekleme."
)

USER_PROMPT_TEMPLATE = (
    "Kullanıcı Sorusu: {question}\n"
    "Kural Motoru Cevabı: {deterministic_answer}\n"
    "Teknik Kanıtlar (Evidence): {evidence}\n\n"
    "Lütfen yukarıdaki kurallara sadık kalarak cevabı Türkçe olarak yeniden yaz:"
)


# ---------------------------------------------------------------------------
# API Call Wrappers
# ---------------------------------------------------------------------------


def _post_https_json(
    url: str,
    headers: dict[str, str],
    body: dict[str, Any],
    timeout: float,
) -> dict[str, Any]:
    """POST a JSON payload to an HTTPS endpoint and parse the JSON response.

    Only the ``https`` scheme is accepted; any other scheme raises
    ``ValueError`` before a request is made.
    """

    if not url.startswith("https://"):
        raise ValueError(f"Only https:// URLs are allowed, got: {url}")

    # Scheme is validated as https above; file:// or custom schemes
    # are rejected before the request object is even built.
    req = urllib.request.Request(  # noqa: S310
        url,
        data=json.dumps(body).encode("utf-8"),
        headers=headers,
        method="POST",
    )

    # Scheme is validated as https above, so this cannot open
    # file:// or other unexpected schemes.
    with urllib.request.urlopen(req, timeout=timeout) as response:  # noqa: S310
        payload: dict[str, Any] = json.loads(response.read().decode("utf-8"))
        return payload


def _call_gemini_api(api_key: str, prompt: str, timeout: float = 5.0) -> str:
    """Call Google Gemini API using urllib."""

    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"gemini-2.5-flash:generateContent?key={api_key}"
    )
    headers = {"Content-Type": "application/json"}
    body = {
        "contents": [{"parts": [{"text": f"{SYSTEM_PROMPT}\n\n{prompt}"}]}],
        "generationConfig": {"temperature": 0.2},
    }

    res_data = _post_https_json(url, headers, body, timeout)
    # Extract text from Gemini structure
    candidates = res_data.get("candidates", [])
    if not candidates:
        raise ValueError("Gemini API returned no candidates.")
    parts = candidates[0].get("content", {}).get("parts", [])
    if not parts:
        raise ValueError("Gemini API candidate has no parts.")
    text = parts[0].get("text", "")
    return str(text).strip()


def _call_openai_api(
    api_key: str, system_prompt: str, user_prompt: str, timeout: float = 5.0
) -> str:
    """Call OpenAI API using urllib."""

    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    body = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.2,
    }

    res_data = _post_https_json(url, headers, body, timeout)
    choices = res_data.get("choices", [])
    if not choices:
        raise ValueError("OpenAI API returned no choices.")
    message = choices[0].get("message", {})
    content = message.get("content", "")
    return str(content).strip()


# ---------------------------------------------------------------------------
# Public Entry Point
# ---------------------------------------------------------------------------


def generate_llm_explanation(
    question: str,
    deterministic_answer: str,
    evidence: dict[str, Any],
    timeout: float = 5.0,
) -> str | None:
    """Rephrase deterministic explanation using an optional LLM.

    If GEMINI_API_KEY or OPENAI_API_KEY environment variables are present, this
    function queries the respective API. If no keys are set, or if the API call
    fails for any reason (network timeout, invalid key, etc.), it returns
    ``None``, signaling that the pipeline should fall back to the rule-based
    answer.

    Args:
        question: Original question asked by the user.
        deterministic_answer: Rule-based text answer.
        evidence: Evidence dictionary containing raw data facts.
        timeout: API call timeout in seconds.

    Returns:
        The LLM-rephrased explanation, or ``None`` if disabled/failed.
    """

    gemini_key = os.environ.get("GEMINI_API_KEY")
    openai_key = os.environ.get("OPENAI_API_KEY")

    if not gemini_key and not openai_key:
        return None

    user_prompt = USER_PROMPT_TEMPLATE.format(
        question=question,
        deterministic_answer=deterministic_answer,
        evidence=json.dumps(evidence, ensure_ascii=False),
    )

    try:
        if gemini_key:
            return _call_gemini_api(gemini_key, user_prompt, timeout)
        if openai_key:
            return _call_openai_api(openai_key, SYSTEM_PROMPT, user_prompt, timeout)
    except (urllib.error.URLError, ValueError, Exception):
        # Graceful fallback: return None on any connection error, timeout,
        # API failure, or bad response format.
        return None

    return None
