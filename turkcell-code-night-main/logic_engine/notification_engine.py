"""
Notification Engine for Gamification System.

Creates BiP notification records from challenge award data,
producing a DataFrame ready for downstream dispatch.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional

import pandas as pd

NOTIFICATION_COLUMNS = [
    "notification_id",
    "user_id",
    "channel",
    "message",
    "sent_at",
]


def create_notifications(
    challenge_awards_df: pd.DataFrame,
    existing_notifications_df: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    """Generate one BiP notification per challenge award.

    For each row in *challenge_awards_df* a notification record is
    created with a formatted congratulations message and a UTC timestamp.

    If *existing_notifications_df* is provided, awards that already have
    a matching notification are skipped.  The duplicate key is the
    combination of (user_id, selected_challenge, reward_points).

    Expected columns in *challenge_awards_df*:
        award_id, user_id, selected_challenge, reward_points

    Args:
        challenge_awards_df: DataFrame of challenge award records.
        existing_notifications_df: Optional DataFrame of previously
            sent notifications.  Used for idempotency checks.

    Returns:
        A pandas DataFrame with one row per notification and columns:
            notification_id, user_id, channel, message, sent_at.
        Returns an empty DataFrame with the correct columns if the
        input is empty.
    """
    if challenge_awards_df.empty:
        if existing_notifications_df is not None:
            return existing_notifications_df.copy()
        return pd.DataFrame(columns=NOTIFICATION_COLUMNS)

    existing_keys: set[tuple] = set()
    if existing_notifications_df is not None and not existing_notifications_df.empty:
        for _, n_row in existing_notifications_df.iterrows():
            msg = str(n_row["message"])
            existing_keys.add((str(n_row["user_id"]), msg))

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    records: list[dict] = []
    for _, row in challenge_awards_df.iterrows():
        message = (
            f"Congratulations! You completed {row['selected_challenge']} "
            f"and earned {row['reward_points']} points."
        )

        dedup_key = (str(row["user_id"]), message)
        if dedup_key in existing_keys:
            continue

        records.append({
            "notification_id": str(uuid.uuid4()),
            "user_id": row["user_id"],
            "channel": "BiP",
            "message": message,
            "sent_at": timestamp,
        })

    new_df = pd.DataFrame(records, columns=NOTIFICATION_COLUMNS)

    if existing_notifications_df is not None:
        return pd.concat(
            [existing_notifications_df, new_df],
            ignore_index=True,
        )

    return new_df

