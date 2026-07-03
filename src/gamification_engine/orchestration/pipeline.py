"""Pipeline orchestrator for the deterministic gamification engine."""

from __future__ import annotations

import logging

from gamification_engine.badges.badge_engine import assign_badges
from gamification_engine.badges.badge_repository import (
    load_badge_assignments_json,
)
from gamification_engine.domain.errors import GamificationEngineError
from gamification_engine.export.json_exporter import RunSummary, export_all
from gamification_engine.ingestion.csv_loader import (
    load_challenge_definitions_csv,
    load_user_activities_csv,
)
from gamification_engine.leaderboard.leaderboard_engine import build_leaderboard
from gamification_engine.ledger.ledger_repository import load_points_ledger_json
from gamification_engine.ledger.points_ledger import (
    append_reward_events,
    calculate_total_points,
)
from gamification_engine.notifications.notification_engine import (
    create_notifications,
)
from gamification_engine.notifications.notification_repository import (
    load_notifications_json,
)
from gamification_engine.orchestration.run_context import RunContext
from gamification_engine.rules.evaluator import evaluate_challenges_for_state
from gamification_engine.rules.reward_selector import select_reward
from gamification_engine.state.state_builder import build_daily_user_states

logger = logging.getLogger(__name__)


def run_pipeline(context: RunContext) -> RunSummary:
    """Execute the batch gamification pipeline end-to-end.

    This function coordinates all stages of the pipeline: loading inputs,
    building state, evaluating rules, updating history, ranking users,
    generating notifications, and exporting the final outputs to JSON.

    Args:
        context: Execution parameters and paths for the run.

    Returns:
        A RunSummary containing metadata about the execution.

    Raises:
        GamificationEngineError: If any pipeline stage fails.
    """

    logger.info("Starting pipeline run for date: %s", context.run_date)

    try:
        # 1. Load CSV Inputs
        logger.info("Loading user activities from %s", context.activities_csv_path)
        activities = load_user_activities_csv(context.activities_csv_path)

        logger.info("Loading challenges from %s", context.challenges_csv_path)
        challenges = load_challenge_definitions_csv(context.challenges_csv_path)

        # 2. Load Historical Data
        assert context.existing_ledger_path is not None
        assert context.existing_badges_path is not None
        assert context.existing_notifications_path is not None

        logger.info("Loading ledger history from %s", context.existing_ledger_path)
        existing_ledger = load_points_ledger_json(context.existing_ledger_path)

        logger.info("Loading badge history from %s", context.existing_badges_path)
        existing_badges = load_badge_assignments_json(context.existing_badges_path)

        logger.info(
            "Loading notification history from %s",
            context.existing_notifications_path,
        )
        existing_notifications = load_notifications_json(
            context.existing_notifications_path
        )

        # 3. Build Daily User States
        logger.info("Building daily user states")
        states = build_daily_user_states(activities, context.run_date)

        # 4. Evaluate Challenges & Select Rewards
        logger.info("Evaluating challenges and selecting rewards")
        new_rewards = []
        for state in states:
            triggered = evaluate_challenges_for_state(state, challenges)
            reward = select_reward(state.user_id, context.run_date, triggered)
            if reward is not None:
                new_rewards.append(reward)

        # 5. Update Points Ledger
        logger.info("Updating points ledger")
        updated_ledger = append_reward_events(existing_ledger, new_rewards)

        # 6. Calculate Total Points
        user_total_points = calculate_total_points(updated_ledger)

        # 7. Assign Badges
        logger.info("Assigning badges")
        new_badges, all_badges = assign_badges(
            user_total_points,
            existing_badges,
            context.run_date,
        )

        # 8. Build Leaderboard
        logger.info("Building leaderboard")
        leaderboard = build_leaderboard(user_total_points, all_badges)

        # 9. Create Notifications
        logger.info("Creating notifications")
        all_notifications = create_notifications(
            new_rewards,
            new_badges,
            existing_notifications,
        )

        # 10. Generate Run Summary
        summary = RunSummary(
            run_date=context.run_date,
            total_users_processed=len(states),
            total_rewards_generated=len(new_rewards),
            total_ledger_entries=len(updated_ledger),
            total_badges_assigned=len(all_badges),
            total_notifications_created=len(all_notifications),
            leaderboard_size=len(leaderboard),
        )

        # 11. Export JSON Outputs
        logger.info("Exporting JSON outputs to %s", context.output_dir)
        export_all(
            states=states,
            rewards=new_rewards,
            ledger_entries=updated_ledger,
            badges=all_badges,
            leaderboard=leaderboard,
            notifications=all_notifications,
            run_summary=summary,
            output_dir=context.output_dir,
        )

        logger.info("Pipeline completed successfully for date: %s", context.run_date)
        return summary

    except GamificationEngineError as exc:
        logger.error("Pipeline failed: %s", exc)
        raise
    except Exception as exc:
        logger.error("Unexpected error in pipeline: %s", exc)
        raise GamificationEngineError(f"Unexpected pipeline error: {exc}") from exc
