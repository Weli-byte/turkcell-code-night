"""Tests for the CLI command-line interface."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from gamification_engine.cli.main import main
from gamification_engine.domain.errors import IngestionError
from gamification_engine.domain.models import ExplanationResponse
from gamification_engine.export.json_exporter import RunSummary


def test_cli_version_prints_package_version(capsys) -> None:  # type: ignore[no-untyped-def]
    """The CLI should expose the package version."""

    exit_code = main(["--version"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "gamification-engine 0.1.0" in captured.out


@patch("gamification_engine.cli.main.run_pipeline")
def test_cli_run_success(mock_run_pipeline, capsys) -> None:  # type: ignore[no-untyped-def]
    """The CLI run command should succeed and print execution details."""

    from datetime import date

    mock_summary = RunSummary(
        run_date=date(2026, 6, 15),
        total_users_processed=5,
        total_rewards_generated=2,
        total_ledger_entries=10,
        total_badges_assigned=3,
        total_notifications_created=7,
        leaderboard_size=5,
    )
    mock_run_pipeline.return_value = mock_summary

    exit_code = main(
        [
            "run",
            "--activities",
            "activities.csv",
            "--challenges",
            "challenges.csv",
            "--output-dir",
            "out/",
            "--run-date",
            "2026-06-15",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Pipeline completed successfully." in captured.out
    assert "Total Users Processed:     5" in captured.out
    assert "Total Rewards Generated:   2" in captured.out
    assert "Total Ledger Entries:      10" in captured.out
    assert "Total Badges Assigned:     3" in captured.out
    assert "Total Notifications:       7" in captured.out

    mock_run_pipeline.assert_called_once()
    context = mock_run_pipeline.call_args[0][0]
    assert context.activities_csv_path.name == "activities.csv"
    assert context.challenges_csv_path.name == "challenges.csv"
    assert context.output_dir.name == "out"
    assert context.run_date == date(2026, 6, 15)


def test_cli_run_invalid_date(capsys) -> None:  # type: ignore[no-untyped-def]
    """The CLI run command should fail when given an invalid date format."""

    exit_code = main(
        [
            "run",
            "--activities",
            "activities.csv",
            "--challenges",
            "challenges.csv",
            "--output-dir",
            "out/",
            "--run-date",
            "not-a-date",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "Error: Invalid run-date" in captured.err


@patch("gamification_engine.cli.main.run_pipeline")
def test_cli_run_pipeline_error(mock_run_pipeline, capsys) -> None:  # type: ignore[no-untyped-def]
    """The CLI should return 1 and print the error if pipeline raises an error."""

    mock_run_pipeline.side_effect = IngestionError("Header mismatch")

    exit_code = main(
        [
            "run",
            "--activities",
            "activities.csv",
            "--challenges",
            "challenges.csv",
            "--output-dir",
            "out/",
            "--run-date",
            "2026-06-15",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "Pipeline Error: Header mismatch" in captured.err


# ---------------------------------------------------------------------------
# Explain Subcommand Tests
# ---------------------------------------------------------------------------


@patch("gamification_engine.cli.main._load_states_json")
@patch("gamification_engine.cli.main.load_points_ledger_json")
@patch("gamification_engine.cli.main.load_badge_assignments_json")
@patch("gamification_engine.cli.main._load_leaderboard_json")
@patch("gamification_engine.cli.main._load_rewards_json")
@patch("gamification_engine.cli.main.load_challenge_definitions_csv")
@patch("gamification_engine.cli.main.explain_user_query")
@patch.dict("os.environ", {"GEMINI_API_KEY": "", "OPENAI_API_KEY": ""})
def test_cli_explain_text_format(
    mock_explain,
    mock_load_challenges,
    mock_load_rewards,
    mock_load_leaderboard,
    mock_load_badges,
    mock_load_ledger,
    mock_load_states,
    capsys,
) -> None:  # type: ignore[no-untyped-def]
    """The CLI explain command should print only the answer in text format by default."""

    mock_load_states.return_value = []
    mock_load_ledger.return_value = []
    mock_load_badges.return_value = []
    mock_load_leaderboard.return_value = []
    mock_load_rewards.return_value = []
    mock_load_challenges.return_value = []

    mock_explain.return_value = ExplanationResponse(
        user_id="u001",
        question="Kaç puanım var?",
        answer="Toplam 250 puanınız var.",
        evidence={"points": 250},
    )

    exit_code = main(
        [
            "explain",
            "--user-id",
            "u001",
            "--question",
            "Kaç puanım var?",
            "--output-dir",
            "out/",
            "--challenges",
            "challenges.csv",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.out.strip() == "Toplam 250 puanınız var."
    mock_explain.assert_called_once()


@patch("gamification_engine.cli.main._load_states_json")
@patch("gamification_engine.cli.main.load_points_ledger_json")
@patch("gamification_engine.cli.main.load_badge_assignments_json")
@patch("gamification_engine.cli.main._load_leaderboard_json")
@patch("gamification_engine.cli.main._load_rewards_json")
@patch("gamification_engine.cli.main.load_challenge_definitions_csv")
@patch("gamification_engine.cli.main.explain_user_query")
@patch.dict("os.environ", {"GEMINI_API_KEY": "", "OPENAI_API_KEY": ""})
def test_cli_explain_json_format(
    mock_explain,
    mock_load_challenges,
    mock_load_rewards,
    mock_load_leaderboard,
    mock_load_badges,
    mock_load_ledger,
    mock_load_states,
    capsys,
) -> None:  # type: ignore[no-untyped-def]
    """The CLI explain command should print full JSON response when format is 'json'."""

    mock_load_states.return_value = []
    mock_load_ledger.return_value = []
    mock_load_badges.return_value = []
    mock_load_leaderboard.return_value = []
    mock_load_rewards.return_value = []
    mock_load_challenges.return_value = []

    mock_explain.return_value = ExplanationResponse(
        user_id="u001",
        question="Kaç puanım var?",
        answer="Toplam 250 puanınız var.",
        evidence={"points": 250},
    )

    exit_code = main(
        [
            "explain",
            "--user-id",
            "u001",
            "--question",
            "Kaç puanım var?",
            "--output-dir",
            "out/",
            "--challenges",
            "challenges.csv",
            "--format",
            "json",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    data = json.loads(captured.out)
    assert data["user_id"] == "u001"
    assert data["question"] == "Kaç puanım var?"
    assert data["answer"] == "Toplam 250 puanınız var."
    assert data["evidence"]["points"] == 250


@patch("gamification_engine.cli.main._load_states_json")
@patch.dict("os.environ", {"GEMINI_API_KEY": "", "OPENAI_API_KEY": ""})
def test_cli_explain_load_error(mock_load_states, capsys) -> None:  # type: ignore[no-untyped-def]
    """The CLI explain command should fail cleanly and print the error if a load fails."""

    mock_load_states.side_effect = RuntimeError("Read error")

    exit_code = main(
        [
            "explain",
            "--user-id",
            "u001",
            "--question",
            "Kaç puanım var?",
            "--output-dir",
            "out/",
            "--challenges",
            "challenges.csv",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "Explain Error" in captured.err
