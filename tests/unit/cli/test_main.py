"""Tests for the CLI command-line interface."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from gamification_engine.cli.main import main
from gamification_engine.domain.errors import IngestionError
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
