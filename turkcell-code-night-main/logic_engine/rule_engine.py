"""
Rule Engine for Gamification System.

Provides secure condition evaluation, priority-based challenge resolution,
and challenge award generation for user engagement workflows.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

import pandas as pd


def evaluate_condition(condition: str, state: dict) -> bool:
    """Safely evaluate a condition expression against the given state dictionary.

    Supports simple comparison expressions such as:
        watch_minutes_today >= 60
        episodes_completed_today >= 2
        watch_streak_days >= 3

    Only variables present in *state* are accessible during evaluation.
    Built-in functions and modules are completely blocked.

    Args:
        condition: A string expression to evaluate (e.g. "score >= 100").
        state: A dictionary mapping variable names to their current values.

    Returns:
        True if the condition evaluates to a truthy value, False otherwise.
        Returns False on any error to guarantee fail-safe behaviour.
    """
    try:
        result = eval(condition, {"__builtins__": {}}, state)  # noqa: S307
        return bool(result)
    except Exception:
        return False


def resolve_priority(
    triggered: list[dict],
) -> tuple[Optional[dict], list[dict]]:
    """Select the highest-priority challenge and suppress the rest.

    Priority is determined by the ``priority`` field where the *lowest*
    numeric value represents the *highest* priority (1 = top priority).

    Each item in *triggered* is expected to contain at least:
        - challenge_id (str)
        - priority (int)
        - reward_points (int)

    Args:
        triggered: A list of challenge dictionaries that have been triggered.

    Returns:
        A tuple of (selected_challenge, suppressed_challenges).
        If *triggered* is empty, returns (None, []).
    """
    if not triggered:
        return None, []

    sorted_challenges = sorted(triggered, key=lambda c: c["priority"])
    selected = sorted_challenges[0]
    suppressed = sorted_challenges[1:]
    return selected, suppressed


def generate_challenge_award(
    user_id: str,
    as_of_date: str,
    triggered: list[dict],
) -> Optional[dict]:
    """Generate a challenge award record after applying the priority rule.

    Resolves the highest-priority challenge from the *triggered* list and
    assembles a complete award payload including a unique award identifier,
    timestamps, and details of both selected and suppressed challenges.

    Args:
        user_id: The unique identifier of the user receiving the award.
        as_of_date: The reference date for the award (ISO-8601 date string).
        triggered: A list of triggered challenge dictionaries, each containing
            at minimum ``challenge_id``, ``priority``, and ``reward_points``.

    Returns:
        A dictionary representing the award record, or None if no challenge
        was selected (i.e. *triggered* was empty).
    """
    selected, suppressed = resolve_priority(triggered)

    if selected is None:
        return None

    return {
        "award_id": str(uuid.uuid4()),
        "user_id": user_id,
        "as_of_date": as_of_date,
        "triggered_challenges": [c["challenge_id"] for c in triggered],
        "selected_challenge": selected["challenge_id"],
        "reward_points": selected["reward_points"],
        "suppressed_challenges": [c["challenge_id"] for c in suppressed],
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def evaluate_challenges_for_users(
    user_state_df: pd.DataFrame,
    challenges_df: pd.DataFrame,
) -> dict[str, list[dict]]:
    """Evaluate all active challenges against every user's state.

    For each user row in *user_state_df*, iterates over every challenge
    in *challenges_df* where ``is_active`` is True, evaluates the
    challenge's ``condition`` string against the user's state values,
    and collects the triggered challenges.

    Args:
        user_state_df: A DataFrame with one row per user_id and computed
            state columns (e.g. watch_minutes_today, watch_streak_days).
        challenges_df: A DataFrame of challenge definitions with columns:
            challenge_id, challenge_name, challenge_type, condition,
            reward_points, priority, is_active.

    Returns:
        A dictionary mapping each user_id (str) to a list of triggered
        challenge dictionaries. Users with no triggered challenges are
        included with an empty list.
    """
    active_challenges = challenges_df[challenges_df["is_active"] == True].copy().to_dict(orient="records")  # noqa: E712

    results: dict[str, list[dict]] = {}

    for _, row in user_state_df.iterrows():
        user_id = str(row["user_id"])
        state = row.drop(labels=["user_id"]).to_dict()

        triggered: list[dict] = []
        for challenge in active_challenges:
            if evaluate_condition(challenge["condition"], state):
                triggered.append({
                    "challenge_id": challenge["challenge_id"],
                    "challenge_name": challenge["challenge_name"],
                    "challenge_type": challenge["challenge_type"],
                    "condition": challenge["condition"],
                    "reward_points": challenge["reward_points"],
                    "priority": challenge["priority"],
                })
        results[user_id] = triggered

    return results


def generate_challenge_awards(
    triggered_dict: dict[str, list[dict]],
    as_of_date: str,
    existing_awards_df: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    """Generate one challenge award record per user from triggered challenges.

    For each user in *triggered_dict*, applies priority resolution to
    select the winning challenge (lowest priority number) and marks the
    remaining challenges as suppressed.  Users with no triggered
    challenges are skipped.

    If *existing_awards_df* is provided, awards that already exist
    (matching on user_id, as_of_date, and selected_challenge) are
    skipped to guarantee idempotent behavior.

    Args:
        triggered_dict: A dictionary mapping user_id to a list of
            triggered challenge dictionaries, each containing at least
            challenge_id, challenge_name, reward_points, and priority.
        as_of_date: The reference date for the awards (YYYY-MM-DD).
        existing_awards_df: Optional DataFrame of previously generated
            awards.  Used for deduplication.

    Returns:
        A pandas DataFrame with one row per awarded user and columns:
            award_id, user_id, as_of_date, triggered_challenges,
            selected_challenge, reward_points, suppressed_challenges,
            timestamp.
        Returns an empty DataFrame with the correct columns if no user
        has any triggered challenges.
    """
    columns = [
        "award_id", "user_id", "as_of_date", "triggered_challenges",
        "selected_challenge", "reward_points", "suppressed_challenges",
        "timestamp",
    ]

    existing_keys: set[tuple] = set()
    if existing_awards_df is not None and not existing_awards_df.empty:
        existing_keys = set(
            zip(
                existing_awards_df["user_id"].astype(str),
                existing_awards_df["as_of_date"].astype(str),
                existing_awards_df["selected_challenge"].astype(str),
            )
        )

    awards: list[dict] = []

    for user_id, triggered in triggered_dict.items():
        if not triggered:
            continue

        selected, suppressed = resolve_priority(triggered)

        dedup_key = (str(user_id), str(as_of_date), str(selected["challenge_id"]))
        if dedup_key in existing_keys:
            continue

        awards.append({
            "award_id": str(uuid.uuid4()),
            "user_id": user_id,
            "as_of_date": as_of_date,
            "triggered_challenges": [c["challenge_id"] for c in triggered],
            "selected_challenge": selected["challenge_id"],
            "reward_points": selected["reward_points"],
            "suppressed_challenges": [c["challenge_id"] for c in suppressed],
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        })

    new_df = pd.DataFrame(awards, columns=columns)

    if existing_awards_df is not None:
        return pd.concat(
            [existing_awards_df, new_df],
            ignore_index=True,
        )

    return new_df


def simulate_extra_watch_minutes(
    user_state_row: dict | pd.Series,
    challenges_df: pd.DataFrame,
    extra_minutes: float,
) -> dict:
    """Simulate the effect of additional watch minutes on challenge outcomes.

    Creates a modified copy of the user's state with an increased
    ``watch_minutes_today`` value, re-evaluates all active challenges,
    and applies priority resolution — without producing any persistent
    side effects.

    Args:
        user_state_row: A single user state as a dict or pandas Series.
            Must contain at least ``watch_minutes_today`` and any other
            keys referenced by challenge conditions.
        challenges_df: DataFrame of challenge definitions with columns:
            challenge_id, challenge_name, condition, reward_points,
            priority, is_active.
        extra_minutes: The number of additional watch minutes to add
            to the current ``watch_minutes_today`` value.

    Returns:
        A dictionary with keys:
            selected_challenge_id — the winning challenge id (or None),
            reward_points — points from the selected challenge (or 0),
            triggered_challenge_ids — list of all triggered challenge ids.
    """
    if isinstance(user_state_row, pd.Series):
        simulated_state = user_state_row.to_dict()
    else:
        simulated_state = dict(user_state_row)
    simulated_state.pop("user_id", None)
    simulated_state["watch_minutes_today"] = (
        simulated_state.get("watch_minutes_today", 0) + extra_minutes
    )

    active_challenges = (
        challenges_df[challenges_df["is_active"] == True].copy()  # noqa: E712
        .to_dict(orient="records")
    )

    triggered: list[dict] = []
    for challenge in active_challenges:
        if evaluate_condition(challenge["condition"], simulated_state):
            triggered.append({
                "challenge_id": challenge["challenge_id"],
                "challenge_name": challenge["challenge_name"],
                "reward_points": challenge["reward_points"],
                "priority": challenge["priority"],
            })

    if not triggered:
        return {
            "selected_challenge_id": None,
            "reward_points": 0,
            "triggered_challenge_ids": [],
        }

    selected, _ = resolve_priority(triggered)

    return {
        "selected_challenge_id": selected["challenge_id"],
        "reward_points": selected["reward_points"],
        "triggered_challenge_ids": [c["challenge_id"] for c in triggered],
    }



