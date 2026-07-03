"""JSON persistence helpers for points ledger entries."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from gamification_engine.domain.enums import RewardReason
from gamification_engine.domain.errors import IngestionError
from gamification_engine.domain.models import PointsLedgerEntry
from gamification_engine.ledger.points_ledger import sort_ledger_entries


def load_points_ledger_json(path: str | Path) -> list[PointsLedgerEntry]:
    """Load points ledger entries from a JSON file.

    Missing files are treated as empty history so the first run can start with
    an empty ledger.
    """

    ledger_path = Path(path)
    if not ledger_path.exists():
        return []
    if not ledger_path.is_file():
        raise IngestionError(f"Ledger path is not a file: {ledger_path}.")

    try:
        raw_data = json.loads(ledger_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise IngestionError(f"Could not read ledger JSON: {ledger_path}.") from exc

    if not isinstance(raw_data, list):
        raise IngestionError("Ledger JSON must contain a list of entries.")

    entries = [
        _parse_ledger_entry(item, index + 1) for index, item in enumerate(raw_data)
    ]
    return sort_ledger_entries(entries)


def write_points_ledger_json(
    path: str | Path,
    ledger_entries: list[PointsLedgerEntry],
) -> None:
    """Write ledger entries to JSON in deterministic order."""

    ledger_path = Path(path)
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    payload = [entry.to_dict() for entry in sort_ledger_entries(ledger_entries)]
    ledger_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _parse_ledger_entry(raw_entry: Any, row_number: int) -> PointsLedgerEntry:
    if not isinstance(raw_entry, dict):
        raise IngestionError(f"Ledger entry {row_number} must be an object.")

    try:
        return PointsLedgerEntry(
            ledger_id=_required_text(raw_entry, "ledger_id"),
            user_id=_required_text(raw_entry, "user_id"),
            points_delta=_required_positive_int(raw_entry, "points_delta"),
            source=RewardReason(_required_text(raw_entry, "source")),
            source_ref=_required_text(raw_entry, "source_ref"),
            created_at=datetime.fromisoformat(_required_text(raw_entry, "created_at")),
        )
    except (ValueError, TypeError) as exc:
        raise IngestionError(f"Invalid ledger entry {row_number}: {exc}") from exc


def _required_text(raw_entry: dict[str, Any], field_name: str) -> str:
    value = raw_entry.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string.")
    return value.strip()


def _required_positive_int(raw_entry: dict[str, Any], field_name: str) -> int:
    value = raw_entry.get(field_name)
    if not isinstance(value, int):
        raise ValueError(f"{field_name} must be an integer.")
    if value <= 0:
        raise ValueError(f"{field_name} must be positive.")
    return value
