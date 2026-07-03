"""Adapter layer for optional LLM enhancement of explanations.

The deterministic explanation engine always produces the authoritative
answer. Adapters may only rephrase that answer linguistically; on any
failure they return the original response unchanged, so the system works
identically with the LLM disabled, misconfigured, or unreachable.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from gamification_engine.ai.llm_client import (
    SYSTEM_PROMPT,
    build_user_prompt,
    call_gemini_api,
    call_openai_api,
)
from gamification_engine.config.llm_config import (
    LLMConfig,
    LLMProvider,
    llm_config_from_env,
)
from gamification_engine.domain.models import ExplanationResponse


class LLMAdapter(ABC):
    """Interface for optional LLM enhancement of explanation responses.

    Implementations must never change ``user_id``, ``question`` or
    ``evidence``, and must never make business decisions (points, badges,
    ranks). They may only replace ``answer`` with a rephrased version of
    the deterministic answer.
    """

    @abstractmethod
    def enhance(self, response: ExplanationResponse) -> ExplanationResponse:
        """Return the response, optionally with a rephrased answer.

        Args:
            response: Deterministic explanation produced by the rule-based
                engine.

        Returns:
            The enhanced response, or the original response unchanged when
            enhancement is unavailable or fails.
        """


class NoOpLLMAdapter(LLMAdapter):
    """Adapter used when the LLM layer is disabled.

    Guarantees byte-identical output to the deterministic engine.
    """

    def enhance(self, response: ExplanationResponse) -> ExplanationResponse:
        """Return the deterministic response unchanged."""

        return response


class _RephrasingLLMAdapter(LLMAdapter):
    """Base class for provider adapters with shared fallback behaviour."""

    def __init__(self, api_key: str, timeout_seconds: float = 5.0) -> None:
        self._api_key = api_key
        self._timeout_seconds = timeout_seconds

    @abstractmethod
    def _rephrase(self, user_prompt: str) -> str:
        """Call the provider and return the rephrased text.

        Raises:
            OSError: On connection errors or timeouts.
            ValueError: On unexpected response payloads.
        """

    def enhance(self, response: ExplanationResponse) -> ExplanationResponse:
        """Rephrase the answer, falling back to the original on failure."""

        user_prompt = build_user_prompt(
            question=response.question,
            deterministic_answer=response.answer,
            evidence=response.evidence,
        )

        try:
            rephrased = self._rephrase(user_prompt)
        except (OSError, ValueError):
            # OSError covers URLError, timeouts and connection resets;
            # ValueError covers JSON decoding and payload contract errors.
            # Any failure must fall back to the deterministic answer.
            return response

        if not rephrased:
            return response

        return ExplanationResponse(
            user_id=response.user_id,
            question=response.question,
            answer=rephrased,
            evidence=response.evidence,
        )


class GeminiLLMAdapter(_RephrasingLLMAdapter):
    """Adapter that rephrases answers via the Google Gemini API."""

    def _rephrase(self, user_prompt: str) -> str:
        return call_gemini_api(
            self._api_key,
            user_prompt,
            self._timeout_seconds,
        )


class OpenAILLMAdapter(_RephrasingLLMAdapter):
    """Adapter that rephrases answers via the OpenAI API."""

    def _rephrase(self, user_prompt: str) -> str:
        return call_openai_api(
            self._api_key,
            SYSTEM_PROMPT,
            user_prompt,
            self._timeout_seconds,
        )


def create_llm_adapter(config: LLMConfig) -> LLMAdapter:
    """Create the adapter matching the given configuration.

    Args:
        config: Resolved LLM configuration.

    Returns:
        A provider adapter when enabled and configured, otherwise a
        :class:`NoOpLLMAdapter`.
    """

    if not config.enabled or config.provider is None or not config.api_key:
        return NoOpLLMAdapter()

    if config.provider is LLMProvider.GEMINI:
        return GeminiLLMAdapter(config.api_key, config.timeout_seconds)

    return OpenAILLMAdapter(config.api_key, config.timeout_seconds)


def create_llm_adapter_from_env() -> LLMAdapter:
    """Create an adapter from environment variables.

    Environment reading is delegated to
    :func:`gamification_engine.config.llm_config.llm_config_from_env`,
    the single place where LLM environment variables are interpreted.
    """

    return create_llm_adapter(llm_config_from_env())
