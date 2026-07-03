"""Configuration for the optional LLM explanation-enhancement layer.

Environment variables are read here and nowhere else, so the rest of the
code base stays deterministic and testable with explicit configuration
objects.

Environment contract:
    GAMIFICATION_LLM_ENABLED:
        Optional kill switch. Set to ``0``, ``false``, ``no`` or ``off``
        (case-insensitive) to force the deterministic-only mode even when
        API keys are present. Any other value (or unset) leaves the layer
        enabled.
    GEMINI_API_KEY:
        API key for Google Gemini. Takes precedence over OpenAI when both
        keys are present.
    OPENAI_API_KEY:
        API key for OpenAI.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

_FALSY_VALUES = frozenset({"0", "false", "no", "off"})

DEFAULT_LLM_TIMEOUT_SECONDS = 5.0


class LLMProvider(StrEnum):
    """Supported LLM providers for explanation enhancement."""

    GEMINI = "GEMINI"
    OPENAI = "OPENAI"


@dataclass(frozen=True)
class LLMConfig:
    """Resolved configuration for the LLM enhancement layer.

    Attributes:
        enabled: Whether LLM enhancement may run at all. When ``False``
            the engine must behave exactly as if no LLM existed.
        provider: Selected provider, or ``None`` when no usable provider
            is configured.
        api_key: API key for the selected provider, or ``None``.
        timeout_seconds: HTTP timeout for provider calls.
    """

    enabled: bool
    provider: LLMProvider | None
    api_key: str | None
    timeout_seconds: float = DEFAULT_LLM_TIMEOUT_SECONDS


def llm_config_from_env(env: Mapping[str, str] | None = None) -> LLMConfig:
    """Build an :class:`LLMConfig` from environment variables.

    Args:
        env: Optional mapping used instead of ``os.environ`` (for tests).

    Returns:
        The resolved configuration. When the kill switch is active or no
        API key is present, ``enabled`` is ``False`` and no provider is
        selected.
    """

    source: Mapping[str, str] = os.environ if env is None else env

    enabled_raw = source.get("GAMIFICATION_LLM_ENABLED", "").strip().lower()
    kill_switch_active = enabled_raw in _FALSY_VALUES

    gemini_key = source.get("GEMINI_API_KEY", "").strip()
    openai_key = source.get("OPENAI_API_KEY", "").strip()

    if kill_switch_active or (not gemini_key and not openai_key):
        return LLMConfig(enabled=False, provider=None, api_key=None)

    if gemini_key:
        return LLMConfig(
            enabled=True,
            provider=LLMProvider.GEMINI,
            api_key=gemini_key,
        )
    return LLMConfig(
        enabled=True,
        provider=LLMProvider.OPENAI,
        api_key=openai_key,
    )
