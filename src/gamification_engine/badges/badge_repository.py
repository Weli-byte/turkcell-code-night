"""JSON persistence helpers for badge assignments."""

from __future__ import annotations

import json
from collections.abc import Iterable
from datetime import date
from pathlib import Path
from typing import Any

from gamification_engine.badges.badge_engine import sort_badge_assignments
from gamification_engine.domain.enums import BadgeType
from gamification_engine.domain.errors import IngestionError
from gamification_engine.domain.models import BadgeAssignment


def load_badge_assignments_json(path: str | Path) -> list[BadgeAssignment]:
    """Load badge assignments from JSON.

    Missing files are treated as empty badge history.
    """

    badge_path = Path(path)
    if not badge_path.exists():
        return []
    if not badge_path.is_file():
        raise IngestionError(f"Badge path is not a file: {badge_path}.")

    try:
        raw_data = json.loads(badge_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise IngestionError(f"Could not read badge JSON: {badge_path}.") from exc

    if not isinstance(raw_data, list):
        raise IngestionError("Badge JSON must contain a list of assignments.")

    badges = [_parse_badge_assignment(item, index + 1) for index, item in enumerate(raw_data)]
    return sort_badge_assignments(badges)


def write_badge_assignments_json(
    path: str | Path,
    badges: Iterable[BadgeAssignment],
) -> None:
    """Write badge assignments as deterministic JSON."""

    badge_path = Path(path)
    badge_path.parent.mkdir(parents=True, exist_ok=True)
    payload = [badge.to_dict() for badge in sort_badge_assignments(badges)]
    badge_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _parse_badge_assignment(raw_entry: Any, row_number: int) -> BadgeAssignment:
    if not isinstance(raw_entry, dict):
        raise IngestionError(f"Badge assignment {row_number} must be an object.")

    try:
        return BadgeAssignment(
            user_id=_required_text(raw_entry, "user_id"),
            badge_type=BadgeType(_required_text(raw_entry, "badge_type")),
            awarded_at=date.fromisoformat(_required_text(raw_entry, "awarded_at")),
            badge_id=_optional_text(raw_entry, "badge_id"),
        )
    except (ValueError, TypeError) as exc:
        raise IngestionError(
            f"Invalid badge assignment {row_number}: {exc}"
        ) from exc


def _required_text(raw_entry: dict[str, Any], field_name: str) -> str:
    value = raw_entry.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string.")
    return value.strip()


def _optional_text(raw_entry: dict[str, Any], field_name: str) -> str | None:
    value = raw_entry.get(field_name)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string when present.")
    return value.strip()
