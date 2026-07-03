"""Serialize domain objects to stable JSON output files.

The exporter performs no computation. It converts pipeline results into
deterministic JSON documents with a stable key order, ISO-formatted dates,
and UTF-8 encoding.  Output directories are created automatically when they
do not exist.

Design decisions (Sprint 10 plan):
    - JSON indentation: 2 spaces
    - Encoding: UTF-8 with ``ensure_ascii=False``
    - Dates: ISO 8601
    - Key order: stable, matching ``to_dict()`` field order
    - Output files are overwritten on each run (ledger append-only semantics
      are enforced by the ledger module, not by the exporter)
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

from gamification_engine.domain.models import (
    BadgeAssignment,
    DailyUserState,
    LeaderboardEntry,
    Notification,
    PointsLedgerEntry,
    RewardEvent,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_JSON_INDENT: int = 2
_JSON_ENCODING: str = "utf-8"


# ---------------------------------------------------------------------------
# Run summary model
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RunSummary:
    """Summary metadata for a single pipeline execution.

    This is a lightweight data container.  The exporter produces it; the
    orchestrator populates it.
    """

    run_date: date
    total_users_processed: int
    total_rewards_generated: int
    total_ledger_entries: int
    total_badges_assigned: int
    total_notifications_created: int
    leaderboard_size: int

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible representation."""

        return {
            "run_date": self.run_date.isoformat(),
            "total_users_processed": self.total_users_processed,
            "total_rewards_generated": self.total_rewards_generated,
            "total_ledger_entries": self.total_ledger_entries,
            "total_badges_assigned": self.total_badges_assigned,
            "total_notifications_created": self.total_notifications_created,
            "leaderboard_size": self.leaderboard_size,
        }


# ---------------------------------------------------------------------------
# JSON serialization helpers
# ---------------------------------------------------------------------------


def _serialize_value(value: Any) -> Any:
    """Convert a domain value into a JSON-safe primitive.

    Handles ``date``, ``datetime``, enum-like objects with a ``.value``
    attribute, and nested containers.
    """

    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if hasattr(value, "value"):
        return value.value
    if isinstance(value, (list, tuple)):
        return [_serialize_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _serialize_value(val) for key, val in value.items()}
    return value


def _to_json_string(payload: Any) -> str:
    """Encode *payload* as a stable, human-readable JSON string.

    Guarantees:
        - 2-space indentation
        - UTF-8 characters kept verbatim (``ensure_ascii=False``)
        - Trailing newline for POSIX-friendly files
    """

    return json.dumps(
        payload,
        ensure_ascii=False,
        indent=_JSON_INDENT,
    ) + "\n"


def _write_json(path: Path, payload: Any) -> None:
    """Persist *payload* as JSON, creating parent directories as needed."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_to_json_string(payload), encoding=_JSON_ENCODING)


# ---------------------------------------------------------------------------
# Individual export helpers
# ---------------------------------------------------------------------------


def export_states(
    states: list[DailyUserState],
    output_dir: str | Path,
) -> Path:
    """Export user state records to ``states.json``.

    States are written in the order supplied by the caller (which should
    already be deterministic from the state builder).
    """

    out = Path(output_dir) / "states.json"
    _write_json(out, [state.to_dict() for state in states])
    return out


def export_rewards(
    rewards: list[RewardEvent],
    output_dir: str | Path,
) -> Path:
    """Export reward events to ``rewards.json``.

    Rewards are sorted by ``(reward_date, user_id, challenge_id, reward_id)``
    before writing to guarantee a stable output order.
    """

    sorted_rewards = sorted(
        rewards,
        key=lambda r: (r.reward_date, r.user_id, r.challenge_id, r.reward_id),
    )
    out = Path(output_dir) / "rewards.json"
    _write_json(out, [reward.to_dict() for reward in sorted_rewards])
    return out


def export_ledger(
    ledger_entries: list[PointsLedgerEntry],
    output_dir: str | Path,
) -> Path:
    """Export points ledger entries to ``ledger.json``.

    Entries are sorted by ``(created_at, user_id, source, source_ref,
    ledger_id)`` before writing to guarantee a stable output order.
    """

    sorted_entries = sorted(
        ledger_entries,
        key=lambda e: (
            e.created_at,
            e.user_id,
            e.source.value,
            e.source_ref,
            e.ledger_id,
        ),
    )
    out = Path(output_dir) / "ledger.json"
    _write_json(out, [entry.to_dict() for entry in sorted_entries])
    return out


def export_badges(
    badges: list[BadgeAssignment],
    output_dir: str | Path,
) -> Path:
    """Export badge assignments to ``badges.json``.

    Badges are sorted by ``(awarded_at, user_id, badge_type, badge_id)``
    before writing to guarantee a stable output order.
    """

    badge_type_order = {"BRONZE": 0, "SILVER": 1, "GOLD": 2}
    sorted_badges = sorted(
        badges,
        key=lambda b: (
            b.awarded_at,
            b.user_id,
            badge_type_order.get(b.badge_type.value, 99),
            b.badge_id or "",
        ),
    )
    out = Path(output_dir) / "badges.json"
    _write_json(out, [badge.to_dict() for badge in sorted_badges])
    return out


def export_leaderboard(
    leaderboard: list[LeaderboardEntry],
    output_dir: str | Path,
) -> Path:
    """Export leaderboard entries to ``leaderboard.json``.

    Entries are written in rank order (ascending rank number).
    """

    sorted_leaderboard = sorted(leaderboard, key=lambda e: e.rank)
    out = Path(output_dir) / "leaderboard.json"
    _write_json(out, [entry.to_dict() for entry in sorted_leaderboard])
    return out


def export_notifications(
    notifications: list[Notification],
    output_dir: str | Path,
) -> Path:
    """Export notification records to ``notifications.json``.

    Notifications are sorted by ``(created_at, user_id, notification_type,
    source_ref, notification_id)`` before writing.
    """

    sorted_notifications = sorted(
        notifications,
        key=lambda n: (
            n.created_at,
            n.user_id,
            n.notification_type.value,
            n.source_ref,
            n.notification_id,
        ),
    )
    out = Path(output_dir) / "notifications.json"
    _write_json(out, [n.to_dict() for n in sorted_notifications])
    return out


def export_run_summary(
    summary: RunSummary,
    output_dir: str | Path,
) -> Path:
    """Export pipeline run summary to ``run_summary.json``."""

    out = Path(output_dir) / "run_summary.json"
    _write_json(out, summary.to_dict())
    return out


# ---------------------------------------------------------------------------
# Convenience: export everything in one call
# ---------------------------------------------------------------------------


def export_all(
    *,
    states: list[DailyUserState],
    rewards: list[RewardEvent],
    ledger_entries: list[PointsLedgerEntry],
    badges: list[BadgeAssignment],
    leaderboard: list[LeaderboardEntry],
    notifications: list[Notification],
    run_summary: RunSummary,
    output_dir: str | Path,
) -> dict[str, Path]:
    """Export every pipeline result set to *output_dir*.

    Returns a mapping of logical name → written file path.
    """

    return {
        "states": export_states(states, output_dir),
        "rewards": export_rewards(rewards, output_dir),
        "ledger": export_ledger(ledger_entries, output_dir),
        "badges": export_badges(badges, output_dir),
        "leaderboard": export_leaderboard(leaderboard, output_dir),
        "notifications": export_notifications(notifications, output_dir),
        "run_summary": export_run_summary(run_summary, output_dir),
    }
