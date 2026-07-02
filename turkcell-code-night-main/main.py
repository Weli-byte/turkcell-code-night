"""
Main Orchestrator for Gamification System.

Loads activity and challenge data, evaluates challenges, generates
awards, updates the points ledger, assigns badges, creates
notifications, builds the leaderboard, validates system integrity,
and atomically exports all results.
"""

import os
import shutil
import sys

import pandas as pd

from state_engine.state_processor import build_user_state
from logic_engine.rule_engine import (
    evaluate_challenges_for_users,
    generate_challenge_awards,
)
from logic_engine.badge_engine import assign_badges
from logic_engine.notification_engine import create_notifications
from logic_engine.leaderboard_engine import generate_leaderboard
from models.ledger import add_ledger_entries, calculate_total_points
from utils.file_loader import load_csv, export_json
from utils.integrity_validator import validate_system_integrity

DATA_DIR = "data"
OUTPUT_DIR = "output"
TEMP_DIR = "output_temp"

ACTIVITY_CSV = os.path.join(DATA_DIR, "activity_events.csv")
CHALLENGES_CSV = os.path.join(DATA_DIR, "challenges.csv")
LEDGER_CSV = os.path.join(OUTPUT_DIR, "points_ledger.csv")
BADGE_CSV = os.path.join(OUTPUT_DIR, "badge_awards.csv")
NOTIFICATIONS_CSV = os.path.join(OUTPUT_DIR, "notifications.csv")
LEADERBOARD_CSV = os.path.join(OUTPUT_DIR, "leaderboard.csv")

OUTPUT_FILES = {
    "challenge_awards.json": None,
    "badge_awards.json": None,
    "badge_awards.csv": None,
    "notifications.json": None,
    "notifications.csv": None,
    "points_ledger.json": None,
    "points_ledger.csv": None,
    "leaderboard.json": None,
    "leaderboard.csv": None,
}


def _load_existing_csv(filepath: str) -> pd.DataFrame | None:
    """Load a CSV file if it exists, otherwise return None.

    Args:
        filepath: Path to the CSV file.

    Returns:
        A pandas DataFrame or None if the file does not exist.
    """
    if os.path.isfile(filepath):
        return pd.read_csv(filepath)
    return None


def _write_to_temp(
    temp_dir: str,
    challenge_awards_df: pd.DataFrame,
    ledger_df: pd.DataFrame,
    badge_awards_df: pd.DataFrame,
    notifications_df: pd.DataFrame,
    leaderboard_df: pd.DataFrame,
) -> None:
    """Write all output files to the temporary directory.

    Args:
        temp_dir: The temporary directory path.
        challenge_awards_df: Challenge awards DataFrame.
        ledger_df: Points ledger DataFrame.
        badge_awards_df: Badge awards DataFrame.
        notifications_df: Notifications DataFrame.
        leaderboard_df: Leaderboard DataFrame.
    """
    export_json(
        challenge_awards_df.to_dict(orient="records"),
        os.path.join(temp_dir, "challenge_awards.json"),
    )

    export_json(
        badge_awards_df.to_dict(orient="records"),
        os.path.join(temp_dir, "badge_awards.json"),
    )
    badge_awards_df.to_csv(
        os.path.join(temp_dir, "badge_awards.csv"), index=False,
    )

    export_json(
        notifications_df.to_dict(orient="records"),
        os.path.join(temp_dir, "notifications.json"),
    )
    notifications_df.to_csv(
        os.path.join(temp_dir, "notifications.csv"), index=False,
    )

    export_json(
        ledger_df.to_dict(orient="records"),
        os.path.join(temp_dir, "points_ledger.json"),
    )
    ledger_df.to_csv(
        os.path.join(temp_dir, "points_ledger.csv"), index=False,
    )

    export_json(
        leaderboard_df.to_dict(orient="records"),
        os.path.join(temp_dir, "leaderboard.json"),
    )
    leaderboard_df.to_csv(
        os.path.join(temp_dir, "leaderboard.csv"), index=False,
    )


def _promote_temp_to_output(temp_dir: str, output_dir: str) -> None:
    """Atomically replace output files with their temporary counterparts.

    Uses ``os.replace()`` for each file to guarantee that the target
    is never left in a partially-written state.

    Args:
        temp_dir: The temporary directory containing validated files.
        output_dir: The final output directory.
    """
    os.makedirs(output_dir, exist_ok=True)

    for filename in OUTPUT_FILES:
        src = os.path.join(temp_dir, filename)
        dst = os.path.join(output_dir, filename)
        if os.path.isfile(src):
            os.replace(src, dst)


def run(as_of_date: str) -> None:
    """Execute the full gamification pipeline with atomic writes.

    All computation and validation happens in memory first.  Output
    files are written to a temporary directory and only promoted to
    the final output directory after integrity validation passes.
    If any step fails, existing output files remain untouched.

    Steps:
        1.  Load activity and challenge CSVs.
        2.  Build per-user state DataFrame.
        3.  Evaluate challenge conditions for all users.
        4.  Generate priority-resolved challenge awards.
        5.  Load existing persistence files for idempotency.
        6.  Record awarded points in the ledger.
        7.  Calculate total points per user.
        8.  Assign badges based on point thresholds.
        9.  Generate BiP notifications for awards.
        10. Build the ranked leaderboard.
        11. Validate system integrity.
        12. Write to temporary directory.
        13. Atomically promote to output directory.

    Args:
        as_of_date: The reference date for evaluation (YYYY-MM-DD).
    """
    activity_df = load_csv(ACTIVITY_CSV)
    challenges_df = load_csv(CHALLENGES_CSV)

    user_state_df = build_user_state(activity_df, as_of_date)

    triggered_dict = evaluate_challenges_for_users(user_state_df, challenges_df)

    existing_awards_df = _load_existing_csv(
        os.path.join(OUTPUT_DIR, "challenge_awards.csv")
    )
    challenge_awards_df = generate_challenge_awards(
        triggered_dict, as_of_date, existing_awards_df,
    )

    existing_ledger_df = _load_existing_csv(LEDGER_CSV)
    ledger_df = add_ledger_entries(challenge_awards_df, existing_ledger_df)

    total_points_df = calculate_total_points(ledger_df)

    existing_badge_awards_df = _load_existing_csv(BADGE_CSV)
    badge_awards_df = assign_badges(total_points_df, existing_badge_awards_df)

    existing_notifications_df = _load_existing_csv(NOTIFICATIONS_CSV)
    notifications_df = create_notifications(
        challenge_awards_df, existing_notifications_df,
    )

    leaderboard_df = generate_leaderboard(total_points_df)

    validate_system_integrity(
        challenge_awards_df=challenge_awards_df,
        ledger_df=ledger_df,
        badge_awards_df=badge_awards_df,
        notifications_df=notifications_df,
        leaderboard_df=leaderboard_df,
        total_points_df=total_points_df,
    )

    os.makedirs(TEMP_DIR, exist_ok=True)
    try:
        _write_to_temp(
            TEMP_DIR,
            challenge_awards_df,
            ledger_df,
            badge_awards_df,
            notifications_df,
            leaderboard_df,
        )
        _promote_temp_to_output(TEMP_DIR, OUTPUT_DIR)
    finally:
        if os.path.isdir(TEMP_DIR):
            shutil.rmtree(TEMP_DIR)


if __name__ == "__main__":
    date_arg = sys.argv[1] if len(sys.argv) > 1 else "2026-02-16"
    run(as_of_date=date_arg)
