"""Unit tests for the optional LLM client layer."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from gamification_engine.ai.llm_client import generate_llm_explanation


@patch("urllib.request.urlopen")
@patch.dict(
    "os.environ",
    {"GEMINI_API_KEY": "fake-gemini-key", "OPENAI_API_KEY": ""},
)
def test_gemini_api_call_success(mock_urlopen) -> None:
    """generate_llm_explanation should parse a successful Gemini JSON response."""

    # Set up mock response stream
    mock_response = MagicMock()
    mock_response.read.return_value = json.dumps(
        {
            "candidates": [
                {"content": {"parts": [{"text": "LLM-rewritten Turkish answer."}]}}
            ]
        }
    ).encode("utf-8")
    mock_urlopen.return_value.__enter__.return_value = mock_response

    res = generate_llm_explanation(
        question="Kaç puanım var?",
        deterministic_answer="Toplam 250 puanınız var.",
        evidence={"points": 250},
    )

    assert res == "LLM-rewritten Turkish answer."
    mock_urlopen.assert_called_once()
    req = mock_urlopen.call_args[0][0]
    assert "generativelanguage.googleapis.com" in req.full_url
    assert "fake-gemini-key" in req.full_url


@patch("urllib.request.urlopen")
@patch.dict(
    "os.environ",
    {"OPENAI_API_KEY": "fake-openai-key", "GEMINI_API_KEY": ""},
)
def test_openai_api_call_success(mock_urlopen) -> None:
    """generate_llm_explanation should parse a successful OpenAI JSON response."""

    # Set up mock response stream
    mock_response = MagicMock()
    mock_response.read.return_value = json.dumps(
        {
            "choices": [
                {"message": {"role": "assistant", "content": "OpenAI answer."}}
            ]
        }
    ).encode("utf-8")
    mock_urlopen.return_value.__enter__.return_value = mock_response

    res = generate_llm_explanation(
        question="Kaç puanım var?",
        deterministic_answer="Toplam 250 puanınız var.",
        evidence={"points": 250},
    )

    assert res == "OpenAI answer."
    mock_urlopen.assert_called_once()
    req = mock_urlopen.call_args[0][0]
    assert "api.openai.com" in req.full_url
    assert req.headers["Authorization"] == "Bearer fake-openai-key"


@patch.dict("os.environ", {"GEMINI_API_KEY": "", "OPENAI_API_KEY": ""})
def test_fallback_when_no_api_keys_are_set() -> None:
    """generate_llm_explanation should return None immediately if no keys exist."""

    res = generate_llm_explanation(
        question="Kaç puanım var?",
        deterministic_answer="Toplam 250 puanınız var.",
        evidence={"points": 250},
    )

    assert res is None


@patch("urllib.request.urlopen")
@patch.dict(
    "os.environ",
    {"GEMINI_API_KEY": "fake-gemini-key", "OPENAI_API_KEY": ""},
)
def test_fallback_on_api_errors(mock_urlopen) -> None:
    """generate_llm_explanation should return None on any connection failure."""

    # Mock connection timeout
    mock_urlopen.side_effect = TimeoutError("Connection timed out")

    res = generate_llm_explanation(
        question="Kaç puanım var?",
        deterministic_answer="Toplam 250 puanınız var.",
        evidence={"points": 250},
    )

    assert res is None


@patch("urllib.request.urlopen")
@patch.dict(
    "os.environ",
    {"GEMINI_API_KEY": "fake-gemini-key", "OPENAI_API_KEY": ""},
)
def test_fallback_on_invalid_response_format(mock_urlopen) -> None:
    """generate_llm_explanation should return None if the JSON format is invalid."""

    mock_response = MagicMock()
    mock_response.read.return_value = b"invalid json"
    mock_urlopen.return_value.__enter__.return_value = mock_response

    res = generate_llm_explanation(
        question="Kaç puanım var?",
        deterministic_answer="Toplam 250 puanınız var.",
        evidence={"points": 250},
    )

    assert res is None
