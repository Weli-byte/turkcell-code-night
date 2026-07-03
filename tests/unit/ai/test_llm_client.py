"""Unit tests for the LLM HTTP transport layer."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from gamification_engine.ai.llm_client import (
    build_user_prompt,
    call_gemini_api,
    call_openai_api,
)


def _mock_http_response(payload: bytes) -> MagicMock:
    mock_response = MagicMock()
    mock_response.read.return_value = payload
    return mock_response


def test_build_user_prompt_embeds_question_answer_and_evidence() -> None:
    """The user prompt should contain all deterministic inputs verbatim."""

    prompt = build_user_prompt(
        question="Kaç puanım var?",
        deterministic_answer="Toplam 250 puanınız var.",
        evidence={"points": 250},
    )

    assert "Kaç puanım var?" in prompt
    assert "Toplam 250 puanınız var." in prompt
    assert '"points": 250' in prompt


@patch("urllib.request.urlopen")
def test_gemini_api_call_success(mock_urlopen) -> None:  # type: ignore[no-untyped-def]
    """call_gemini_api should parse a successful Gemini JSON response."""

    payload = json.dumps(
        {"candidates": [{"content": {"parts": [{"text": "LLM answer."}]}}]}
    ).encode("utf-8")
    mock_urlopen.return_value.__enter__.return_value = _mock_http_response(payload)

    res = call_gemini_api("fake-gemini-key", "prompt")

    assert res == "LLM answer."
    mock_urlopen.assert_called_once()
    req = mock_urlopen.call_args[0][0]
    assert "generativelanguage.googleapis.com" in req.full_url
    assert "fake-gemini-key" in req.full_url


@patch("urllib.request.urlopen")
def test_openai_api_call_success(mock_urlopen) -> None:  # type: ignore[no-untyped-def]
    """call_openai_api should parse a successful OpenAI JSON response."""

    payload = json.dumps(
        {"choices": [{"message": {"role": "assistant", "content": "OpenAI answer."}}]}
    ).encode("utf-8")
    mock_urlopen.return_value.__enter__.return_value = _mock_http_response(payload)

    res = call_openai_api("fake-openai-key", "system", "user prompt")

    assert res == "OpenAI answer."
    mock_urlopen.assert_called_once()
    req = mock_urlopen.call_args[0][0]
    assert "api.openai.com" in req.full_url
    assert req.headers["Authorization"] == "Bearer fake-openai-key"


@patch("urllib.request.urlopen")
def test_gemini_api_raises_on_empty_candidates(mock_urlopen) -> None:  # type: ignore[no-untyped-def]
    """call_gemini_api should raise ValueError when no candidates exist."""

    payload = json.dumps({"candidates": []}).encode("utf-8")
    mock_urlopen.return_value.__enter__.return_value = _mock_http_response(payload)

    with pytest.raises(ValueError, match="no candidates"):
        call_gemini_api("fake-key", "prompt")


@patch("urllib.request.urlopen")
def test_openai_api_raises_on_empty_choices(mock_urlopen) -> None:  # type: ignore[no-untyped-def]
    """call_openai_api should raise ValueError when no choices exist."""

    payload = json.dumps({"choices": []}).encode("utf-8")
    mock_urlopen.return_value.__enter__.return_value = _mock_http_response(payload)

    with pytest.raises(ValueError, match="no choices"):
        call_openai_api("fake-key", "system", "user")


@patch("urllib.request.urlopen")
def test_invalid_json_response_raises_value_error(mock_urlopen) -> None:  # type: ignore[no-untyped-def]
    """A malformed JSON payload should surface as a ValueError subclass."""

    mock_urlopen.return_value.__enter__.return_value = _mock_http_response(
        b"invalid json"
    )

    with pytest.raises(ValueError):
        call_gemini_api("fake-key", "prompt")


def test_non_https_url_is_rejected_before_any_request() -> None:
    """The transport helper must reject non-https schemes."""

    from gamification_engine.ai.llm_client import _post_https_json

    with pytest.raises(ValueError, match="Only https"):
        _post_https_json("file:///etc/passwd", {}, {}, timeout=1.0)
