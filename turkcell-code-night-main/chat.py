"""
Chat CLI for Gamification System.

Provides a command-line interface to interact with the gamification
chatbot.  Loads pipeline output data and delegates to the AI layer
for response generation.

Usage:
    python chat.py <user_id> "<message>"
"""

import json
import os
import sys

import pandas as pd

from ai_layer.chatbot_engine import generate_response

OUTPUT_DIR = "output"

FILE_MAP = {
    "leaderboard": "leaderboard.json",
    "badge_awards": "badge_awards.json",
    "challenge_awards": "challenge_awards.json",
    "notifications": "notifications.json",
    "points_ledger": "points_ledger.json",
}


def _load_json_as_df(filepath: str) -> pd.DataFrame:
    """Load a JSON file and return its contents as a DataFrame.

    Returns an empty DataFrame if the file does not exist or
    cannot be parsed.

    Args:
        filepath: Path to the JSON file.

    Returns:
        A pandas DataFrame, possibly empty.
    """
    if not os.path.isfile(filepath):
        return pd.DataFrame()

    with open(filepath, "r", encoding="utf-8") as fh:
        data = json.load(fh)

    if isinstance(data, list) and data:
        return pd.DataFrame(data)

    return pd.DataFrame()


def _compute_total_points(ledger_df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate total points per user from the ledger DataFrame.

    Args:
        ledger_df: The points ledger DataFrame with user_id and
            points_delta columns.

    Returns:
        A DataFrame with columns user_id and total_points.
    """
    if ledger_df.empty or "points_delta" not in ledger_df.columns:
        return pd.DataFrame(columns=["user_id", "total_points"])

    return (
        ledger_df
        .groupby("user_id", as_index=False)["points_delta"]
        .sum()
        .rename(columns={"points_delta": "total_points"})
    )


def main() -> None:
    """Parse CLI arguments, load data, and print the chatbot response."""
    if len(sys.argv) < 3:
        sys.stderr.write("Usage: python chat.py <user_id> \"<message>\"\n")
        sys.exit(1)

    user_id = sys.argv[1]
    message = " ".join(sys.argv[2:])

    leaderboard_df = _load_json_as_df(
        os.path.join(OUTPUT_DIR, FILE_MAP["leaderboard"])
    )
    badge_awards_df = _load_json_as_df(
        os.path.join(OUTPUT_DIR, FILE_MAP["badge_awards"])
    )
    challenge_awards_df = _load_json_as_df(
        os.path.join(OUTPUT_DIR, FILE_MAP["challenge_awards"])
    )
    notifications_df = _load_json_as_df(
        os.path.join(OUTPUT_DIR, FILE_MAP["notifications"])
    )
    ledger_df = _load_json_as_df(
        os.path.join(OUTPUT_DIR, FILE_MAP["points_ledger"])
    )

    total_points_df = _compute_total_points(ledger_df)

    result = generate_response(
        user_message=message,
        user_id=user_id,
        leaderboard_df=leaderboard_df,
        badge_awards_df=badge_awards_df,
        total_points_df=total_points_df,
        challenge_awards_df=challenge_awards_df,
        notifications_df=notifications_df,
    )

    print(result["response_text"])


if __name__ == "__main__":
    main()
