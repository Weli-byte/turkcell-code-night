"""
Points Ledger for Gamification System.

Provides an append-only ledger backed by pandas DataFrames for tracking
point transactions with full auditability.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional

import pandas as pd

LEDGER_COLUMNS = [
    "ledger_id",
    "user_id",
    "points_delta",
    "source",
    "source_ref",
    "created_at",
]


def add_ledger_entries(
    challenge_awards_df: pd.DataFrame,
    existing_ledger_df: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    """Create ledger entries from challenge awards and append to the ledger.

    For each row in *challenge_awards_df* a new ledger record is created
    with a unique identifier, the awarded points, and a back-reference
    to the originating award.

    If an *existing_ledger_df* is provided the new entries are appended
    to it (the original is never overwritten).  Otherwise a fresh ledger
    DataFrame is returned.

    Expected columns in *challenge_awards_df*:
        award_id, user_id, reward_points

    Args:
        challenge_awards_df: DataFrame of challenge award records.
        existing_ledger_df: Optional existing ledger DataFrame to
            append to.

    Returns:
        The updated (or newly created) ledger DataFrame with columns:
            ledger_id, user_id, points_delta, source, source_ref,
            created_at.
    """
    if challenge_awards_df.empty:
        if existing_ledger_df is not None:
            return existing_ledger_df.copy()
        return pd.DataFrame(columns=LEDGER_COLUMNS)

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    existing_refs: set = set()
    if existing_ledger_df is not None and not existing_ledger_df.empty:
        existing_refs = set(existing_ledger_df["source_ref"].tolist())

    new_entries: list[dict] = []
    for _, row in challenge_awards_df.iterrows():
        if row["award_id"] in existing_refs:
            continue
        new_entries.append({
            "ledger_id": str(uuid.uuid4()),
            "user_id": row["user_id"],
            "points_delta": row["reward_points"],
            "source": "CHALLENGE_REWARD",
            "source_ref": row["award_id"],
            "created_at": timestamp,
        })

    new_df = pd.DataFrame(new_entries, columns=LEDGER_COLUMNS)

    if existing_ledger_df is not None:
        return pd.concat(
            [existing_ledger_df, new_df],
            ignore_index=True,
        )

    return new_df


def calculate_total_points(ledger_df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate total points per user from the ledger.

    Args:
        ledger_df: The points ledger DataFrame containing at least
            user_id and points_delta columns.

    Returns:
        A DataFrame with columns: user_id, total_points.
        Returns an empty DataFrame with the correct columns if the
        ledger is empty.
    """
    if ledger_df.empty:
        return pd.DataFrame(columns=["user_id", "total_points"])

    totals = (
        ledger_df
        .groupby("user_id", as_index=False)["points_delta"]
        .sum()
        .rename(columns={"points_delta": "total_points"})
    )

    return totals
