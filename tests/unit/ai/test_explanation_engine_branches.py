"""Branch-focused unit tests for the deterministic explanation engine.

Complements test_explanation_engine.py by covering edge branches:
fallbacks without challenge ids, invalid ids, fully-earned badges,
incomplete leaderboards and condition parse failures.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

from gamification_engine.ai.explanation_engine import (
    _build_reward_id,
    explain_user_query,
)
from gamification_engine.domain.enums import (
    BadgeType,
    ChallengeType,
    RewardReason,
)
from gamification_engine.domain.models import (
    BadgeAssignment,
    ChallengeDefinition,
    DailyUserState,
    LeaderboardEntry,
    PointsLedgerEntry,
)

USER = "u001"
DAY = date(2026, 6, 15)


def _entry(
    points: int,
    source_ref: str,
    created: datetime | None = None,
) -> PointsLedgerEntry:
    return PointsLedgerEntry(
        ledger_id=f"l-{source_ref}",
        user_id=USER,
        points_delta=points,
        source=RewardReason.CHALLENGE_COMPLETED,
        source_ref=source_ref,
        created_at=created or datetime(2026, 6, 15, tzinfo=UTC),
    )


def _challenge(
    challenge_id: str = "C-01",
    condition: str = "watch_minutes_today >= 60",
    is_active: bool = True,
) -> ChallengeDefinition:
    return ChallengeDefinition(
        challenge_id=challenge_id,
        name="Daily Watcher",
        challenge_type=ChallengeType.DAILY,
        condition=condition,
        reward_points=100,
        priority=5,
        is_active=is_active,
    )


def _state() -> DailyUserState:
    return DailyUserState(
        user_id=USER,
        state_date=DAY,
        watch_minutes_today=45,
        watch_minutes_7d=300,
        episodes_completed_today=1,
        episodes_completed_7d=5,
        unique_genres_today=1,
        watch_party_minutes_today=0,
        ratings_today=0,
        ratings_7d=2,
        watch_streak_days=2,
    )


def _explain(question: str, **overrides: object) -> object:
    kwargs: dict[str, object] = {
        "question": question,
        "user_id": USER,
        "state": None,
        "ledger_entries": [],
        "badges": [],
        "leaderboard": [],
        "challenges": [],
    }
    kwargs.update(overrides)
    return explain_user_query(**kwargs)  # type: ignore[arg-type]


def test_reward_won_without_challenge_id_uses_latest_ledger_entry() -> None:
    """Without a challenge id, the most recent reward is explained."""

    ledger = [
        _entry(100, "r-old", datetime(2026, 6, 10, tzinfo=UTC)),
        _entry(150, "r-new", datetime(2026, 6, 14, tzinfo=UTC)),
    ]

    resp = _explain("Ödülü aldım mı?", ledger_entries=ledger)

    assert resp.evidence["challenge_id"] == "r-new"  # type: ignore[attr-defined]
    assert resp.evidence["points"] == 150  # type: ignore[attr-defined]


def test_reward_won_without_any_history_says_no_rewards() -> None:
    """No ledger history means no reward to explain."""

    resp = _explain("Ödülü aldım mı?")

    assert "Henüz kazandığınız bir ödül bulunmuyor" in resp.answer  # type: ignore[attr-defined]


def test_reward_won_for_unwon_challenge_reports_not_won() -> None:
    """Asking about an unwon challenge id must report NOT_WON."""

    resp = _explain(
        "Neden C-01 ödülünü kazandım?",
        challenges=[_challenge("C-01")],
    )

    assert resp.evidence["status"] == "NOT_WON"  # type: ignore[attr-defined]


def test_reward_not_won_without_challenge_id_asks_for_one() -> None:
    """Without a challenge id, the user is asked to be specific."""

    resp = _explain("Neden ödül alamadım?")

    assert "spesifik" in resp.answer  # type: ignore[attr-defined]


def test_reward_not_won_with_unknown_challenge_id_is_rejected() -> None:
    """An id not present in the challenge list is invalid."""

    resp = _explain(
        "Neden C-99 ödülünü alamadım?",
        challenges=[_challenge("C-01")],
    )

    assert "Geçersiz challenge ID" in resp.answer  # type: ignore[attr-defined]


def test_reward_not_won_when_already_won_says_so() -> None:
    """If the ledger shows the reward was won, say it was won."""

    reward_id = _build_reward_id(USER, DAY, "C-01")
    ledger = [_entry(100, reward_id, datetime(2026, 6, 15, tzinfo=UTC))]

    resp = _explain(
        "Neden C-01 ödülünü alamadım?",
        challenges=[_challenge("C-01")],
        ledger_entries=ledger,
    )

    assert resp.evidence["status"] == "WON"  # type: ignore[attr-defined]


def test_reward_not_won_with_unparseable_condition_reports_error() -> None:
    """A condition over an unknown field yields a controlled error answer."""

    resp = _explain(
        "Neden C-01 ödülünü alamadım?",
        challenges=[_challenge("C-01", condition="unknown_field >= 1")],
        state=_state(),
    )

    assert "hata oluştu" in resp.answer  # type: ignore[attr-defined]
    assert "error" in resp.evidence  # type: ignore[attr-defined]


def test_badge_question_when_all_badges_earned() -> None:
    """A user holding every badge gets the congratulation answer."""

    badges = [
        BadgeAssignment(
            user_id=USER,
            badge_type=badge_type,
            awarded_at=DAY,
        )
        for badge_type in (BadgeType.BRONZE, BadgeType.SILVER, BadgeType.GOLD)
    ]

    resp = _explain("Sıradaki rozetim ne olacak?", badges=badges)

    assert resp.evidence["badge_status"] == "ALL_EARNED"  # type: ignore[attr-defined]


def test_leaderboard_rank_without_visible_higher_entry() -> None:
    """A ranked user without a visible rank-1 entry still gets an answer."""

    leaderboard = [
        LeaderboardEntry(rank=2, user_id=USER, total_points=120, badges=()),
    ]

    resp = _explain(
        "Liderlik tablosunda neden bu sıradayım?",
        leaderboard=leaderboard,
    )

    assert resp.evidence == {"rank": 2, "total_points": 120}  # type: ignore[attr-defined]


def test_challenge_id_extracted_by_pattern_when_not_in_catalog() -> None:
    """Challenge ids are recognized by pattern even with an empty catalog."""

    resp = _explain("Neden C-42 ödülünü alamadım?")

    assert "C-42" in resp.answer  # type: ignore[attr-defined]
