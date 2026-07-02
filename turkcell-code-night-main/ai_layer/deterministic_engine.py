"""
AI Layer – Deterministic Engine.

Generates structured, reproducible responses based solely on provided
context data.  No LLM calls, no randomness — every output is fully
determined by the input.  Includes advanced reasoning for leaderboard
gap analysis, badge progression intelligence, and velocity-based
estimation of badge attainment timelines.
"""

import math
from typing import Any, Optional

BADGE_TIERS: list[tuple[int, str]] = [
    (300, "Bronze Viewer"),
    (850, "Silver Viewer"),
    (1500, "Gold Viewer"),
]

DATA_UNAVAILABLE = "Data not available."


def _next_badge_info(total_points: int) -> tuple[Optional[str], int]:
    """Determine the next badge tier and points needed.

    Args:
        total_points: The user's current total points.

    Returns:
        A tuple of (next_badge_name, points_needed).
        If the user holds the highest tier, returns (None, 0).
    """
    for threshold, badge_name in BADGE_TIERS:
        if total_points < threshold:
            return badge_name, threshold - total_points
    return None, 0


def _estimate_days(points_needed: int, reward_per_award: int) -> Optional[int]:
    """Estimate days to reach a badge based on earning velocity.

    Uses a simple deterministic model: 1 award per day at the
    given reward rate.

    Args:
        points_needed: Points remaining to the next tier.
        reward_per_award: Points earned per award (daily rate).

    Returns:
        Estimated days as an integer, or None if calculation
        is not possible (zero or negative reward).
    """
    if reward_per_award <= 0 or points_needed <= 0:
        return None
    return math.ceil(points_needed / reward_per_award)


def _handle_leaderboard(context: dict[str, Any]) -> str:
    """Generate a deterministic leaderboard response with gap analysis.

    If the user is ranked and leaderboard data is available, calculates
    the exact points gap to the next rank above.

    Args:
        context: Context dictionary with optional user_rank and
            leaderboard_top keys.

    Returns:
        A formatted leaderboard string.
    """
    user_rank = context.get("user_rank")
    if not user_rank:
        return "You are currently not ranked."

    rank = user_rank.get("rank")
    total_points = user_rank.get("total_points", 0)

    lines = [f"You are ranked #{rank} with {total_points} points."]

    leaderboard_top = context.get("leaderboard_top")
    if leaderboard_top and rank is not None and rank > 1:
        target_rank = rank - 1
        for entry in leaderboard_top:
            if entry.get("rank") == target_rank:
                next_rank_points = entry.get("total_points", 0)
                points_gap = next_rank_points - total_points
                if points_gap > 0:
                    lines.append(
                        f"You need {points_gap} more points to "
                        f"reach rank #{target_rank}."
                    )
                else:
                    lines.append(
                        f"You are tied with rank #{target_rank}."
                    )
                break

    if rank == 1:
        lines.append("You are in first place!")

    return "\n".join(lines)


def _handle_points(context: dict[str, Any]) -> str:
    """Generate a deterministic points response with badge progression.

    Shows current point total, next badge target, and velocity-based
    estimation of when the user might reach it.

    Args:
        context: Context dictionary with optional user_points,
            user_awards, and badge-related keys.

    Returns:
        A formatted points summary string.
    """
    user_points = context.get("user_points")
    if user_points is None:
        return DATA_UNAVAILABLE

    total_points = int(user_points)
    next_badge, points_needed = _next_badge_info(total_points)

    lines = [f"You currently have {total_points} points."]

    if next_badge is not None:
        lines.append(
            f"To reach {next_badge}, you need {points_needed} more points."
        )

        lines.extend(_velocity_estimate(context, next_badge, points_needed))
    else:
        lines.append("You have reached the highest badge tier.")

    return "\n".join(lines)


def _handle_badge(context: dict[str, Any]) -> str:
    """Generate a deterministic badge response with progression intelligence.

    Handles three scenarios:
        1. No badge and no points data → safe fallback message.
        2. No badge but points available → shows points and next badge.
        3. Has badge → shows current badge, next tier, and velocity.

    Args:
        context: Context dictionary with optional user_badges,
            user_points, and award-related keys.

    Returns:
        A formatted badge information string.
    """
    badges = context.get("user_badges")
    user_points_raw = context.get("user_points")

    if not badges:
        if user_points_raw is None:
            return "Points data not available."

        total_points = int(user_points_raw)
        next_badge, points_needed = _next_badge_info(total_points)

        lines = [
            "You do not have a badge yet.",
            f"You currently have {total_points} points.",
        ]

        if next_badge is not None:
            lines.append(
                f"You need {points_needed} more points to reach {next_badge}."
            )
            lines.extend(_velocity_estimate(context, next_badge, points_needed))
        else:
            lines.append("You have reached the highest badge tier.")

        return "\n".join(lines)

    badge_names = [str(b.get("badge_name", "")) for b in badges]
    tier_order = [name for _, name in BADGE_TIERS]

    current_badge = badge_names[0]
    for name in tier_order[::-1]:
        if name in badge_names:
            current_badge = name
            break

    total_points = int(user_points_raw) if user_points_raw is not None else 0
    next_badge, points_needed = _next_badge_info(total_points)

    lines = [f"Your current badge is {current_badge}."]

    if next_badge is not None:
        lines.append(f"Next badge: {next_badge}.")
        lines.append(
            f"To reach {next_badge}, you need {points_needed} more points."
        )
        lines.extend(_velocity_estimate(context, next_badge, points_needed))
    else:
        lines.append("You have reached the highest badge tier.")

    return "\n".join(lines)


def _handle_challenge(context: dict[str, Any]) -> str:
    """Generate a deterministic challenge response.

    Lists number of completed challenges and total points earned.

    Args:
        context: Context dictionary with optional user_awards key.

    Returns:
        A formatted challenge awards summary string.
    """
    awards = context.get("user_awards")
    if not awards:
        return DATA_UNAVAILABLE

    total_earned = sum(int(a.get("reward_points", 0)) for a in awards)

    return (
        f"You have completed {len(awards)} challenge(s) "
        f"and earned a total of {total_earned} points from challenges."
    )


def _handle_notification(context: dict[str, Any]) -> str:
    """Generate a deterministic notification response.

    Returns the count of notifications for the user.

    Args:
        context: Context dictionary with optional
            user_notifications key.

    Returns:
        A formatted notification count string.
    """
    notifs = context.get("user_notifications")
    if not notifs:
        return "You have no notifications."

    return f"You have {len(notifs)} notification(s)."


def _velocity_estimate(
    context: dict[str, Any],
    next_badge: str,
    points_needed: int,
) -> list[str]:
    """Produce velocity-based estimation lines.

    Uses the most recent award's reward_points as the daily earning
    rate (1 award per day model) to estimate days to next badge.

    Args:
        context: Context dictionary with optional user_awards key.
        next_badge: Name of the next badge tier.
        points_needed: Points remaining to reach that tier.

    Returns:
        A list of estimation strings (may be empty if data is
        insufficient).
    """
    lines: list[str] = []

    awards = context.get("user_awards")
    if not awards:
        return lines

    last_award = awards[-1] if isinstance(awards, list) else None
    if last_award is None:
        return lines

    reward_points = int(last_award.get("reward_points", 0))
    if reward_points <= 0:
        return lines

    estimated_days = _estimate_days(points_needed, reward_points)
    if estimated_days is not None:
        lines.append(
            f"At your current earning rate, you may reach {next_badge} "
            f"in approximately {estimated_days} days."
        )

    return lines


_INTENT_HANDLERS: dict[str, Any] = {
    "leaderboard": _handle_leaderboard,
    "points": _handle_points,
    "badge": _handle_badge,
    "challenge": _handle_challenge,
    "notification": _handle_notification,
}


def generate_deterministic_response(
    intent: str,
    user_id: str,
    context: dict[str, Any],
) -> str:
    """Generate a deterministic response based on intent and context.

    Routes to the appropriate intent handler and returns a structured,
    reproducible response derived solely from the provided data.
    No LLM calls are made and no randomness is involved.

    Includes advanced reasoning:
        - Leaderboard gap analysis to next rank.
        - Badge progression intelligence with next-tier guidance.
        - Velocity-based estimation of badge attainment timeline.

    Args:
        intent: The classified intent string.
        user_id: The user identifier.
        context: The context dictionary built from system DataFrames.

    Returns:
        A deterministic response string.  Returns a "data not
        available" message if the intent is unrecognised or required
        context data is missing.
    """
    handler = _INTENT_HANDLERS.get(intent)
    if handler is None:
        return DATA_UNAVAILABLE

    return handler(context)
