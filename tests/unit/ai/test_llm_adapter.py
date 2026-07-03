"""Unit tests for the LLM adapter layer and its configuration."""

from __future__ import annotations

from unittest.mock import patch

from gamification_engine.ai.llm_adapter import (
    GeminiLLMAdapter,
    LLMAdapter,
    NoOpLLMAdapter,
    OpenAILLMAdapter,
    create_llm_adapter,
    create_llm_adapter_from_env,
)
from gamification_engine.config.llm_config import (
    LLMConfig,
    LLMProvider,
    llm_config_from_env,
)
from gamification_engine.domain.models import ExplanationResponse


def _response() -> ExplanationResponse:
    return ExplanationResponse(
        user_id="u001",
        question="Kaç puanım var?",
        answer="Toplam 250 puanınız var.",
        evidence={"points": 250},
    )


class FakeLLMAdapter(LLMAdapter):
    """Test double that records calls and returns a canned answer."""

    def __init__(self, answer: str) -> None:
        self.answer = answer
        self.calls: list[ExplanationResponse] = []

    def enhance(self, response: ExplanationResponse) -> ExplanationResponse:
        self.calls.append(response)
        return ExplanationResponse(
            user_id=response.user_id,
            question=response.question,
            answer=self.answer,
            evidence=response.evidence,
        )


# ---------------------------------------------------------------------------
# NoOp and Fake adapters
# ---------------------------------------------------------------------------


def test_noop_adapter_returns_response_unchanged() -> None:
    """NoOpLLMAdapter must return the exact same response object."""

    response = _response()
    assert NoOpLLMAdapter().enhance(response) is response


def test_fake_adapter_preserves_identity_fields() -> None:
    """A conforming adapter only replaces the answer text."""

    fake = FakeLLMAdapter(answer="Daha doğal bir cevap.")
    response = _response()

    enhanced = fake.enhance(response)

    assert fake.calls == [response]
    assert enhanced.answer == "Daha doğal bir cevap."
    assert enhanced.user_id == response.user_id
    assert enhanced.question == response.question
    assert enhanced.evidence == response.evidence


# ---------------------------------------------------------------------------
# Provider adapters: success and fallback
# ---------------------------------------------------------------------------


@patch("gamification_engine.ai.llm_adapter.call_gemini_api")
def test_gemini_adapter_rephrases_answer(mock_call) -> None:  # type: ignore[no-untyped-def]
    """GeminiLLMAdapter should replace only the answer text on success."""

    mock_call.return_value = "Yeniden yazılmış cevap."
    adapter = GeminiLLMAdapter(api_key="key", timeout_seconds=1.0)
    response = _response()

    enhanced = adapter.enhance(response)

    assert enhanced.answer == "Yeniden yazılmış cevap."
    assert enhanced.user_id == response.user_id
    assert enhanced.question == response.question
    assert enhanced.evidence == response.evidence
    mock_call.assert_called_once()


@patch("gamification_engine.ai.llm_adapter.call_openai_api")
def test_openai_adapter_rephrases_answer(mock_call) -> None:  # type: ignore[no-untyped-def]
    """OpenAILLMAdapter should replace only the answer text on success."""

    mock_call.return_value = "OpenAI cevabı."
    adapter = OpenAILLMAdapter(api_key="key", timeout_seconds=1.0)

    enhanced = adapter.enhance(_response())

    assert enhanced.answer == "OpenAI cevabı."
    mock_call.assert_called_once()


@patch("gamification_engine.ai.llm_adapter.call_gemini_api")
def test_adapter_falls_back_on_connection_error(mock_call) -> None:  # type: ignore[no-untyped-def]
    """Connection failures must return the deterministic response."""

    mock_call.side_effect = TimeoutError("Connection timed out")
    adapter = GeminiLLMAdapter(api_key="key")
    response = _response()

    assert adapter.enhance(response) is response


@patch("gamification_engine.ai.llm_adapter.call_gemini_api")
def test_adapter_falls_back_on_payload_error(mock_call) -> None:  # type: ignore[no-untyped-def]
    """Malformed provider payloads must return the deterministic response."""

    mock_call.side_effect = ValueError("Gemini API returned no candidates.")
    adapter = GeminiLLMAdapter(api_key="key")
    response = _response()

    assert adapter.enhance(response) is response


@patch("gamification_engine.ai.llm_adapter.call_gemini_api")
def test_adapter_falls_back_on_empty_rephrasing(mock_call) -> None:  # type: ignore[no-untyped-def]
    """An empty LLM answer must not replace the deterministic answer."""

    mock_call.return_value = ""
    adapter = GeminiLLMAdapter(api_key="key")
    response = _response()

    assert adapter.enhance(response) is response


# ---------------------------------------------------------------------------
# Factory and configuration
# ---------------------------------------------------------------------------


def test_factory_returns_noop_when_disabled() -> None:
    """A disabled config must always produce a NoOp adapter."""

    config = LLMConfig(enabled=False, provider=None, api_key=None)
    assert isinstance(create_llm_adapter(config), NoOpLLMAdapter)


def test_factory_returns_noop_without_api_key() -> None:
    """Enabled config without an API key must fall back to NoOp."""

    config = LLMConfig(enabled=True, provider=LLMProvider.GEMINI, api_key=None)
    assert isinstance(create_llm_adapter(config), NoOpLLMAdapter)


def test_factory_selects_gemini_adapter() -> None:
    """A Gemini config must produce a Gemini adapter."""

    config = LLMConfig(enabled=True, provider=LLMProvider.GEMINI, api_key="k")
    assert isinstance(create_llm_adapter(config), GeminiLLMAdapter)


def test_factory_selects_openai_adapter() -> None:
    """An OpenAI config must produce an OpenAI adapter."""

    config = LLMConfig(enabled=True, provider=LLMProvider.OPENAI, api_key="k")
    assert isinstance(create_llm_adapter(config), OpenAILLMAdapter)


def test_config_from_env_defaults_to_disabled() -> None:
    """No API keys means the LLM layer is disabled."""

    config = llm_config_from_env(env={})

    assert config.enabled is False
    assert config.provider is None
    assert config.api_key is None


def test_config_from_env_gemini_takes_precedence() -> None:
    """When both keys are present, Gemini is the selected provider."""

    config = llm_config_from_env(
        env={"GEMINI_API_KEY": "g-key", "OPENAI_API_KEY": "o-key"}
    )

    assert config.enabled is True
    assert config.provider is LLMProvider.GEMINI
    assert config.api_key == "g-key"


def test_config_from_env_selects_openai_without_gemini() -> None:
    """OpenAI is selected when it is the only configured provider."""

    config = llm_config_from_env(env={"OPENAI_API_KEY": "o-key"})

    assert config.provider is LLMProvider.OPENAI
    assert config.api_key == "o-key"


def test_config_from_env_kill_switch_overrides_keys() -> None:
    """GAMIFICATION_LLM_ENABLED=0 disables the layer despite API keys."""

    config = llm_config_from_env(
        env={
            "GAMIFICATION_LLM_ENABLED": "0",
            "GEMINI_API_KEY": "g-key",
            "OPENAI_API_KEY": "o-key",
        }
    )

    assert config.enabled is False
    assert config.provider is None


def test_config_from_env_kill_switch_accepts_word_forms() -> None:
    """false/no/off variants of the kill switch are honoured."""

    for value in ("false", "NO", "Off"):
        config = llm_config_from_env(
            env={"GAMIFICATION_LLM_ENABLED": value, "GEMINI_API_KEY": "k"}
        )
        assert config.enabled is False


@patch.dict(
    "os.environ",
    {"GEMINI_API_KEY": "", "OPENAI_API_KEY": "", "GAMIFICATION_LLM_ENABLED": ""},
)
def test_create_adapter_from_env_without_keys_is_noop() -> None:
    """The env factory yields NoOp when nothing is configured."""

    assert isinstance(create_llm_adapter_from_env(), NoOpLLMAdapter)


@patch.dict(
    "os.environ",
    {"GEMINI_API_KEY": "g-key", "OPENAI_API_KEY": "", "GAMIFICATION_LLM_ENABLED": ""},
)
def test_create_adapter_from_env_with_gemini_key() -> None:
    """The env factory yields a Gemini adapter when the key is present."""

    assert isinstance(create_llm_adapter_from_env(), GeminiLLMAdapter)
