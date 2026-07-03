"""Unit tests for the AI explanation layer."""

from __future__ import annotations

from datetime import date, datetime, timezone

from gamification_engine.ai.explanation_engine import (
    ExplanationIntent,
    classify_intent,
    explain_user_query,
)
from gamification_engine.domain.enums import (
    BadgeType,
    ChallengeType,
    NotificationChannel,
    NotificationType,
    RewardReason,
)
from gamification_engine.domain.models import (
    BadgeAssignment,
    ChallengeDefinition,
    DailyUserState,
    LeaderboardEntry,
    PointsLedgerEntry,
    RewardEvent,
)


def _make_state(user_id: str = "u001") -> DailyUserState:
    return DailyUserState(
        user_id=user_id,
        state_date=date(2026, 6, 15),
        watch_minutes_today=45,  # Did not reach 60 min condition
        watch_minutes_7d=300,
        episodes_completed_today=1,
        episodes_completed_7d=5,
        unique_genres_today=1,
        watch_party_minutes_today=0,
        ratings_today=0,
        ratings_7d=2,
        watch_streak_days=2,
    )


def _make_challenge(
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


def test_classify_intent() -> None:
    """Test classification of user queries into intents."""

    assert classify_intent("Kaç puanım var?") == ExplanationIntent.POINTS_STATUS
    assert classify_intent("Puan durumumu göster") == ExplanationIntent.POINTS_STATUS

    assert (
        classify_intent("Liderlik tablosunda kaçıncı sıradayım?")
        == ExplanationIntent.LEADERBOARD_POSITION
    )
    assert (
        classify_intent("Derecem nedir?")
        == ExplanationIntent.LEADERBOARD_POSITION
    )

    assert (
        classify_intent("Gold rozetine nasıl ulaşırım?")
        == ExplanationIntent.BADGE_REQUIREMENT
    )
    assert (
        classify_intent("Gümüş rozet için ne gerekiyor?")
        == ExplanationIntent.BADGE_REQUIREMENT
    )

    assert (
        classify_intent("Neden c-01 ödülünü kazandım?")
        == ExplanationIntent.REWARD_WON
    )
    assert classify_intent("Ödülü aldım mı?") == ExplanationIntent.REWARD_WON

    assert (
        classify_intent("Neden C-02 ödülünü alamadım?")
        == ExplanationIntent.REWARD_NOT_WON
    )
    assert (
        classify_intent("C-01 neden verilmedi?")
        == ExplanationIntent.REWARD_NOT_WON
    )

    assert classify_intent("Bugün hava nasıl?") == ExplanationIntent.UNKNOWN


def test_explain_points_status() -> None:
    """Test explanation of points status."""

    ledger = [
        PointsLedgerEntry(
            ledger_id="l1",
            user_id="u001",
            points_delta=100,
            source=RewardReason.CHALLENGE_COMPLETED,
            source_ref="r1",
            created_at=datetime.now(timezone.utc),
        ),
        PointsLedgerEntry(
            ledger_id="l2",
            user_id="u001",
            points_delta=150,
            source=RewardReason.CHALLENGE_COMPLETED,
            source_ref="r2",
            created_at=datetime.now(timezone.utc),
        ),
    ]

    resp = explain_user_query(
        question="Kaç puanım var?",
        user_id="u001",
        state=None,
        ledger_entries=ledger,
        badges=[],
        leaderboard=[],
        challenges=[],
    )

    assert resp.user_id == "u001"
    assert "250 puan" in resp.answer
    assert resp.evidence["total_points"] == 250


def test_explain_leaderboard_position() -> None:
    """Test explanation of leaderboard position."""

    leaderboard = [
        LeaderboardEntry(rank=1, user_id="u002", total_points=500),
        LeaderboardEntry(rank=2, user_id="u001", total_points=350),
        LeaderboardEntry(rank=3, user_id="u003", total_points=200),
    ]

    # Test Rank 1 user
    resp_rank1 = explain_user_query(
        question="Sıram nedir?",
        user_id="u002",
        state=None,
        ledger_entries=[],
        badges=[],
        leaderboard=leaderboard,
        challenges=[],
    )
    assert "1. sıradasınız" in resp_rank1.answer
    assert resp_rank1.evidence["rank"] == 1

    # Test Rank > 1 user
    resp_rank2 = explain_user_query(
        question="Liderlik tablosundaki durumum",
        user_id="u001",
        state=None,
        ledger_entries=[],
        badges=[],
        leaderboard=leaderboard,
        challenges=[],
    )
    assert "2. sıradasınız" in resp_rank2.answer
    assert "u002" in resp_rank2.answer
    assert "150 puan" in resp_rank2.answer
    assert resp_rank2.evidence["points_to_next"] == 150
    assert resp_rank2.evidence["next_user_id"] == "u002"

    # Test user not in leaderboard
    resp_not_in = explain_user_query(
        question="Sıram nedir?",
        user_id="u005",
        state=None,
        ledger_entries=[],
        badges=[],
        leaderboard=leaderboard,
        challenges=[],
    )
    assert "tablosunda yer almıyorsunuz" in resp_not_in.answer
    assert resp_not_in.evidence["rank"] is None


def test_explain_badge_requirements() -> None:
    """Test explanation of badge requirements."""

    badges = [
        BadgeAssignment(
            user_id="u001", badge_type=BadgeType.BRONZE, awarded_at=date(2026, 1, 1)
        )
    ]
    ledger = [
        PointsLedgerEntry(
            ledger_id="l1",
            user_id="u001",
            points_delta=600,  # Total 600 points, meets Bronze (500) but not Silver (1500)
            source=RewardReason.CHALLENGE_COMPLETED,
            source_ref="r1",
            created_at=datetime.now(timezone.utc),
        )
    ]

    # Test asking for already earned badge
    resp_earned = explain_user_query(
        question="Bronze rozeti için ne yapmalıyım?",
        user_id="u001",
        state=None,
        ledger_entries=ledger,
        badges=badges,
        leaderboard=[],
        challenges=[],
    )
    assert "rozetine zaten ulaştınız" in resp_earned.answer

    # Test asking for next badge (Silver)
    resp_next = explain_user_query(
        question="Silver rozetine nasıl ulaşırım?",
        user_id="u001",
        state=None,
        ledger_entries=ledger,
        badges=badges,
        leaderboard=[],
        challenges=[],
    )
    assert "SILVER rozetine ulaşmak için 1500 puana" in resp_next.answer
    assert "900 puan daha" in resp_next.answer
    assert resp_next.evidence["remaining_points"] == 900

    # Test asking general rozet question (should default to Silver)
    resp_general = explain_user_query(
        question="Sıradaki rozet için ne gerekiyor?",
        user_id="u001",
        state=None,
        ledger_entries=ledger,
        badges=badges,
        leaderboard=[],
        challenges=[],
    )
    assert "SILVER rozetine ulaşmak için" in resp_general.answer


def test_explain_reward_won() -> None:
    """Test explanation of reward won."""

    challenges = [_make_challenge("C-01")]
    rewards = [
        RewardEvent(
            reward_id="reward-abc",
            user_id="u001",
            challenge_id="C-01",
            reward_points=100,
            reward_date=date(2026, 6, 15),
            reason=RewardReason.CHALLENGE_COMPLETED,
        )
    ]

    # Test won in current batch run
    resp_curr = explain_user_query(
        question="Neden C-01 ödülünü kazandım?",
        user_id="u001",
        state=None,
        ledger_entries=[],
        badges=[],
        leaderboard=[],
        challenges=challenges,
        rewards=rewards,
    )
    assert "Challenge C-01 tamamlandı" in resp_curr.answer
    assert resp_curr.evidence["status"] == "WON"

    # Test won in history (ledger)
    ledger = [
        PointsLedgerEntry(
            ledger_id="l1",
            user_id="u001",
            points_delta=100,
            source=RewardReason.CHALLENGE_COMPLETED,
            # matches deterministic reward ID for u001, date 2026-06-15, C-01
            source_ref="reward-25a286d9123c4981",
            created_at=datetime(2026, 6, 15, 0, 0, 0, tzinfo=timezone.utc),
        )
    ]
    resp_hist = explain_user_query(
        question="Neden C-01 ödülünü kazandım?",
        user_id="u001",
        state=None,
        ledger_entries=ledger,
        badges=[],
        leaderboard=[],
        challenges=challenges,
        rewards=[],
    )
    assert "Challenge C-01 tamamlandı. 2026-06-15 tarihinde" in resp_hist.answer
    assert resp_hist.evidence["status"] == "WON"


def test_explain_reward_not_won() -> None:
    """Test explanation of reward not won cases."""

    challenges = [
        _make_challenge("C-01"),
        _make_challenge("C-02", is_active=False),
        _make_challenge("C-03", condition="episodes_completed_today >= 5"),
    ]

    # 1. Inactive Challenge
    resp_inactive = explain_user_query(
        question="Neden C-02 alamadım?",
        user_id="u001",
        state=None,
        ledger_entries=[],
        badges=[],
        leaderboard=[],
        challenges=challenges,
    )
    assert "aktif değil" in resp_inactive.answer

    # 2. Suppressed Challenge
    rewards = [
        RewardEvent(
            reward_id="reward-abc",
            user_id="u001",
            challenge_id="C-03",
            reward_points=150,
            reward_date=date(2026, 6, 15),
            reason=RewardReason.CHALLENGE_COMPLETED,
            suppressed_challenge_ids=("C-01",),
        )
    ]
    resp_supp = explain_user_query(
        question="Neden C-01 alamadım?",
        user_id="u001",
        state=None,
        ledger_entries=[],
        badges=[],
        leaderboard=[],
        challenges=challenges,
        rewards=rewards,
    )
    assert "selected_challenge_id=C-03" in resp_supp.answer or "C-03" in resp_supp.answer
    assert "öncelikli" in resp_supp.answer
    assert resp_supp.evidence["status"] == "SUPPRESSED"

    # 3. No DailyUserState
    resp_no_state = explain_user_query(
        question="Neden C-01 alamadım?",
        user_id="u001",
        state=None,
        ledger_entries=[],
        badges=[],
        leaderboard=[],
        challenges=challenges,
        rewards=[],
    )
    assert "DailyUserState kaydınız bulunamadığı için" in resp_no_state.answer

    # 4. Condition Not Met
    state = _make_state()
    resp_cond = explain_user_query(
        question="Neden C-01 alamadım?",
        user_id="u001",
        state=state,
        ledger_entries=[],
        badges=[],
        leaderboard=[],
        challenges=challenges,
        rewards=[],
    )
    assert "koşulu (watch_minutes_today >= 60) sağlanamadı" in resp_cond.answer
    assert "watch_minutes_today = 45" in resp_cond.answer
    assert resp_cond.evidence["current_value"] == 45
    assert resp_cond.evidence["required_value"] == 60


def test_explain_unknown() -> None:
    """Test explanation fallback for unknown queries."""

    resp = explain_user_query(
        question="Naber?",
        user_id="u001",
        state=None,
        ledger_entries=[],
        badges=[],
        leaderboard=[],
        challenges=[],
    )
    assert "Sorunuzu tam olarak anlayamadım" in resp.answer
