"""
Schema Validator for Gamification System.

Defines required column schemas for all CSV data files and provides
validation functions to ensure data integrity before processing.
"""

import os
from typing import Any

import pandas as pd

REQUIRED_SCHEMAS: dict[str, list[str]] = {
    "users.csv": [
        "user_id",
        "username",
        "email",
        "created_at",
    ],
    "user_state.csv": [
        "user_id",
        "watch_minutes_today",
        "episodes_completed_today",
        "unique_genres_today",
        "watch_party_minutes_today",
        "ratings_today",
        "watch_minutes_7d",
        "episodes_completed_7d",
        "ratings_7d",
        "watch_streak_days",
    ],
    "shows.csv": [
        "show_id",
        "show_name",
        "genre",
        "release_year",
    ],
    "episodes.csv": [
        "episode_id",
        "show_id",
        "episode_number",
        "season_number",
        "duration_minutes",
    ],
    "activity_events.csv": [
        "user_id",
        "event_type",
        "watch_minutes",
        "episode_id",
        "timestamp",
    ],
    "challenges.csv": [
        "challenge_id",
        "challenge_name",
        "condition",
        "reward_points",
        "priority",
        "is_active",
    ],
    "challenge_decisions.csv": [
        "decision_id",
        "user_id",
        "challenge_id",
        "decision",
        "decided_at",
    ],
    "challenge_awards.csv": [
        "award_id",
        "user_id",
        "as_of_date",
        "selected_challenge",
        "reward_points",
        "triggered_challenges",
        "suppressed_challenges",
        "timestamp",
    ],
    "points_ledger.csv": [
        "ledger_id",
        "user_id",
        "points_delta",
        "source",
        "source_ref",
        "created_at",
    ],
    "badges.csv": [
        "badge_name",
        "threshold_points",
        "tier_rank",
    ],
    "badge_awards.csv": [
        "user_id",
        "badge_id",
        "badge_name",
        "awarded_at",
    ],
    "notifications.csv": [
        "notification_id",
        "user_id",
        "channel",
        "message",
        "sent_at",
    ],
    "leaderboard.csv": [
        "rank",
        "user_id",
        "total_points",
    ],
}


def validate_schema(
    df: pd.DataFrame,
    required_columns: list[str],
    file_name: str = "DataFrame",
) -> None:
    """Validate that a DataFrame contains all required columns.

    Args:
        df: The pandas DataFrame to validate.
        required_columns: A list of column names that must be present.
        file_name: An optional label used in the error message to
            identify the source file.

    Raises:
        ValueError: If one or more required columns are missing.
            The error message lists every missing column.
    """
    actual_columns = set(df.columns)
    required_set = set(required_columns)
    missing = sorted(required_set - actual_columns)

    if missing:
        raise ValueError(
            f"Schema validation failed for '{file_name}'. "
            f"Missing required columns: {missing}"
        )


def validate_all_schemas(base_path: str) -> None:
    """Load every expected CSV from *base_path* and validate its schema.

    Iterates over all file definitions in ``REQUIRED_SCHEMAS``.  For each
    file that exists at ``base_path/<filename>``, loads the CSV and
    verifies that it contains the required columns.  Files that do not
    exist on disk are silently skipped to allow incremental data setups.

    Args:
        base_path: The root directory containing the CSV files.

    Raises:
        ValueError: If any existing CSV is missing required columns.
            The error message identifies the file and lists every
            missing column.
    """
    errors: list[str] = []

    for file_name, required_columns in REQUIRED_SCHEMAS.items():
        file_path = os.path.join(base_path, file_name)

        if not os.path.isfile(file_path):
            continue

        df = pd.read_csv(file_path)

        try:
            validate_schema(df, required_columns, file_name=file_name)
        except ValueError as exc:
            errors.append(str(exc))

    if errors:
        raise ValueError(
            "Schema validation errors found:\n" + "\n".join(errors)
        )
