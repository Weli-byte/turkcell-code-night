"""
Badge Engine for Gamification System.

Assigns tier-based viewer badges to users according to their
accumulated points, enforcing a no-duplicate-assignment policy
across runs via an append-only badge awards DataFrame.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional

import pandas as pd

BADGE_THRESHOLDS: list[tuple[int, str]] = [
    (1500, "Gold Viewer"),
    (850, "Silver Viewer"),
    (300, "Bronze Viewer"),
]

BADGE_COLUMNS = [
    "user_id",
    "badge_id",
    "badge_name",
    "awarded_at",
]


def _determine_badge(total_points: int) -> Optional[str]:
    """Return the highest badge tier the user qualifies for.

    Thresholds are evaluated from highest to lowest so the first
    match is always the best tier.

    Args:
        total_points: The user's cumulative point total.

    Returns:
        The badge name string, or None if no threshold is met.
    """
    for threshold, badge_name in BADGE_THRESHOLDS:
        if total_points >= threshold:
            return badge_name
    return None


def assign_badges(
    total_points_df: pd.DataFrame,
    existing_badge_awards_df: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    """Assign the highest qualifying badge to each user, preventing duplicates.

    For every user in *total_points_df*, determines which badge (if any)
    they qualify for based on ``total_points``.  A badge is only created
    when the user does not already hold that exact badge in
    *existing_badge_awards_df*.

    Args:
        total_points_df: DataFrame with columns user_id and total_points.
        existing_badge_awards_df: Optional DataFrame of previously awarded
            badges (same schema as the return value).  Used for
            deduplication.  If None, all qualifying badges are treated
            as new.

    Returns:
        The updated badge awards DataFrame with columns:
            user_id, badge_id, badge_name, awarded_at.
    """
    all_badge_names = [name for _, name in BADGE_THRESHOLDS]

    if existing_badge_awards_df is not None:
        updated_df = existing_badge_awards_df.copy()
    else:
        updated_df = pd.DataFrame(columns=BADGE_COLUMNS)

    current_badges: dict[str, str] = {}
    if not updated_df.empty:
        for _, badge_row in updated_df.iterrows():
            uid = str(badge_row["user_id"])
            bname = badge_row["badge_name"]
            if uid not in current_badges:
                current_badges[uid] = bname
            else:
                existing_rank = all_badge_names.index(current_badges[uid])
                new_rank = all_badge_names.index(bname)
                if new_rank < existing_rank:
                    current_badges[uid] = bname

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    users_to_upgrade: list[tuple[str, str]] = []
    for _, row in total_points_df.iterrows():
        user_id = str(row["user_id"])
        badge_name = _determine_badge(int(row["total_points"]))

        if badge_name is None:
            continue

        existing_badge = current_badges.get(user_id)

        if existing_badge == badge_name:
            continue

        users_to_upgrade.append((user_id, badge_name))

    for user_id, badge_name in users_to_upgrade:
        updated_df = updated_df[
            ~((updated_df["user_id"].astype(str) == user_id)
              & (updated_df["badge_name"].isin(all_badge_names)))
        ]

    new_entries: list[dict] = []
    for user_id, badge_name in users_to_upgrade:
        new_entries.append({
            "user_id": user_id,
            "badge_id": str(uuid.uuid4()),
            "badge_name": badge_name,
            "awarded_at": timestamp,
        })

    new_df = pd.DataFrame(new_entries, columns=BADGE_COLUMNS)

    return pd.concat(
        [updated_df, new_df],
        ignore_index=True,
    )
