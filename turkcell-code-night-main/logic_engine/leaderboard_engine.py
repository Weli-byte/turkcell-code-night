"""
Leaderboard Engine for Gamification System.

Generates a ranked leaderboard from aggregated user point totals
with deterministic tie-breaking and consecutive ranking.
"""

import pandas as pd


def generate_leaderboard(total_points_df: pd.DataFrame) -> pd.DataFrame:
    """Generate a ranked leaderboard from user point totals.

    Users are sorted by ``total_points`` in descending order.  Ties are
    broken alphabetically by ``user_id`` in ascending order.  Ranks are
    assigned consecutively starting from 1 with no gaps.

    Args:
        total_points_df: DataFrame with columns user_id and total_points.

    Returns:
        A pandas DataFrame with columns: rank, user_id, total_points.
        Returns an empty DataFrame with the correct columns if the
        input is empty.
    """
    if total_points_df.empty:
        return pd.DataFrame(columns=["rank", "user_id", "total_points"])

    total_points_df = total_points_df.copy()
    total_points_df["user_id"] = total_points_df["user_id"].astype(str)

    sorted_df = (
        total_points_df
        .sort_values(
            by=["total_points", "user_id"],
            ascending=[False, True],
        )
        .reset_index(drop=True)
    )

    sorted_df.insert(0, "rank", range(1, len(sorted_df) + 1))

    return sorted_df
