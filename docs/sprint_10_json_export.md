# Sprint 10 JSON Export and Run Summary

## Sprint Goal

Export all pipeline outputs to standard JSON files with deterministic
formatting. Provide a convenience function that writes every result set in
a single call and a run summary document that captures pipeline execution
metadata.

## Deliverables

- JSON exporter module.
- Output file structure.
- Run summary model and export.
- Export unit tests.

## Created Files

### `src/gamification_engine/export/__init__.py`

Package initializer for the export module.

### `src/gamification_engine/export/json_exporter.py`

Domain objects to JSON file serialization. Contains:

- `RunSummary` frozen dataclass for pipeline execution metadata.
- Individual export functions for each result type:
  - `export_states()` → `states.json`
  - `export_rewards()` → `rewards.json`
  - `export_ledger()` → `ledger.json`
  - `export_badges()` → `badges.json`
  - `export_leaderboard()` → `leaderboard.json`
  - `export_notifications()` → `notifications.json`
  - `export_run_summary()` → `run_summary.json`
- `export_all()` convenience function that writes every output file.
- Private serialization helpers.

### `tests/unit/export/__init__.py`

Test package initializer.

### `tests/unit/export/test_json_exporter.py`

Comprehensive test suite with snapshot-style determinism checks.

## Module Responsibilities

The exporter performs no computation. It converts existing domain objects
produced by upstream pipeline stages into stable JSON documents.

## Design Decisions

| Decision | Choice |
|---|---|
| JSON indentation | 2 spaces |
| Character encoding | UTF-8 |
| ASCII escaping | `ensure_ascii=False` |
| Date format | ISO 8601 |
| Output overwrite | Yes — ledger append-only semantics are enforced by the ledger module |
| Output directory | Created automatically if missing |
| Key order | Stable, matching `to_dict()` field order |
| Trailing newline | Yes, for POSIX-friendly files |

## Input Structures

The exporter receives typed domain objects from upstream pipeline stages:

- `list[DailyUserState]` — from state builder
- `list[RewardEvent]` — from reward selector
- `list[PointsLedgerEntry]` — from points ledger
- `list[BadgeAssignment]` — from badge engine
- `list[LeaderboardEntry]` — from leaderboard engine
- `list[Notification]` — from notification engine
- `RunSummary` — from orchestrator

## Output Files

```text
data/output/
  states.json
  rewards.json
  ledger.json
  badges.json
  leaderboard.json
  notifications.json
  run_summary.json
```

## Sorting Rules

Each output type has an explicit deterministic sort key:

| Output | Sort Key |
|---|---|
| States | As received (state builder already sorts by user_id) |
| Rewards | `(reward_date, user_id, challenge_id, reward_id)` |
| Ledger | `(created_at, user_id, source, source_ref, ledger_id)` |
| Badges | `(awarded_at, user_id, badge_tier_order, badge_id)` |
| Leaderboard | `rank` ascending |
| Notifications | `(created_at, user_id, notification_type, source_ref, notification_id)` |
| Run Summary | Single object — no sorting needed |

## Dependencies

- Sprint 2: domain models with `to_dict()` serialization.
- Sprint 4: `DailyUserState`.
- Sprint 5: `RewardEvent`.
- Sprint 6: `PointsLedgerEntry`.
- Sprint 7: `BadgeAssignment`.
- Sprint 8: `LeaderboardEntry`.
- Sprint 9: `Notification`.

## Test Coverage

Tests cover:

- File creation for all seven output types.
- Empty input handling (produces valid empty JSON arrays).
- ISO date formatting.
- Stable key ordering.
- Deterministic sorting for each output type.
- Badge tier ordering (Bronze → Silver → Gold).
- Leaderboard rank ordering.
- Snapshot-style byte-identical determinism across repeated runs.
- Output directory auto-creation for nested paths.
- JSON formatting: 2-space indent, UTF-8 encoding, no ASCII escaping.
- `RunSummary` model: `to_dict()`, frozen immutability.

## Definition of Done

- [x] All outputs written as JSON.
- [x] JSON key order is stable.
- [x] Dates use ISO format.
- [x] Output directory created when missing.
- [x] Export tests perform snapshot-style verification.
- [x] Run summary captures pipeline execution metadata.
- [x] Module performs no business logic.
- [x] Type hints on all public functions.
- [x] Docstrings on all public functions.
- [x] Deterministic output ordering for all result types.
