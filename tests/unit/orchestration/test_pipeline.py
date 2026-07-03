"""Tests for pipeline orchestration and run context."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from gamification_engine.domain.errors import IngestionError, GamificationEngineError
from gamification_engine.orchestration.pipeline import run_pipeline
from gamification_engine.orchestration.run_context import RunContext


# ---------------------------------------------------------------------------
# RunContext Tests
# ---------------------------------------------------------------------------


class TestRunContext:
    """Tests for ``RunContext`` model."""

    def test_run_context_initialization_with_defaults(self) -> None:
        """RunContext should resolve paths and set correct default history paths."""

        ctx = RunContext(
            activities_csv_path="activities.csv",
            challenges_csv_path="challenges.csv",
            output_dir="out_dir",
            run_date=date(2026, 6, 15),
        )

        assert ctx.activities_csv_path == Path("activities.csv")
        assert ctx.challenges_csv_path == Path("challenges.csv")
        assert ctx.output_dir == Path("out_dir")
        assert ctx.run_date == date(2026, 6, 15)
        assert ctx.existing_ledger_path == Path("out_dir/ledger.json")
        assert ctx.existing_badges_path == Path("out_dir/badges.json")
        assert ctx.existing_notifications_path == Path("out_dir/notifications.json")

    def test_run_context_initialization_with_custom_history_paths(self) -> None:
        """RunContext should preserve custom history paths when provided."""

        ctx = RunContext(
            activities_csv_path="activities.csv",
            challenges_csv_path="challenges.csv",
            output_dir="out_dir",
            run_date=date(2026, 6, 15),
            existing_ledger_path="custom_ledger.json",
            existing_badges_path="custom_badges.json",
            existing_notifications_path="custom_notifications.json",
        )

        assert ctx.existing_ledger_path == Path("custom_ledger.json")
        assert ctx.existing_badges_path == Path("custom_badges.json")
        assert ctx.existing_notifications_path == Path("custom_notifications.json")


# ---------------------------------------------------------------------------
# run_pipeline Tests
# ---------------------------------------------------------------------------


@patch("gamification_engine.orchestration.pipeline.load_user_activities_csv")
@patch("gamification_engine.orchestration.pipeline.load_challenge_definitions_csv")
@patch("gamification_engine.orchestration.pipeline.load_points_ledger_json")
@patch("gamification_engine.orchestration.pipeline.load_badge_assignments_json")
@patch("gamification_engine.orchestration.pipeline.load_notifications_json")
@patch("gamification_engine.orchestration.pipeline.build_daily_user_states")
@patch("gamification_engine.orchestration.pipeline.evaluate_challenges_for_state")
@patch("gamification_engine.orchestration.pipeline.select_reward")
@patch("gamification_engine.orchestration.pipeline.append_reward_events")
@patch("gamification_engine.orchestration.pipeline.calculate_total_points")
@patch("gamification_engine.orchestration.pipeline.assign_badges")
@patch("gamification_engine.orchestration.pipeline.build_leaderboard")
@patch("gamification_engine.orchestration.pipeline.create_notifications")
@patch("gamification_engine.orchestration.pipeline.export_all")
def test_run_pipeline_success(
    mock_export_all,
    mock_create_notifications,
    mock_build_leaderboard,
    mock_assign_badges,
    mock_calculate_total_points,
    mock_append_reward_events,
    mock_select_reward,
    mock_evaluate_challenges,
    mock_build_states,
    mock_load_notifications,
    mock_load_badges,
    mock_load_ledger,
    mock_load_challenges,
    mock_load_activities,
) -> None:
    """The pipeline should orchestrate all components in order and return a RunSummary."""

    # Set up mocks
    mock_load_activities.return_value = ["activity1", "activity2"]
    mock_load_challenges.return_value = ["challenge1"]
    mock_load_ledger.return_value = ["ledger1"]
    mock_load_badges.return_value = ["badge1"]
    mock_load_notifications.return_value = ["notif1"]

    mock_state = MagicMock()
    mock_state.user_id = "user1"
    mock_build_states.return_value = [mock_state]

    mock_evaluate_challenges.return_value = ["challenge1"]
    mock_reward = MagicMock()
    mock_reward.user_id = "user1"
    mock_reward.reward_points = 50
    mock_select_reward.return_value = mock_reward

    mock_append_reward_events.return_value = ["ledger1", "ledger2"]
    mock_calculate_total_points.return_value = {"user1": 150}
    mock_assign_badges.return_value = (["new_badge"], ["badge1", "new_badge"])
    mock_build_leaderboard.return_value = ["leader1"]
    mock_create_notifications.return_value = ["notif1", "new_notif"]

    ctx = RunContext(
        activities_csv_path="activities.csv",
        challenges_csv_path="challenges.csv",
        output_dir="out_dir",
        run_date=date(2026, 6, 15),
    )

    summary = run_pipeline(ctx)

    # Verify calls
    mock_load_activities.assert_called_once_with(Path("activities.csv"))
    mock_load_challenges.assert_called_once_with(Path("challenges.csv"))
    mock_load_ledger.assert_called_once_with(Path("out_dir/ledger.json"))
    mock_load_badges.assert_called_once_with(Path("out_dir/badges.json"))
    mock_load_notifications.assert_called_once_with(Path("out_dir/notifications.json"))
    mock_build_states.assert_called_once_with(["activity1", "activity2"], date(2026, 6, 15))
    mock_evaluate_challenges.assert_called_once_with(mock_state, ["challenge1"])
    mock_select_reward.assert_called_once_with("user1", date(2026, 6, 15), ["challenge1"])
    mock_append_reward_events.assert_called_once_with(["ledger1"], [mock_reward])
    mock_calculate_total_points.assert_called_once_with(["ledger1", "ledger2"])
    mock_assign_badges.assert_called_once_with({"user1": 150}, ["badge1"], date(2026, 6, 15))
    mock_build_leaderboard.assert_called_once_with({"user1": 150}, ["badge1", "new_badge"])
    mock_create_notifications.assert_called_once_with([mock_reward], ["new_badge"], ["notif1"])

    mock_export_all.assert_called_once_with(
        states=[mock_state],
        rewards=[mock_reward],
        ledger_entries=["ledger1", "ledger2"],
        badges=["badge1", "new_badge"],
        leaderboard=["leader1"],
        notifications=["notif1", "new_notif"],
        run_summary=summary,
        output_dir=Path("out_dir"),
    )

    # Verify summary fields
    assert summary.run_date == date(2026, 6, 15)
    assert summary.total_users_processed == 1
    assert summary.total_rewards_generated == 1
    assert summary.total_ledger_entries == 2
    assert summary.total_badges_assigned == 2
    assert summary.total_notifications_created == 2
    assert summary.leaderboard_size == 1


@patch("gamification_engine.orchestration.pipeline.load_user_activities_csv")
def test_run_pipeline_propagates_gamification_engine_errors(mock_load_activities) -> None:
    """The pipeline should propagate GamificationEngineError directly."""

    mock_load_activities.side_effect = IngestionError("Corrupted CSV")

    ctx = RunContext(
        activities_csv_path="activities.csv",
        challenges_csv_path="challenges.csv",
        output_dir="out_dir",
        run_date=date(2026, 6, 15),
    )

    with pytest.raises(IngestionError) as excinfo:
        run_pipeline(ctx)

    assert "Corrupted CSV" in str(excinfo.value)


@patch("gamification_engine.orchestration.pipeline.load_user_activities_csv")
def test_run_pipeline_wraps_unexpected_exceptions(mock_load_activities) -> None:
    """The pipeline should wrap any generic Exception as a GamificationEngineError."""

    mock_load_activities.side_effect = RuntimeError("Disk full")

    ctx = RunContext(
        activities_csv_path="activities.csv",
        challenges_csv_path="challenges.csv",
        output_dir="out_dir",
        run_date=date(2026, 6, 15),
    )

    with pytest.raises(GamificationEngineError) as excinfo:
        run_pipeline(ctx)

    assert "Unexpected pipeline error: Disk full" in str(excinfo.value)
