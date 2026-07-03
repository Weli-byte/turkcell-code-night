"""Unit tests for CLI run-command error handling paths."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from gamification_engine.cli.main import main


def _run_args(tmp_path: Path, activities: str = "missing.csv") -> list[str]:
    return [
        "run",
        "--activities",
        activities,
        "--challenges",
        "challenges.csv",
        "--output-dir",
        str(tmp_path),
        "--run-date",
        "2026-03-09",
    ]


def test_run_reports_pipeline_error_with_exit_code_1(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A missing input file must yield exit code 1 and a pipeline error."""

    exit_code = main(_run_args(tmp_path))

    assert exit_code == 1
    assert "Pipeline Error" in capsys.readouterr().err


@patch("gamification_engine.cli.main.run_pipeline")
def test_run_reports_unexpected_error_with_exit_code_1(
    mock_run_pipeline,  # type: ignore[no-untyped-def]
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A non-domain exception must be reported as unexpected."""

    mock_run_pipeline.side_effect = RuntimeError("boom")

    exit_code = main(_run_args(tmp_path))

    assert exit_code == 1
    assert "Unexpected Error" in capsys.readouterr().err
