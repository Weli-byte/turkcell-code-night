"""Tests for the JSON export module.

Sprint 10 acceptance criteria:
    - All outputs are written as JSON.
    - JSON key order is stable.
    - Dates are in ISO format.
    - Output directory is created when it does not exist.
    - Export tests perform snapshot-style verification.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from gamification_engine.domain.enums import (
    BadgeType,
    NotificationChannel,
    NotificationType,
    RewardReason,
)
from gamification_engine.domain.models import (
    BadgeAssignment,
    DailyUserState,
    LeaderboardEntry,
    Notification,
    PointsLedgerEntry,
    RewardEvent,
)
from gamification_engine.export.json_exporter import (
    RunSummary,
    export_all,
    export_badges,
    export_leaderboard,
    export_ledger,
    export_notifications,
    export_rewards,
    export_run_summary,
    export_states,
)

# ---------------------------------------------------------------------------
# Fixtures: reusable domain objects
# ---------------------------------------------------------------------------

_RUN_DATE = date(2026, 6, 15)
_CREATED_AT = datetime(2026, 6, 15, 0, 0, 0, tzinfo=UTC)


def _make_state(user_id: str = "u001") -> DailyUserState:
    return DailyUserState(
        user_id=user_id,
        state_date=_RUN_DATE,
        watch_minutes_today=90,
        watch_minutes_7d=420,
        episodes_completed_today=3,
        episodes_completed_7d=15,
        unique_genres_today=2,
        watch_party_minutes_today=30,
        ratings_today=1,
        ratings_7d=5,
        watch_streak_days=4,
    )


def _make_reward(
    reward_id: str = "reward-abc123",
    user_id: str = "u001",
    challenge_id: str = "c001",
) -> RewardEvent:
    return RewardEvent(
        reward_id=reward_id,
        user_id=user_id,
        challenge_id=challenge_id,
        reward_points=100,
        reward_date=_RUN_DATE,
        reason=RewardReason.CHALLENGE_COMPLETED,
        suppressed_challenge_ids=("c002",),
    )


def _make_ledger_entry(
    ledger_id: str = "ledger-abc123",
    user_id: str = "u001",
) -> PointsLedgerEntry:
    return PointsLedgerEntry(
        ledger_id=ledger_id,
        user_id=user_id,
        points_delta=100,
        source=RewardReason.CHALLENGE_COMPLETED,
        source_ref="reward-abc123",
        created_at=_CREATED_AT,
    )


def _make_badge(
    user_id: str = "u001",
    badge_type: BadgeType = BadgeType.BRONZE,
    badge_id: str = "badge-abc123",
) -> BadgeAssignment:
    return BadgeAssignment(
        user_id=user_id,
        badge_type=badge_type,
        awarded_at=_RUN_DATE,
        badge_id=badge_id,
    )


def _make_leaderboard_entry(
    rank: int = 1,
    user_id: str = "u001",
    total_points: int = 2500,
) -> LeaderboardEntry:
    return LeaderboardEntry(
        rank=rank,
        user_id=user_id,
        total_points=total_points,
        badges=(BadgeType.BRONZE, BadgeType.SILVER),
    )


def _make_notification(
    notification_id: str = "notification-abc123",
    user_id: str = "u001",
) -> Notification:
    return Notification(
        notification_id=notification_id,
        user_id=user_id,
        notification_type=NotificationType.CHALLENGE_REWARD,
        channel=NotificationChannel.IN_APP,
        message="Challenge c001 completed. You earned 100 points.",
        created_at=_CREATED_AT,
        source_ref="reward-abc123",
    )


def _make_run_summary() -> RunSummary:
    return RunSummary(
        run_date=_RUN_DATE,
        total_users_processed=3,
        total_rewards_generated=2,
        total_ledger_entries=5,
        total_badges_assigned=4,
        total_notifications_created=6,
        leaderboard_size=3,
    )


def _read_json(path: Path) -> object:
    """Read and parse a JSON file."""
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# States export
# ---------------------------------------------------------------------------


class TestExportStates:
    """Tests for ``export_states``."""

    def test_writes_states_json(self, tmp_path: Path) -> None:
        """States should be written to states.json."""

        path = export_states([_make_state()], tmp_path)

        assert path == tmp_path / "states.json"
        assert path.exists()
        data = _read_json(path)
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["user_id"] == "u001"
        assert data[0]["state_date"] == "2026-06-15"

    def test_empty_states_writes_empty_list(self, tmp_path: Path) -> None:
        """Empty input should produce an empty JSON list."""

        path = export_states([], tmp_path)
        assert _read_json(path) == []

    def test_dates_are_iso_format(self, tmp_path: Path) -> None:
        """State dates should use ISO 8601 format."""

        export_states([_make_state()], tmp_path)
        data = _read_json(tmp_path / "states.json")
        assert data[0]["state_date"] == "2026-06-15"

    def test_key_order_is_stable(self, tmp_path: Path) -> None:
        """JSON keys should appear in the same order as to_dict() output."""

        export_states([_make_state()], tmp_path)
        raw = (tmp_path / "states.json").read_text(encoding="utf-8")
        data = json.loads(raw)
        expected_keys = list(_make_state().to_dict().keys())
        assert list(data[0].keys()) == expected_keys


# ---------------------------------------------------------------------------
# Rewards export
# ---------------------------------------------------------------------------


class TestExportRewards:
    """Tests for ``export_rewards``."""

    def test_writes_rewards_json(self, tmp_path: Path) -> None:
        """Rewards should be written to rewards.json."""

        path = export_rewards([_make_reward()], tmp_path)

        assert path == tmp_path / "rewards.json"
        data = _read_json(path)
        assert len(data) == 1
        assert data[0]["reward_id"] == "reward-abc123"
        assert data[0]["reward_date"] == "2026-06-15"
        assert data[0]["reason"] == "CHALLENGE_COMPLETED"

    def test_rewards_sorted_deterministically(self, tmp_path: Path) -> None:
        """Rewards should be sorted by
        (reward_date, user_id, challenge_id, reward_id)."""

        rewards = [
            _make_reward(reward_id="reward-zzz", user_id="u002", challenge_id="c001"),
            _make_reward(reward_id="reward-aaa", user_id="u001", challenge_id="c002"),
            _make_reward(reward_id="reward-bbb", user_id="u001", challenge_id="c001"),
        ]
        export_rewards(rewards, tmp_path)
        data = _read_json(tmp_path / "rewards.json")

        assert [d["reward_id"] for d in data] == [
            "reward-bbb",
            "reward-aaa",
            "reward-zzz",
        ]


# ---------------------------------------------------------------------------
# Ledger export
# ---------------------------------------------------------------------------


class TestExportLedger:
    """Tests for ``export_ledger``."""

    def test_writes_ledger_json(self, tmp_path: Path) -> None:
        """Ledger entries should be written to ledger.json."""

        path = export_ledger([_make_ledger_entry()], tmp_path)

        assert path == tmp_path / "ledger.json"
        data = _read_json(path)
        assert len(data) == 1
        assert data[0]["ledger_id"] == "ledger-abc123"
        assert data[0]["created_at"] == "2026-06-15T00:00:00+00:00"

    def test_ledger_sorted_deterministically(self, tmp_path: Path) -> None:
        """Ledger entries should be sorted by
        (created_at, user_id, source, source_ref, ledger_id)."""

        entries = [
            _make_ledger_entry(ledger_id="ledger-zzz", user_id="u001"),
            _make_ledger_entry(ledger_id="ledger-aaa", user_id="u002"),
            _make_ledger_entry(ledger_id="ledger-bbb", user_id="u001"),
        ]
        export_ledger(entries, tmp_path)
        data = _read_json(tmp_path / "ledger.json")

        assert [d["ledger_id"] for d in data] == [
            "ledger-bbb",
            "ledger-zzz",
            "ledger-aaa",
        ]


# ---------------------------------------------------------------------------
# Badges export
# ---------------------------------------------------------------------------


class TestExportBadges:
    """Tests for ``export_badges``."""

    def test_writes_badges_json(self, tmp_path: Path) -> None:
        """Badge assignments should be written to badges.json."""

        path = export_badges([_make_badge()], tmp_path)

        assert path == tmp_path / "badges.json"
        data = _read_json(path)
        assert len(data) == 1
        assert data[0]["badge_type"] == "BRONZE"
        assert data[0]["awarded_at"] == "2026-06-15"

    def test_badges_sorted_by_tier_order(self, tmp_path: Path) -> None:
        """Badges should be sorted by (awarded_at, user_id, tier_order, badge_id)."""

        badges = [
            _make_badge(badge_type=BadgeType.GOLD, badge_id="badge-gold"),
            _make_badge(badge_type=BadgeType.BRONZE, badge_id="badge-bronze"),
            _make_badge(badge_type=BadgeType.SILVER, badge_id="badge-silver"),
        ]
        export_badges(badges, tmp_path)
        data = _read_json(tmp_path / "badges.json")

        assert [d["badge_type"] for d in data] == ["BRONZE", "SILVER", "GOLD"]


# ---------------------------------------------------------------------------
# Leaderboard export
# ---------------------------------------------------------------------------


class TestExportLeaderboard:
    """Tests for ``export_leaderboard``."""

    def test_writes_leaderboard_json(self, tmp_path: Path) -> None:
        """Leaderboard entries should be written to leaderboard.json."""

        path = export_leaderboard([_make_leaderboard_entry()], tmp_path)

        assert path == tmp_path / "leaderboard.json"
        data = _read_json(path)
        assert len(data) == 1
        assert data[0]["rank"] == 1
        assert data[0]["badges"] == ["BRONZE", "SILVER"]

    def test_leaderboard_sorted_by_rank(self, tmp_path: Path) -> None:
        """Leaderboard entries should appear in ascending rank order."""

        entries = [
            _make_leaderboard_entry(rank=3, user_id="u003", total_points=500),
            _make_leaderboard_entry(rank=1, user_id="u001", total_points=2500),
            _make_leaderboard_entry(rank=2, user_id="u002", total_points=1500),
        ]
        export_leaderboard(entries, tmp_path)
        data = _read_json(tmp_path / "leaderboard.json")

        assert [d["rank"] for d in data] == [1, 2, 3]


# ---------------------------------------------------------------------------
# Notifications export
# ---------------------------------------------------------------------------


class TestExportNotifications:
    """Tests for ``export_notifications``."""

    def test_writes_notifications_json(self, tmp_path: Path) -> None:
        """Notifications should be written to notifications.json."""

        path = export_notifications([_make_notification()], tmp_path)

        assert path == tmp_path / "notifications.json"
        data = _read_json(path)
        assert len(data) == 1
        assert data[0]["notification_type"] == "CHALLENGE_REWARD"
        assert data[0]["created_at"] == "2026-06-15T00:00:00+00:00"

    def test_notifications_sorted_deterministically(self, tmp_path: Path) -> None:
        """Notifications should be sorted by
        (created_at, user_id, type, source_ref, id)."""

        notifications = [
            _make_notification(notification_id="notification-zzz", user_id="u002"),
            _make_notification(notification_id="notification-aaa", user_id="u001"),
        ]
        export_notifications(notifications, tmp_path)
        data = _read_json(tmp_path / "notifications.json")

        assert [d["notification_id"] for d in data] == [
            "notification-aaa",
            "notification-zzz",
        ]


# ---------------------------------------------------------------------------
# Run summary export
# ---------------------------------------------------------------------------


class TestExportRunSummary:
    """Tests for ``export_run_summary``."""

    def test_writes_run_summary_json(self, tmp_path: Path) -> None:
        """Run summary should be written to run_summary.json."""

        path = export_run_summary(_make_run_summary(), tmp_path)

        assert path == tmp_path / "run_summary.json"
        data = _read_json(path)
        assert data["run_date"] == "2026-06-15"
        assert data["total_users_processed"] == 3
        assert data["total_rewards_generated"] == 2
        assert data["total_ledger_entries"] == 5
        assert data["total_badges_assigned"] == 4
        assert data["total_notifications_created"] == 6
        assert data["leaderboard_size"] == 3

    def test_run_summary_key_order(self, tmp_path: Path) -> None:
        """Run summary JSON keys should match to_dict() field order."""

        export_run_summary(_make_run_summary(), tmp_path)
        data = _read_json(tmp_path / "run_summary.json")
        expected_keys = list(_make_run_summary().to_dict().keys())
        assert list(data.keys()) == expected_keys


# ---------------------------------------------------------------------------
# export_all convenience function
# ---------------------------------------------------------------------------


class TestExportAll:
    """Tests for ``export_all``."""

    def test_exports_all_files(self, tmp_path: Path) -> None:
        """All seven output files should be created."""

        result = export_all(
            states=[_make_state()],
            rewards=[_make_reward()],
            ledger_entries=[_make_ledger_entry()],
            badges=[_make_badge()],
            leaderboard=[_make_leaderboard_entry()],
            notifications=[_make_notification()],
            run_summary=_make_run_summary(),
            output_dir=tmp_path,
        )

        expected_files = {
            "states",
            "rewards",
            "ledger",
            "badges",
            "leaderboard",
            "notifications",
            "run_summary",
        }
        assert set(result.keys()) == expected_files

        for path in result.values():
            assert path.exists(), f"{path} was not created."
            data = _read_json(path)
            assert data is not None

    def test_export_all_with_empty_inputs(self, tmp_path: Path) -> None:
        """Empty pipeline results should produce valid empty JSON arrays."""

        result = export_all(
            states=[],
            rewards=[],
            ledger_entries=[],
            badges=[],
            leaderboard=[],
            notifications=[],
            run_summary=RunSummary(
                run_date=_RUN_DATE,
                total_users_processed=0,
                total_rewards_generated=0,
                total_ledger_entries=0,
                total_badges_assigned=0,
                total_notifications_created=0,
                leaderboard_size=0,
            ),
            output_dir=tmp_path,
        )

        for name, path in result.items():
            data = _read_json(path)
            if name == "run_summary":
                assert isinstance(data, dict)
            else:
                assert data == []


# ---------------------------------------------------------------------------
# Output directory auto-creation
# ---------------------------------------------------------------------------


class TestOutputDirectoryCreation:
    """Tests for automatic output directory creation."""

    def test_creates_output_dir_when_missing(self, tmp_path: Path) -> None:
        """Export functions should create the output directory tree."""

        nested = tmp_path / "deep" / "nested" / "output"
        assert not nested.exists()

        export_states([_make_state()], nested)
        assert nested.exists()
        assert (nested / "states.json").exists()


# ---------------------------------------------------------------------------
# JSON formatting
# ---------------------------------------------------------------------------


class TestJsonFormatting:
    """Tests for JSON output format compliance."""

    def test_indent_is_two_spaces(self, tmp_path: Path) -> None:
        """JSON files should use 2-space indentation."""

        export_states([_make_state()], tmp_path)
        raw = (tmp_path / "states.json").read_text(encoding="utf-8")

        # The second line of a pretty-printed JSON list with indent=2 starts
        # with "  {" (2-space indent).
        lines = raw.splitlines()
        assert len(lines) > 1
        assert lines[1].startswith("  ")

    def test_unicode_preserved(self, tmp_path: Path) -> None:
        """Non-ASCII characters should be kept verbatim (ensure_ascii=False)."""

        # We test this indirectly: if ensure_ascii were True, a Turkish
        # character like 'ö' would become '\\u00f6' in the output.
        export_run_summary(_make_run_summary(), tmp_path)
        raw = (tmp_path / "run_summary.json").read_text(encoding="utf-8")
        # The file should parse cleanly and not contain escaped unicode for
        # ASCII-only content.
        assert "\\u" not in raw

    def test_file_encoding_is_utf8(self, tmp_path: Path) -> None:
        """Output files should be encoded in UTF-8."""

        export_states([_make_state()], tmp_path)
        content = (tmp_path / "states.json").read_bytes()
        # UTF-8 BOM should not be present
        assert not content.startswith(b"\xef\xbb\xbf")
        # Should decode as valid UTF-8
        content.decode("utf-8")


# ---------------------------------------------------------------------------
# Determinism (snapshot-style)
# ---------------------------------------------------------------------------


class TestDeterminism:
    """Snapshot-style determinism tests.

    Running the same export twice with the same input should produce
    byte-identical output files.
    """

    def test_states_deterministic(self, tmp_path: Path) -> None:
        """Same states input produces byte-identical output."""

        dir_a = tmp_path / "run_a"
        dir_b = tmp_path / "run_b"
        states = [_make_state("u002"), _make_state("u001")]

        export_states(states, dir_a)
        export_states(states, dir_b)

        assert (dir_a / "states.json").read_bytes() == (
            dir_b / "states.json"
        ).read_bytes()

    def test_rewards_deterministic(self, tmp_path: Path) -> None:
        """Same rewards input produces byte-identical output."""

        dir_a = tmp_path / "run_a"
        dir_b = tmp_path / "run_b"
        rewards = [
            _make_reward(reward_id="reward-2", user_id="u002"),
            _make_reward(reward_id="reward-1", user_id="u001"),
        ]

        export_rewards(rewards, dir_a)
        export_rewards(rewards, dir_b)

        assert (dir_a / "rewards.json").read_bytes() == (
            dir_b / "rewards.json"
        ).read_bytes()

    def test_full_export_deterministic(self, tmp_path: Path) -> None:
        """Full export_all produces byte-identical output across runs."""

        dir_a = tmp_path / "run_a"
        dir_b = tmp_path / "run_b"

        kwargs = dict(
            states=[_make_state("u002"), _make_state("u001")],
            rewards=[_make_reward()],
            ledger_entries=[_make_ledger_entry()],
            badges=[_make_badge()],
            leaderboard=[_make_leaderboard_entry()],
            notifications=[_make_notification()],
            run_summary=_make_run_summary(),
        )

        export_all(**kwargs, output_dir=dir_a)
        export_all(**kwargs, output_dir=dir_b)

        for filename in (
            "states.json",
            "rewards.json",
            "ledger.json",
            "badges.json",
            "leaderboard.json",
            "notifications.json",
            "run_summary.json",
        ):
            assert (dir_a / filename).read_bytes() == (dir_b / filename).read_bytes(), (
                f"{filename} differs between runs"
            )


# ---------------------------------------------------------------------------
# RunSummary model
# ---------------------------------------------------------------------------


class TestRunSummary:
    """Tests for the RunSummary model."""

    def test_to_dict_returns_expected_fields(self) -> None:
        """to_dict should return all summary fields."""

        summary = _make_run_summary()
        d = summary.to_dict()

        assert d["run_date"] == "2026-06-15"
        assert d["total_users_processed"] == 3
        assert d["total_rewards_generated"] == 2
        assert d["total_ledger_entries"] == 5
        assert d["total_badges_assigned"] == 4
        assert d["total_notifications_created"] == 6
        assert d["leaderboard_size"] == 3

    def test_run_summary_is_frozen(self) -> None:
        """RunSummary should be immutable."""

        summary = _make_run_summary()
        with pytest.raises(AttributeError):
            summary.run_date = date(2026, 1, 1)  # type: ignore[misc]
