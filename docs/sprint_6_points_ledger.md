# Sprint 6 Points Ledger

## Goal

Sprint 6 adds the append-only points ledger for the new production package.

The ledger receives selected `RewardEvent` records from Sprint 5 and turns them
into `PointsLedgerEntry` records. Existing entries are preserved. New entries
are appended only when the reward has not already been recorded.

## Added Modules

```text
src/gamification_engine/ledger/
  __init__.py
  points_ledger.py
  ledger_repository.py
```

## Responsibilities

### points_ledger.py

Provides core ledger behavior:

- Append new reward events.
- Preserve existing ledger entries.
- Prevent duplicate reward entries.
- Calculate total points by user.
- Sort ledger entries deterministically.
- Generate deterministic ledger IDs.

### ledger_repository.py

Provides JSON persistence helpers:

- Load ledger entries from JSON.
- Treat missing ledger file as empty history.
- Write ledger entries to JSON.
- Validate loaded JSON payloads.

## Append-Only Rules

The ledger does not update or delete entries.

Normal flow:

```text
existing ledger + reward events -> updated ledger
```

Duplicate guard:

```text
RewardEvent.reward_id == PointsLedgerEntry.source_ref
```

If a reward ID already exists in the ledger, it is skipped.

## Deterministic ID Strategy

Ledger IDs are generated with SHA-256:

```text
ledger_id = ledger-{sha256(user_id|reward_date|reason|reward_id)[:16]}
```

This makes repeated runs produce the same ledger ID for the same logical
reward.

## Timestamp Strategy

`created_at` is deterministic for business outputs:

```text
created_at = reward_date at 00:00:00 UTC
```

This avoids current-system-time drift in repeated runs.

## Total Points

Totals are calculated from ledger history:

```python
dict[str, int]
```

The dictionary is returned sorted by user ID for deterministic downstream use.

## Input

```python
existing_entries: Iterable[PointsLedgerEntry]
reward_events: Iterable[RewardEvent]
```

## Output

```python
updated_ledger: list[PointsLedgerEntry]
user_total_points: dict[str, int]
```

## Definition of Done

Sprint 6 is complete when:

- Reward events can be appended to existing ledger entries.
- Existing entries are preserved.
- Duplicate rewards do not create duplicate point entries.
- Ledger IDs are deterministic.
- Ledger timestamps are deterministic.
- User totals are calculated from ledger history.
- JSON repository helpers can write and load ledger entries.
- Unit tests cover append, idempotency, totals, and repository behavior.
