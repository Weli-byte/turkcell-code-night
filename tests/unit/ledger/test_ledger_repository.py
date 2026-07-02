"""Tests for points ledger JSON repository helpers."""

import json
from datetime import date

import pytest

from gamification_engine.domain.enums import RewardReason
from gamification_engine.domain.errors import IngestionError
from gamification_engine.domain.models import RewardEvent
from gamification_engine.ledger.ledger_repository import (
    load_points_ledger_json,
    write_points_ledger_json,
)
from gamification_engine.ledger.points_ledger import append_reward_events


def test_load_points_ledger_json_returns_empty_for_missing_file(tmp_path) -> None:
    """A missing ledger file represents empty history."""

    assert load_points_ledger_json(tmp_path / "missing.json") == []


def test_write_and_load_points_ledger_json_round_trips_entries(tmp_path) -> None:
    """Repository should persist and restore ledger entries."""

    reward = RewardEvent(
        reward_id="reward-1",
        user_id="U1",
        challenge_id="C-01",
        reward_points=80,
        reward_date=date(2026, 3, 14),
        reason=RewardReason.CHALLENGE_COMPLETED,
    )
    ledger_entries = append_reward_events([], [reward])
    path = tmp_path / "ledger.json"

    write_points_ledger_json(path, ledger_entries)
    loaded_entries = load_points_ledger_json(path)

    assert loaded_entries == ledger_entries
    raw_payload = json.loads(path.read_text(encoding="utf-8"))
    assert raw_payload[0]["source"] == "CHALLENGE_COMPLETED"


def test_load_points_ledger_json_rejects_non_list_payload(tmp_path) -> None:
    """Ledger JSON top-level payload must be a list."""

    path = tmp_path / "ledger.json"
    path.write_text("{}", encoding="utf-8")

    with pytest.raises(IngestionError, match="must contain a list"):
        load_points_ledger_json(path)


def test_load_points_ledger_json_rejects_invalid_entry(tmp_path) -> None:
    """Invalid ledger entries should fail ingestion."""

    path = tmp_path / "ledger.json"
    path.write_text('[{"ledger_id": ""}]', encoding="utf-8")

    with pytest.raises(IngestionError, match="Invalid ledger entry"):
        load_points_ledger_json(path)

