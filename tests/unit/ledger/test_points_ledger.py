"""Tests for append-only points ledger behavior."""

from datetime import UTC, date, datetime

from gamification_engine.domain.enums import RewardReason
from gamification_engine.domain.models import PointsLedgerEntry, RewardEvent
from gamification_engine.ledger.points_ledger import (
    append_reward_events,
    calculate_total_points,
)


def _reward(
    reward_id: str,
    user_id: str,
    challenge_id: str,
    points: int,
    reward_date: date = date(2026, 3, 14),
) -> RewardEvent:
    return RewardEvent(
        reward_id=reward_id,
        user_id=user_id,
        challenge_id=challenge_id,
        reward_points=points,
        reward_date=reward_date,
        reason=RewardReason.CHALLENGE_COMPLETED,
    )


def _entry(
    ledger_id: str,
    user_id: str,
    points: int,
    source_ref: str,
) -> PointsLedgerEntry:
    return PointsLedgerEntry(
        ledger_id=ledger_id,
        user_id=user_id,
        points_delta=points,
        source=RewardReason.CHALLENGE_COMPLETED,
        source_ref=source_ref,
        created_at=datetime(2026, 3, 13, tzinfo=UTC),
    )


def test_append_reward_events_preserves_existing_entries_and_appends_new() -> None:
    """Existing entries should remain and new reward events should append."""

    existing = [_entry("ledger-existing", "U1", 80, "reward-existing")]
    updated = append_reward_events(
        existing,
        [_reward("reward-new", "U2", "C-01", 100)],
    )

    assert [entry.source_ref for entry in updated] == [
        "reward-existing",
        "reward-new",
    ]
    assert updated[1].ledger_id.startswith("ledger-")
    assert updated[1].created_at.isoformat() == "2026-03-14T00:00:00+00:00"


def test_append_reward_events_is_idempotent_for_existing_source_ref() -> None:
    """Reprocessing the same reward should not duplicate points."""

    existing = [_entry("ledger-existing", "U1", 80, "reward-1")]
    updated = append_reward_events(existing, [_reward("reward-1", "U1", "C-01", 80)])

    assert updated == existing


def test_append_reward_events_deduplicates_reward_batch() -> None:
    """Duplicate rewards in the same batch should create one entry only."""

    updated = append_reward_events(
        [],
        [
            _reward("reward-1", "U1", "C-01", 80),
            _reward("reward-1", "U1", "C-01", 80),
        ],
    )

    assert len(updated) == 1
    assert updated[0].source_ref == "reward-1"


def test_append_reward_events_has_deterministic_ledger_ids() -> None:
    """Same reward should produce the same ledger ID across runs."""

    first = append_reward_events([], [_reward("reward-1", "U1", "C-01", 80)])
    second = append_reward_events([], [_reward("reward-1", "U1", "C-01", 80)])

    assert first[0].ledger_id == second[0].ledger_id


def test_calculate_total_points_returns_user_totals_sorted_by_user_id() -> None:
    """Totals should be aggregated from ledger history."""

    totals = calculate_total_points(
        [
            _entry("ledger-2", "U2", 50, "reward-2"),
            _entry("ledger-1", "U1", 80, "reward-1"),
            _entry("ledger-3", "U1", 20, "reward-3"),
        ]
    )

    assert totals == {"U1": 100, "U2": 50}
