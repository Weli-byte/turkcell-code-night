"""Tests for backend settings and environment variable handling."""

from __future__ import annotations

import pytest

from gamification_backend.config import BackendSettings


def test_defaults_point_at_repo_paths() -> None:
    settings = BackendSettings()

    assert settings.database_url.startswith("sqlite:///")
    assert settings.database_url.endswith("gamification.db")
    assert settings.challenges_csv.name == "challenges.csv"
    assert settings.seed_on_startup is True


def test_env_variables_override_defaults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GAMIFICATION_BACKEND_DATABASE_URL", "sqlite://")
    monkeypatch.setenv("GAMIFICATION_BACKEND_SEED_ON_STARTUP", "0")

    settings = BackendSettings()

    assert settings.database_url == "sqlite://"
    assert settings.seed_on_startup is False


def test_unrelated_prefixed_env_vars_are_ignored(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GAMIFICATION_BACKEND_TOTALLY_UNKNOWN", "x")

    settings = BackendSettings()

    assert settings.seed_on_startup is True
