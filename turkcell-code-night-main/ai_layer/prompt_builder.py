"""
AI Layer – Prompt Builder.

Constructs structured, LLM-ready prompts from classified intents,
gathered context data, and the original user question.  Produces
instruction-driven prompts that guide the language model to respond
accurately using the provided data.
"""

import json
from typing import Any


KNOWN_INTENTS = {"leaderboard", "badge", "points", "challenge", "notification"}

SYSTEM_INSTRUCTION = (
    "You are a gamification assistant. "
    "Answer strictly using the provided data."
)

RESPONSE_REQUIREMENTS = (
    "RESPONSE REQUIREMENTS:\n"
    "- Be concise\n"
    "- Use numbers from data\n"
    "- If data missing, explain clearly"
)


def _filter_none(data: dict[str, Any]) -> dict[str, Any]:
    """Recursively remove keys whose values are None.

    Args:
        data: The dictionary to filter.

    Returns:
        A new dictionary with all None values removed.
    """
    cleaned: dict[str, Any] = {}
    for key, value in data.items():
        if value is None:
            continue
        if isinstance(value, dict):
            filtered = _filter_none(value)
            if filtered:
                cleaned[key] = filtered
        else:
            cleaned[key] = value
    return cleaned


def build_prompt(
    intent: str,
    context: dict[str, Any],
    user_message: str = "",
) -> str:
    """Build a structured LLM-ready prompt from intent, context, and question.

    For known intents (leaderboard, badge, points, challenge,
    notification) this always returns a non-empty prompt containing
    the system instruction, intent label, user question, JSON context,
    and response requirements.

    For the ``"general"`` intent (or any unknown intent) an empty
    string is returned, signalling the caller to use a fallback.

    Args:
        intent: The classified intent string.
        context: A dictionary of context data gathered for this query.
        user_message: The original user question text.

    Returns:
        A structured prompt string, or empty string for general/unknown
        intents.
    """
    if intent not in KNOWN_INTENTS:
        return ""

    filtered_context = _filter_none(context)
    context_json = json.dumps(filtered_context, indent=2, ensure_ascii=False)

    prompt = (
        f"SYSTEM INSTRUCTION:\n"
        f"\"{SYSTEM_INSTRUCTION}\"\n"
        f"\n"
        f"INTENT:\n"
        f"{intent}\n"
        f"\n"
        f"USER QUESTION:\n"
        f"{user_message}\n"
        f"\n"
        f"CONTEXT DATA (JSON):\n"
        f"{context_json}\n"
        f"\n"
        f"{RESPONSE_REQUIREMENTS}"
    )

    return prompt
