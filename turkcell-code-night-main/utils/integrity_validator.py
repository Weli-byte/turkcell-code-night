"""
System Integrity Validator for Gamification System.

Provides cross-module consistency checks to ensure that challenge
awards, ledger entries, badge assignments, notifications, and
leaderboard rankings are all in a coherent state.
"""

import pandas as pd

BADGE_THRESHOLDS: dict[str, int] = {
    "Gold Viewer": 1500,
    "Silver Viewer": 850,
    "Bronze Viewer": 300,
}


def validate_system_integrity(
    challenge_awards_df: pd.DataFrame,
    ledger_df: pd.DataFrame,
    badge_awards_df: pd.DataFrame,
    notifications_df: pd.DataFrame,
    leaderboard_df: pd.DataFrame,
    total_points_df: pd.DataFrame,
) -> None:
    """Validate cross-module consistency of all gamification data.

    Checks that:
        1. Every challenge award has exactly one matching ledger entry.
        2. No orphan ledger entries exist for CHALLENGE_REWARD source.
        3. Badge assignments are consistent with point thresholds.
        4. Leaderboard totals match the aggregated point totals.
        5. Every notification corresponds to an award or badge.

    Args:
        challenge_awards_df: DataFrame of challenge award records.
        ledger_df: DataFrame of points ledger entries.
        badge_awards_df: DataFrame of badge award records.
        notifications_df: DataFrame of notification records.
        leaderboard_df: DataFrame of ranked leaderboard entries.
        total_points_df: DataFrame of aggregated user point totals.

    Raises:
        ValueError: If any integrity rule is violated. The message
            describes every detected violation.
    """
    errors: list[str] = []

    errors.extend(_validate_awards_to_ledger(challenge_awards_df, ledger_df))
    errors.extend(_validate_ledger_to_awards(ledger_df, challenge_awards_df))
    errors.extend(_validate_badge_thresholds(badge_awards_df, total_points_df))
    errors.extend(_validate_leaderboard_points(leaderboard_df, total_points_df))
    errors.extend(
        _validate_notifications(
            notifications_df, challenge_awards_df, badge_awards_df
        )
    )

    if errors:
        raise ValueError(
            "System integrity validation failed:\n"
            + "\n".join(f"  - {e}" for e in errors)
        )


def _validate_awards_to_ledger(
    awards_df: pd.DataFrame,
    ledger_df: pd.DataFrame,
) -> list[str]:
    """Rule 1: Every challenge award must have exactly one matching ledger entry."""
    errors: list[str] = []

    if awards_df.empty:
        return errors

    award_ids = set(awards_df["award_id"].astype(str))

    if ledger_df.empty:
        for aid in sorted(award_ids):
            errors.append(
                f"Award '{aid}' has no matching ledger entry."
            )
        return errors

    challenge_ledger = ledger_df[ledger_df["source"] == "CHALLENGE_REWARD"]
    ledger_refs = challenge_ledger["source_ref"].astype(str).tolist()
    ledger_ref_counts: dict[str, int] = {}
    for ref in ledger_refs:
        ledger_ref_counts[ref] = ledger_ref_counts.get(ref, 0) + 1

    for aid in sorted(award_ids):
        count = ledger_ref_counts.get(aid, 0)
        if count == 0:
            errors.append(
                f"Award '{aid}' has no matching ledger entry."
            )
        elif count > 1:
            errors.append(
                f"Award '{aid}' has {count} ledger entries (expected 1)."
            )

    return errors


def _validate_ledger_to_awards(
    ledger_df: pd.DataFrame,
    awards_df: pd.DataFrame,
) -> list[str]:
    """Rule 2: No orphan ledger entries for CHALLENGE_REWARD source."""
    errors: list[str] = []

    if ledger_df.empty:
        return errors

    challenge_ledger = ledger_df[ledger_df["source"] == "CHALLENGE_REWARD"]

    if challenge_ledger.empty:
        return errors

    award_ids = set()
    if not awards_df.empty:
        award_ids = set(awards_df["award_id"].astype(str))

    orphan_refs = sorted(
        set(challenge_ledger["source_ref"].astype(str)) - award_ids
    )
    for ref in orphan_refs:
        errors.append(
            f"Ledger entry references award '{ref}' which does not exist."
        )

    return errors


def _validate_badge_thresholds(
    badge_awards_df: pd.DataFrame,
    total_points_df: pd.DataFrame,
) -> list[str]:
    """Rule 3: Badge assignments must be consistent with point thresholds."""
    errors: list[str] = []

    if badge_awards_df.empty:
        return errors

    points_lookup: dict[str, int] = {}
    if not total_points_df.empty:
        for _, row in total_points_df.iterrows():
            points_lookup[str(row["user_id"])] = int(row["total_points"])

    for _, row in badge_awards_df.iterrows():
        user_id = str(row["user_id"])
        badge_name = row["badge_name"]
        required_threshold = BADGE_THRESHOLDS.get(badge_name)

        if required_threshold is None:
            errors.append(
                f"User '{user_id}' has unknown badge tier '{badge_name}'."
            )
            continue

        user_points = points_lookup.get(user_id, 0)
        if user_points < required_threshold:
            errors.append(
                f"User '{user_id}' has badge '{badge_name}' "
                f"(requires {required_threshold} pts) but only has "
                f"{user_points} pts."
            )

    return errors


def _validate_leaderboard_points(
    leaderboard_df: pd.DataFrame,
    total_points_df: pd.DataFrame,
) -> list[str]:
    """Rule 4: Leaderboard total_points must match total_points_df."""
    errors: list[str] = []

    if leaderboard_df.empty:
        return errors

    points_lookup: dict[str, int] = {}
    if not total_points_df.empty:
        for _, row in total_points_df.iterrows():
            points_lookup[str(row["user_id"])] = int(row["total_points"])

    for _, row in leaderboard_df.iterrows():
        user_id = str(row["user_id"])
        lb_points = int(row["total_points"])
        expected_points = points_lookup.get(user_id)

        if expected_points is None:
            errors.append(
                f"Leaderboard contains user '{user_id}' "
                f"who has no entry in total_points."
            )
        elif lb_points != expected_points:
            errors.append(
                f"Leaderboard shows {lb_points} pts for user '{user_id}' "
                f"but total_points_df shows {expected_points} pts."
            )

    return errors


def _validate_notifications(
    notifications_df: pd.DataFrame,
    challenge_awards_df: pd.DataFrame,
    badge_awards_df: pd.DataFrame,
) -> list[str]:
    """Rule 5: Every notification must correspond to an award or badge."""
    errors: list[str] = []

    if notifications_df.empty:
        return errors

    award_user_ids: set[str] = set()
    if not challenge_awards_df.empty:
        award_user_ids = set(challenge_awards_df["user_id"].astype(str))

    badge_user_ids: set[str] = set()
    if not badge_awards_df.empty:
        badge_user_ids = set(badge_awards_df["user_id"].astype(str))

    valid_user_ids = award_user_ids | badge_user_ids

    for _, row in notifications_df.iterrows():
        user_id = str(row["user_id"])
        if user_id not in valid_user_ids:
            notification_id = row.get("notification_id", "unknown")
            errors.append(
                f"Notification '{notification_id}' for user '{user_id}' "
                f"has no matching challenge award or badge award."
            )

    return errors
