"""Append-only points ledger behavior."""

from __future__ import annotations

import hashlib
from collections import defaultdict
from collections.abc import Iterable
from datetime import datetime, time, timezone

from gamification_engine.domain.models import PointsLedgerEntry, RewardEvent


def append_reward_events(
    existing_entries: Iterable[PointsLedgerEntry],
    reward_events: Iterable[RewardEvent],
) -> list[PointsLedgerEntry]:
    """Append new reward events to the ledger without mutating old entries.

    Existing entries are preserved exactly. A reward event is considered a
    duplicate when its ``reward_id`` already appears as an existing
    ``source_ref`` or when the same reward appears more than once in the input
    reward batch.
    """

    existing = list(existing_entries)
    existing_source_refs = {entry.source_ref for entry in existing}
    batch_source_refs: set[str] = set()

    new_entries: list[PointsLedgerEntry] = []
    for reward_event in sorted(
        reward_events,
        key=lambda reward: (
            reward.reward_date,
            reward.user_id,
            reward.challenge_id,
            reward.reward_id,
        ),
    ):
        if reward_event.reward_id in existing_source_refs:
            continue
        if reward_event.reward_id in batch_source_refs:
            continue

        batch_source_refs.add(reward_event.reward_id)
        new_entries.append(_ledger_entry_from_reward(reward_event))

    return sort_ledger_entries([*existing, *new_entries])


def calculate_total_points(
    ledger_entries: Iterable[PointsLedgerEntry],
) -> dict[str, int]:
    """Calculate total points by user from ledger history."""

    totals: defaultdict[str, int] = defaultdict(int)
    for entry in ledger_entries:
        totals[entry.user_id] += entry.points_delta

    return dict(sorted(totals.items(), key=lambda item: item[0]))


def sort_ledger_entries(
    ledger_entries: Iterable[PointsLedgerEntry],
) -> list[PointsLedgerEntry]:
    """Return ledger entries in deterministic output order."""

    return sorted(
        ledger_entries,
        key=lambda entry: (
            entry.created_at,
            entry.user_id,
            entry.source.value,
            entry.source_ref,
            entry.ledger_id,
        ),
    )


def _ledger_entry_from_reward(reward_event: RewardEvent) -> PointsLedgerEntry:
    return PointsLedgerEntry(
        ledger_id=_build_ledger_id(reward_event),
        user_id=reward_event.user_id,
        points_delta=reward_event.reward_points,
        source=reward_event.reason,
        source_ref=reward_event.reward_id,
        created_at=datetime.combine(
            reward_event.reward_date,
            time.min,
            tzinfo=timezone.utc,
        ),
    )


def _build_ledger_id(reward_event: RewardEvent) -> str:
    raw_key = (
        f"{reward_event.user_id}|"
        f"{reward_event.reward_date.isoformat()}|"
        f"{reward_event.reason.value}|"
        f"{reward_event.reward_id}"
    )
    digest = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()[:16]
    return f"ledger-{digest}"

