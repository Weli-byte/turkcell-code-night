"""
AI Layer – Fallback Engine.

Provides graceful fallback responses when the chatbot cannot find
relevant data or when an intent is unrecognised.  Ensures the user
always receives a meaningful reply.
"""

from typing import Optional


FALLBACK_MESSAGES: dict[str, str] = {
    "leaderboard": (
        "I couldn't find leaderboard data right now. "
        "Please make sure the pipeline has been run at least once."
    ),
    "badge": (
        "I don't have badge information available at the moment. "
        "Badges are assigned after challenge awards are processed."
    ),
    "points": (
        "I couldn't retrieve your points total. "
        "Ensure your activity has been recorded and the pipeline has run."
    ),
    "challenge": (
        "I don't have challenge award data available. "
        "Challenges are evaluated daily based on your engagement."
    ),
    "notification": (
        "No notifications found. "
        "Notifications are generated when you complete challenges."
    ),
    "general": (
        "I'm your gamification assistant. You can ask me about:\n"
        "  • Your points and ranking\n"
        "  • Badge progress\n"
        "  • Challenge awards\n"
        "  • Notifications\n"
        "  • Leaderboard standings"
    ),
}

PERSONALISED_PREFIX = "Hi{user_part}! "


def generate_fallback_response(
    intent: str,
    user_id: Optional[str] = None,
) -> str:
    """Generate a fallback response for the given intent.

    Returns a user-friendly message explaining why data is unavailable
    and suggesting next steps.  If a *user_id* is provided the response
    is personalised with a greeting.

    Args:
        intent: The classified intent string.
        user_id: Optional user identifier for personalisation.

    Returns:
        A plain-text fallback response string.
    """
    user_part = f" {user_id}" if user_id else ""
    prefix = PERSONALISED_PREFIX.format(user_part=user_part)

    base_message = FALLBACK_MESSAGES.get(
        intent,
        FALLBACK_MESSAGES["general"],
    )

    return prefix + base_message


def generate_error_response(error: Exception) -> str:
    """Generate a safe error response without leaking internals.

    Args:
        error: The exception that was caught.

    Returns:
        A generic error message string safe for end-user display.
    """
    return (
        "Sorry, something went wrong while processing your request. "
        "Please try again later."
    )


def generate_empty_data_response(data_name: str) -> str:
    """Generate a response for when a specific data source is empty.

    Args:
        data_name: A human-readable name for the missing data
            (e.g. "leaderboard", "badge awards").

    Returns:
        A message informing the user the data is currently empty.
    """
    return (
        f"The {data_name} data is currently empty. "
        f"This usually means the pipeline hasn't processed data yet."
    )
