"""
AI Layer – Chatbot Engine.

Provides the main conversational interface for the gamification system.
Routes user queries to the appropriate handler and returns structured
responses based on system state data.
"""

import json
import os
from typing import Any, Optional

import pandas as pd

from ai_layer.deterministic_engine import generate_deterministic_response
from ai_layer.prompt_builder import build_prompt
from ai_layer.fallback_engine import generate_fallback_response



BADGE_TIERS: list[tuple[int, str]] = [
    (300, "Bronze Viewer"),
    (850, "Silver Viewer"),
    (1500, "Gold Viewer"),
]


INTENT_KEYWORDS: dict[str, list[str]] = {
    "leaderboard": ["leaderboard", "ranking", "rank", "top", "sıralama"],
    "badge": ["badge", "rozet", "tier", "gold", "silver", "bronze"],
    "points": ["points", "puan", "score", "total"],
    "challenge": ["challenge", "görev", "award", "ödül"],
    "notification": ["notification", "bildirim", "message"],
}


def classify_intent(user_message: str) -> str:
    """Classify the user's message into a known intent category.

    Performs keyword-based matching against ``INTENT_KEYWORDS``.
    Returns the first matching intent or ``"general"`` if no
    keywords are found.

    Args:
        user_message: The raw text input from the user.

    Returns:
        A string representing the classified intent.
    """
    lower_message = user_message.lower()
    for intent, keywords in INTENT_KEYWORDS.items():
        for keyword in keywords:
            if keyword in lower_message:
                return intent
    return "general"


def build_context(
    intent: str,
    user_id: Optional[str] = None,
    leaderboard_df: Optional[pd.DataFrame] = None,
    badge_awards_df: Optional[pd.DataFrame] = None,
    total_points_df: Optional[pd.DataFrame] = None,
    challenge_awards_df: Optional[pd.DataFrame] = None,
    notifications_df: Optional[pd.DataFrame] = None,
) -> dict[str, Any]:
    """Gather relevant context data based on the classified intent.

    Extracts user-specific or system-wide information from the
    provided DataFrames and packages it into a dictionary for
    prompt construction.

    Args:
        intent: The classified intent string.
        user_id: Optional user identifier for user-scoped queries.
        leaderboard_df: Leaderboard DataFrame.
        badge_awards_df: Badge awards DataFrame.
        total_points_df: Total points DataFrame.
        challenge_awards_df: Challenge awards DataFrame.
        notifications_df: Notifications DataFrame.

    Returns:
        A dictionary of context values keyed by data category.
    """
    context: dict[str, Any] = {"intent": intent, "user_id": user_id}

    if intent == "leaderboard" and leaderboard_df is not None:
        if not leaderboard_df.empty:
            context["leaderboard_top"] = (
                leaderboard_df.head(10).to_dict(orient="records")
            )
            if user_id is not None:
                user_row = leaderboard_df[
                    leaderboard_df["user_id"].astype(str) == str(user_id)
                ]
                if not user_row.empty:
                    context["user_rank"] = user_row.iloc[0].to_dict()

    elif intent == "badge":
        if user_id is not None:
            if badge_awards_df is not None and not badge_awards_df.empty:
                user_badges = badge_awards_df[
                    badge_awards_df["user_id"].astype(str) == str(user_id)
                ]
                context["user_badges"] = user_badges.to_dict(orient="records")

            if total_points_df is not None and not total_points_df.empty:
                user_pts = total_points_df[
                    total_points_df["user_id"].astype(str) == str(user_id)
                ]
                if not user_pts.empty:
                    pts = int(user_pts.iloc[0]["total_points"])
                    context["user_points"] = pts
                    context["total_points"] = pts
                else:
                    context["user_points"] = 0
                    context["total_points"] = 0
            else:
                context["user_points"] = 0
                context["total_points"] = 0

    elif intent == "points":
        if user_id is not None:
            if total_points_df is not None and not total_points_df.empty:
                user_pts = total_points_df[
                    total_points_df["user_id"].astype(str) == str(user_id)
                ]
                if not user_pts.empty:
                    pts = int(user_pts.iloc[0]["total_points"])
                    context["user_points"] = pts
                    context["total_points"] = pts
                else:
                    context["user_points"] = 0
                    context["total_points"] = 0
            else:
                context["user_points"] = 0
                context["total_points"] = 0

    elif intent == "challenge" and challenge_awards_df is not None:
        if user_id is not None and not challenge_awards_df.empty:
            user_awards = challenge_awards_df[
                challenge_awards_df["user_id"].astype(str) == str(user_id)
            ]
            context["user_awards"] = user_awards.to_dict(orient="records")

    elif intent == "notification" and notifications_df is not None:
        if user_id is not None and not notifications_df.empty:
            user_notifs = notifications_df[
                notifications_df["user_id"].astype(str) == str(user_id)
            ]
            context["user_notifications"] = user_notifs.to_dict(orient="records")

    return context


def generate_response(
    user_message: str,
    user_id: Optional[str] = None,
    leaderboard_df: Optional[pd.DataFrame] = None,
    badge_awards_df: Optional[pd.DataFrame] = None,
    total_points_df: Optional[pd.DataFrame] = None,
    challenge_awards_df: Optional[pd.DataFrame] = None,
    notifications_df: Optional[pd.DataFrame] = None,
) -> dict[str, Any]:
    """Generate a chatbot response for the given user message.

    Orchestrates intent classification, context gathering, prompt
    building, and response generation.  Falls back to a generic
    response when no relevant data is available.

    Args:
        user_message: The raw text input from the user.
        user_id: Optional user identifier for personalised responses.
        leaderboard_df: Leaderboard DataFrame.
        badge_awards_df: Badge awards DataFrame.
        total_points_df: Total points DataFrame.
        challenge_awards_df: Challenge awards DataFrame.
        notifications_df: Notifications DataFrame.

    Returns:
        A dictionary with keys: intent, response_text, context.
    """
    intent = classify_intent(user_message)

    context = build_context(
        intent=intent,
        user_id=user_id,
        leaderboard_df=leaderboard_df,
        badge_awards_df=badge_awards_df,
        total_points_df=total_points_df,
        challenge_awards_df=challenge_awards_df,
        notifications_df=notifications_df,
    )

    prompt = build_prompt(intent, context, user_message=user_message)

    if prompt:
        response_text = generate_deterministic_response(intent, user_id, context)
    else:
        response_text = generate_fallback_response(intent, user_id)

    return {
        "intent": intent,
        "response_text": response_text,
        "context": context,
    }


def _load_json(filepath: str) -> list[dict]:
    """Load a JSON file and return its contents as a list of dicts.

    Returns an empty list if the file does not exist or cannot be
    parsed.

    Args:
        filepath: Absolute or relative path to the JSON file.

    Returns:
        A list of dictionaries, or an empty list on failure.
    """
    if not os.path.isfile(filepath):
        return []
    with open(filepath, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    if isinstance(data, list):
        return data
    return []


def _determine_next_badge(
    total_points: int,
    current_badge: Optional[str],
) -> tuple[Optional[str], int]:
    """Determine the next badge tier and points needed to reach it.

    Args:
        total_points: The user's current total points.
        current_badge: The user's current badge name, or None.

    Returns:
        A tuple of (next_badge_name, points_needed).  If the user
        already holds the highest tier, returns (None, 0).
    """
    for threshold, badge_name in BADGE_TIERS:
        if total_points < threshold:
            return badge_name, threshold - total_points

    return None, 0


def build_user_context(user_id: str, base_path: str = ".") -> dict[str, Any]:
    """Build a comprehensive context dictionary for a single user.

    Loads output JSON files (points ledger, leaderboard, badge awards,
    challenge awards) and computes derived metrics including total
    points, rank, current/next badge, and most recent award.

    Args:
        user_id: The user identifier to gather context for.
        base_path: The project root directory (defaults to ``"."``).

    Returns:
        A dictionary with keys:
            user_id, total_points, rank, current_badge,
            next_badge, points_needed_for_next_badge, last_award.
    """
    output_dir = os.path.join(base_path, "output")

    ledger_data = _load_json(os.path.join(output_dir, "points_ledger.json"))
    leaderboard_data = _load_json(os.path.join(output_dir, "leaderboard.json"))
    badge_data = _load_json(os.path.join(output_dir, "badge_awards.json"))
    awards_data = _load_json(os.path.join(output_dir, "challenge_awards.json"))

    total_points = 0
    for entry in ledger_data:
        if str(entry.get("user_id", "")) == str(user_id):
            total_points += int(entry.get("points_delta", 0))

    rank: Optional[int] = None
    for entry in leaderboard_data:
        if str(entry.get("user_id", "")) == str(user_id):
            rank = int(entry["rank"])
            break

    current_badge: Optional[str] = None
    latest_badge_time = ""
    for entry in badge_data:
        if str(entry.get("user_id", "")) == str(user_id):
            awarded_at = str(entry.get("awarded_at", ""))
            if awarded_at >= latest_badge_time:
                latest_badge_time = awarded_at
                current_badge = entry.get("badge_name")

    next_badge, points_needed = _determine_next_badge(total_points, current_badge)

    last_award: Optional[dict[str, Any]] = None
    latest_award_time = ""
    for entry in awards_data:
        if str(entry.get("user_id", "")) == str(user_id):
            ts = str(entry.get("timestamp", ""))
            if ts >= latest_award_time:
                latest_award_time = ts
                last_award = {
                    "selected_challenge": entry.get("selected_challenge"),
                    "reward_points": entry.get("reward_points"),
                    "as_of_date": entry.get("as_of_date"),
                    "timestamp": ts,
                }

    return {
        "user_id": user_id,
        "total_points": total_points,
        "rank": rank,
        "current_badge": current_badge,
        "next_badge": next_badge,
        "points_needed_for_next_badge": points_needed,
        "last_award": last_award,
    }

