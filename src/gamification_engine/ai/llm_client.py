"""HTTP transport and prompt contract for optional LLM providers.

This module only knows how to talk to provider APIs. Provider selection,
enablement, and fallback behaviour live in
:mod:`gamification_engine.ai.llm_adapter`.
"""

from __future__ import annotations

import json
import urllib.request
from typing import Any

# ---------------------------------------------------------------------------
# Prompt Contract
# ---------------------------------------------------------------------------
# The system prompt is the guardrail: the LLM may only rephrase the
# deterministic answer. It must never invent, alter, or decide anything.
# See docs/ai_layer.md for the full contract.

SYSTEM_PROMPT = (
    "Sen dijital video platformu oyunlaştırma asistanısın. Görevin, kural "
    "motorundan gelen deterministik teknik cevabı ve kanıtları kullanıcıya "
    "dostane, akıcı ve anlaşılır bir dilde açıklamaktır.\n\n"
    "Uyman gereken kesin kurallar:\n"
    "1. Kural motorunun kararını, sayısal verileri, tarihleri ve puanları "
    "asla değiştirme. Yeni kurallar veya veriler uydurma (halüsinasyon "
    "yapma).\n"
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


def build_user_prompt(
    question: str,
    deterministic_answer: str,
    evidence: dict[str, Any],
) -> str:
    """Render the user prompt for a rephrasing request.

    Args:
        question: Original question asked by the user.
        deterministic_answer: Rule-based text answer to be rephrased.
        evidence: Evidence dictionary containing raw data facts.

    Returns:
        The formatted user prompt.
    """

    return USER_PROMPT_TEMPLATE.format(
        question=question,
        deterministic_answer=deterministic_answer,
        evidence=json.dumps(evidence, ensure_ascii=False),
    )


# ---------------------------------------------------------------------------
# HTTP helpers
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


# ---------------------------------------------------------------------------
# Provider calls
# ---------------------------------------------------------------------------


def call_gemini_api(api_key: str, prompt: str, timeout: float = 5.0) -> str:
    """Call Google Gemini API and return the rephrased text.

    Raises:
        ValueError: If the response payload does not contain a candidate.
        OSError: On connection errors or timeouts.
    """

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
    candidates = res_data.get("candidates", [])
    if not candidates:
        raise ValueError("Gemini API returned no candidates.")
    parts = candidates[0].get("content", {}).get("parts", [])
    if not parts:
        raise ValueError("Gemini API candidate has no parts.")
    text = parts[0].get("text", "")
    return str(text).strip()


def call_openai_api(
    api_key: str,
    system_prompt: str,
    user_prompt: str,
    timeout: float = 5.0,
) -> str:
    """Call OpenAI API and return the rephrased text.

    Raises:
        ValueError: If the response payload does not contain a choice.
        OSError: On connection errors or timeouts.
    """

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
