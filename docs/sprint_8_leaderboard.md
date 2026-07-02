# Sprint 8 Leaderboard Engine

## Goal

Sprint 8 adds deterministic leaderboard generation to the new production
package.

The leaderboard receives total points from the points ledger and optional badge
assignments from the badge engine. It produces typed `LeaderboardEntry` rows.

## Added Modules

```text
src/gamification_engine/leaderboard/
  __init__.py
  leaderboard_engine.py
```

## Sorting Rules

Leaderboard ordering:

```text
1. total_points descending
2. user_id ascending
```

Ranks are assigned consecutively:

```text
1, 2, 3, ...
```

Equal scores do not share rank in the MVP policy.

## Badge Display

Leaderboard entries include badge tiers when badge assignments are provided.

Badge order:

```text
BRONZE
SILVER
GOLD
```

Users without point totals do not appear on the leaderboard even if they have
badge assignments.

## Input

```python
user_total_points: dict[str, int]
badge_assignments: Iterable[BadgeAssignment]
limit: int | None
```

## Output

```python
list[LeaderboardEntry]
```

Example:

```json
[
  {
    "rank": 1,
    "user_id": "U1",
    "total_points": 500,
    "badges": ["BRONZE"]
  }
]
```

## Optional Limit

The engine supports an optional non-negative `limit` parameter for Top N
leaderboards.

`limit=None` returns all users.

## Definition of Done

Sprint 8 is complete when:

- Leaderboard entries are sorted by points descending and user ID ascending.
- Ranks are consecutive.
- Equal scores are deterministic.
- Badge assignments are included in configured tier order.
- Empty input returns an empty list.
- Optional Top N limit is supported.
- Unit tests cover sorting, ties, ranks, badges, empty input, and limit.
