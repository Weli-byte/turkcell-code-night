"""Integration tests for the batch pipeline execution and CLI."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from gamification_engine.cli.main import main
from gamification_engine.orchestration.pipeline import run_pipeline
from gamification_engine.orchestration.run_context import RunContext


def test_pipeline_integration_runs_successfully_and_is_idempotent(tmp_path: Path) -> None:
    """The pipeline should execute end-to-end, write all outputs, and be idempotent."""

    fixtures_dir = Path(__file__).parent.parent / "fixtures"
    activities_csv = fixtures_dir / "valid_user_activities.csv"
    challenges_csv = fixtures_dir / "valid_challenges.csv"

    ctx = RunContext(
        activities_csv_path=activities_csv,
        challenges_csv_path=challenges_csv,
        output_dir=tmp_path,
        run_date=date(2026, 3, 9),
    )

    # 1. First Run: Execute pipeline
    summary = run_pipeline(ctx)

    # Check summary counts
    assert summary.run_date == date(2026, 3, 9)
    assert summary.total_users_processed == 2  # U1 and U2
    assert summary.total_rewards_generated == 1  # U1 completes C-02
    assert summary.total_ledger_entries == 1
    assert summary.total_badges_assigned == 0  # 140 points is < 500 threshold
    assert summary.total_notifications_created == 1
    assert summary.leaderboard_size == 1  # Only U1 has points (U2 doesn't trigger rewards)

    # Verify that all JSON output files exist
    expected_files = [
        "states.json",
        "rewards.json",
        "ledger.json",
        "badges.json",
        "leaderboard.json",
        "notifications.json",
        "run_summary.json",
    ]
    for filename in expected_files:
        assert (tmp_path / filename).exists(), f"{filename} does not exist"

    # Verify rewards
    rewards = json.loads((tmp_path / "rewards.json").read_text(encoding="utf-8"))
    assert len(rewards) == 1
    assert rewards[0]["user_id"] == "U1"
    assert rewards[0]["challenge_id"] == "C-02"
    assert rewards[0]["reward_points"] == 140
    # Daily Watcher (C-01) is suppressed because Episode Finisher (C-02) has priority 3 < 5
    assert rewards[0]["suppressed_challenge_ids"] == ["C-01"]

    # Verify points ledger
    ledger = json.loads((tmp_path / "ledger.json").read_text(encoding="utf-8"))
    assert len(ledger) == 1
    assert ledger[0]["user_id"] == "U1"
    assert ledger[0]["points_delta"] == 140
    assert ledger[0]["source_ref"] == rewards[0]["reward_id"]

    # Verify leaderboard
    leaderboard = json.loads((tmp_path / "leaderboard.json").read_text(encoding="utf-8"))
    assert len(leaderboard) == 1
    assert leaderboard[0]["user_id"] == "U1"
    assert leaderboard[0]["total_points"] == 140
    assert leaderboard[0]["rank"] == 1

    # Verify notifications
    notifications = json.loads((tmp_path / "notifications.json").read_text(encoding="utf-8"))
    assert len(notifications) == 1
    assert notifications[0]["user_id"] == "U1"
    assert "Challenge C-02 completed" in notifications[0]["message"]

    # 2. Second Run: Run the same pipeline again on the same output directory to test idempotency
    summary_run2 = run_pipeline(ctx)

    assert summary_run2.total_rewards_generated == 1  # Generates reward candidate again
    assert summary_run2.total_ledger_entries == 1  # Ledger should NOT duplicate the entry
    assert summary_run2.total_notifications_created == 1  # Notification should NOT duplicate


def test_cli_integration_run_command(tmp_path: Path) -> None:
    """The CLI run command should run successfully end-to-end."""

    fixtures_dir = Path(__file__).parent.parent / "fixtures"
    activities_csv = fixtures_dir / "valid_user_activities.csv"
    challenges_csv = fixtures_dir / "valid_challenges.csv"

    argv = [
        "run",
        "--activities",
        str(activities_csv),
        "--challenges",
        str(challenges_csv),
        "--output-dir",
        str(tmp_path),
        "--run-date",
        "2026-03-09",
    ]

    exit_code = main(argv)
    assert exit_code == 0

    assert (tmp_path / "run_summary.json").exists()
    summary = json.loads((tmp_path / "run_summary.json").read_text(encoding="utf-8"))
    assert summary["total_users_processed"] == 2
    assert summary["total_rewards_generated"] == 1
